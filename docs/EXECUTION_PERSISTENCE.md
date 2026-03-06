# Execution Persistence & Visibility Architecture

This document describes the architecture for maintaining visibility into agent executions across page navigation, refreshes, and connection drops.

## Problem Statement

### Current Behavior

When a user initiates an agent execution (sends a message), the following occurs:

1. **Frontend** opens an SSE connection to `/stream`
2. **Backend** begins agent execution, streaming events to the frontend
3. **LangGraph** checkpoints state to PostgreSQL after each node completes

**The problem:** If the user navigates away, refreshes, or loses connection:

- The SSE stream is terminated
- The frontend loses visibility into the ongoing execution
- The agent **continues running** on the backend (execution is NOT tied to the HTTP connection)
- When the user returns, they see the conversation history but:
  - Miss intermediate status updates ("Searching courses...", "Building path...")
  - Don't know if execution is still running or completed
  - May not see pending interrupt confirmations until they interact

### User Impact

| Scenario | Current Behavior | Expected Behavior |
|----------|------------------|-------------------|
| Navigate away during execution | Execution continues silently; user sees nothing on return | Show "Execution in progress" or final result |
| Refresh during "thinking" | Lost visibility; shows old history | Resume showing current status |
| Connection drop mid-stream | "Error" message; user retries unnecessarily | Detect completion/failure and show appropriate state |
| Return to pending interrupt | No indication until user sends message | Show confirmation card immediately |

---

## Architecture Analysis

### What Currently Persists

| Data | Storage | Survives Navigation | Notes |
|------|---------|---------------------|-------|
| Conversation messages | PostgreSQL (LangGraph checkpoints) | Yes | Loaded via `/history` endpoint |
| Agent state (route, handoff, worklist) | PostgreSQL (LangGraph checkpoints) | Yes | Full state snapshot per node |
| Pending interrupts | PostgreSQL (LangGraph checkpoints) | Yes | Includes `pending_pre_interrupt` for resumption |
| Student profile | PostgreSQL (`student_profiles`) | Yes | Queried fresh on load |
| Course path | PostgreSQL (`course_paths`) | Yes | Queried fresh on load |
| Thread metadata | PostgreSQL (`threads`) | Yes | Thread list for sidebar |
| Current thread ID | localStorage | Yes | Survives refresh, not incognito |

### What Is Lost

| Data | Why Lost | Impact |
|------|----------|--------|
| Streaming status | React state only | No "thinking" indicator on reconnect |
| Current node name | SSE events only | Can't show "Searching courses..." |
| Status messages | SSE events only | Detailed progress lost |
| Partial token stream | Buffer cleared on unmount | Incomplete messages disappear |
| Error messages | React state only | Errors vanish on refresh |

### Key Insight

The **durable state** (checkpoints) and **ephemeral state** (status messages) serve different purposes:

- **Durable:** What happened? What's the final result? Can we resume?
- **Ephemeral:** What's happening RIGHT NOW? What node is executing?

Currently, only durable state persists. Ephemeral state needs a separate persistence mechanism.

---

## Proposed Solution

### Phase 1: PostgreSQL-Based Execution Tracking (MVP)

Use PostgreSQL to track execution lifecycle. This provides durability and uses existing infrastructure.

#### Database Schema

Add to `supabase_schema.sql`:

```sql
-- ============================================================================
-- EXECUTIONS TABLE
-- ============================================================================
-- Tracks active and recent agent executions for visibility across reconnects
-- Updated on execution lifecycle events (start, node change, complete, fail)

CREATE TABLE executions (
    id TEXT PRIMARY KEY,              -- LangGraph run_id
    thread_id TEXT NOT NULL,          -- Associated thread
    user_id TEXT NOT NULL,            -- User who initiated
    status TEXT NOT NULL DEFAULT 'running',  -- running | interrupted | completed | failed
    current_node TEXT,                -- Current/last node (orchestrator, course_search, etc.)
    status_message TEXT,              -- Human-readable status ("Searching for ML courses...")
    started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    error_message TEXT,               -- Error details if failed
    metadata JSONB DEFAULT '{}'::JSONB,  -- Additional context (search params, etc.)
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX idx_executions_thread_id ON executions(thread_id);
CREATE INDEX idx_executions_user_id ON executions(user_id);
CREATE INDEX idx_executions_status ON executions(status) WHERE status = 'running';
CREATE INDEX idx_executions_updated_at ON executions(updated_at DESC);

-- RLS policy
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only access their own executions"
  ON executions FOR ALL
  USING (auth.uid()::TEXT = user_id);

-- Auto-cleanup: Executions older than 24 hours (optional, via pg_cron or app logic)
-- DELETE FROM executions WHERE completed_at < NOW() - INTERVAL '24 hours';
```

#### Backend: Execution Tracking Service

Create `backend/dreampath_processing/database/execution_service.py`:

```python
"""
Execution tracking service for visibility across reconnects.

Tracks execution lifecycle:
- start: When user sends message and agent begins
- update: On node transitions and status changes
- complete: When agent finishes successfully
- interrupt: When waiting for user confirmation
- fail: On errors
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class ExecutionStatus(str, Enum):
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ExecutionRecord:
    id: str
    thread_id: str
    user_id: str
    status: ExecutionStatus
    current_node: Optional[str] = None
    status_message: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None

class ExecutionService:
    """Service for tracking execution state in PostgreSQL."""

    def __init__(self, db_connection):
        self.db = db_connection

    async def start_execution(
        self,
        execution_id: str,
        thread_id: str,
        user_id: str,
        initial_node: str = "orchestrator"
    ) -> ExecutionRecord:
        """Record a new execution starting."""
        query = """
            INSERT INTO executions (id, thread_id, user_id, status, current_node, status_message)
            VALUES ($1, $2, $3, 'running', $4, 'Starting...')
            ON CONFLICT (id) DO UPDATE SET
                status = 'running',
                current_node = $4,
                status_message = 'Starting...',
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
        """
        row = await self.db.fetchrow(query, execution_id, thread_id, user_id, initial_node)
        return self._row_to_record(row)

    async def update_execution(
        self,
        execution_id: str,
        current_node: Optional[str] = None,
        status_message: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        metadata: Optional[dict] = None
    ) -> Optional[ExecutionRecord]:
        """Update execution progress."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = [execution_id]
        param_idx = 2

        if current_node is not None:
            updates.append(f"current_node = ${param_idx}")
            params.append(current_node)
            param_idx += 1

        if status_message is not None:
            updates.append(f"status_message = ${param_idx}")
            params.append(status_message)
            param_idx += 1

        if status is not None:
            updates.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
            if status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
                updates.append("completed_at = CURRENT_TIMESTAMP")

        if metadata is not None:
            updates.append(f"metadata = metadata || ${param_idx}::jsonb")
            params.append(json.dumps(metadata))
            param_idx += 1

        query = f"""
            UPDATE executions
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, *params)
        return self._row_to_record(row) if row else None

    async def complete_execution(
        self,
        execution_id: str,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
        error_message: Optional[str] = None
    ) -> Optional[ExecutionRecord]:
        """Mark execution as completed or failed."""
        query = """
            UPDATE executions
            SET status = $2,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                error_message = $3
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, execution_id, status.value, error_message)
        return self._row_to_record(row) if row else None

    async def get_active_execution(self, thread_id: str) -> Optional[ExecutionRecord]:
        """Get the active execution for a thread, if any."""
        query = """
            SELECT * FROM executions
            WHERE thread_id = $1 AND status IN ('running', 'interrupted')
            ORDER BY updated_at DESC
            LIMIT 1
        """
        row = await self.db.fetchrow(query, thread_id)
        return self._row_to_record(row) if row else None

    async def get_thread_status(self, thread_id: str) -> dict:
        """
        Get comprehensive status for a thread.
        Combines execution tracking with LangGraph interrupt state.
        """
        execution = await self.get_active_execution(thread_id)

        return {
            "has_active_execution": execution is not None,
            "execution_id": execution.id if execution else None,
            "status": execution.status.value if execution else None,
            "current_node": execution.current_node if execution else None,
            "status_message": execution.status_message if execution else None,
            "updated_at": execution.updated_at.isoformat() if execution and execution.updated_at else None,
        }

    def _row_to_record(self, row) -> ExecutionRecord:
        return ExecutionRecord(
            id=row["id"],
            thread_id=row["thread_id"],
            user_id=row["user_id"],
            status=ExecutionStatus(row["status"]),
            current_node=row.get("current_node"),
            status_message=row.get("status_message"),
            started_at=row.get("started_at"),
            updated_at=row.get("updated_at"),
            completed_at=row.get("completed_at"),
            error_message=row.get("error_message"),
            metadata=row.get("metadata"),
        )
```

#### Backend: Modify Status Emission Pattern

The key insight is that status events are already emitted via the `writer` callback throughout the graph. We need to **augment** this pattern to also persist to the database.

**Current pattern** (in `service.py` and nodes):

```python
# Status emitted via writer - goes to SSE stream only
def _emit_status(config: RunnableConfig, node: str, reason: str):
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": node,
                "status": "node_info",
                "reason": reason
            }
        )
        writer(status_event)
```

**Enhanced pattern** - emit AND persist:

```python
# New utility in service.py or a shared module
async def emit_and_persist_status(
    config: RunnableConfig,
    node: str,
    reason: str,
    execution_service: ExecutionService = None
):
    """Emit status to SSE stream AND persist to database for reconnection."""

    # 1. Emit to SSE (existing behavior)
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": node,
                "status": "node_info",
                "reason": reason
            }
        )
        writer(status_event)

    # 2. Persist to database (new behavior)
    execution_id = config.get("configurable", {}).get("run_id")
    if execution_service and execution_id:
        await execution_service.update_execution(
            execution_id=str(execution_id),
            current_node=node,
            status_message=reason
        )
```

**Integration points** - where to call this:

| Location | Current Status Emission | Add Persistence |
|----------|------------------------|-----------------|
| `service.py` message_generator | Node transition events | Yes - wrap existing emission |
| `orchestrator.py` | Route decisions | Yes |
| `course_search.py` | Search agent status | Yes |
| `search_agent/nodes/orchestrator.py` | Task creation | Yes |
| `search_agent/nodes/tool_executor.py` | Search execution | Yes |
| `plan_builder.py` | Course selection | Yes |
| `rebuild.py` | Rebuild progress | Yes |
| `finalize.py` | Final response | Yes (mark complete) |

#### Backend: Status Endpoint

Add to `thread_routes.py` (not `service.py` - follows existing route organization):

```python
@router.get("/{thread_id}/status")
async def get_thread_status(thread_id: str) -> dict:
    """
    Get current execution status for a thread.

    Used by frontend to:
    - Check if execution is still running after reconnect
    - Detect pending interrupts
    - Show appropriate UI state
    """
    global execution_service

    # Get execution tracking status
    execution_status = await execution_service.get_thread_status(thread_id)

    # Also check LangGraph for interrupt state
    agent = get_agent(DEFAULT_AGENT)
    try:
        state = await agent.aget_state(
            config=RunnableConfig(configurable={"thread_id": thread_id})
        )

        # Check for pending interrupts
        interrupted_tasks = [
            task for task in state.tasks
            if hasattr(task, "interrupts") and task.interrupts
        ]

        if interrupted_tasks:
            interrupt_value = interrupted_tasks[0].interrupts[0].value
            execution_status["waiting_for_interrupt"] = True
            execution_status["interrupt_type"] = interrupt_value.get("event_type")
            execution_status["interrupt_data"] = {
                k: v for k, v in interrupt_value.items()
                if k not in ["pending_pre_interrupt"]  # Don't expose internal state
            }
        else:
            execution_status["waiting_for_interrupt"] = False

    except Exception as e:
        logger.warning(f"Could not check interrupt state for {thread_id}: {e}")
        execution_status["waiting_for_interrupt"] = False

    return execution_status
```

#### Frontend: Status Polling Hook

Create `frontend/src/hooks/useExecutionStatus.js`:

```javascript
import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';

/**
 * Hook to track execution status across reconnects.
 *
 * Polls for status when:
 * - Component mounts (initial check)
 * - Tab becomes visible (user returns)
 * - Execution is running (continuous polling)
 *
 * @param {string} threadId - The thread to monitor
 * @param {Object} options - Configuration options
 * @param {number} options.pollInterval - Polling interval in ms (default: 2000)
 * @param {boolean} options.enabled - Whether polling is enabled (default: true)
 */
export function useExecutionStatus(threadId, options = {}) {
  const { pollInterval = 2000, enabled = true } = options;

  const [status, setStatus] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState(null);

  const checkStatus = useCallback(async () => {
    if (!threadId || !enabled) return null;

    try {
      const response = await api.getThreadStatus(threadId);
      setStatus(response);
      setError(null);
      return response;
    } catch (err) {
      setError(err);
      return null;
    }
  }, [threadId, enabled]);

  // Initial check and visibility change handler
  useEffect(() => {
    if (!threadId || !enabled) return;

    // Check immediately on mount
    checkStatus();

    // Check when tab becomes visible
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkStatus();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [threadId, enabled, checkStatus]);

  // Continuous polling when execution is running
  useEffect(() => {
    if (!status?.has_active_execution || status?.status !== 'running') {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    const interval = setInterval(checkStatus, pollInterval);

    return () => {
      clearInterval(interval);
      setIsPolling(false);
    };
  }, [status?.has_active_execution, status?.status, pollInterval, checkStatus]);

  return {
    status,
    isPolling,
    error,
    refetch: checkStatus,

    // Convenience accessors
    isRunning: status?.status === 'running',
    isInterrupted: status?.waiting_for_interrupt === true,
    currentNode: status?.current_node,
    statusMessage: status?.status_message,
  };
}
```

#### Frontend: ChatWindow Integration

Update `frontend/src/components/ChatWindow.jsx`:

```javascript
import { useExecutionStatus } from '../hooks/useExecutionStatus';

function ChatWindow({ threadId, ... }) {
  const {
    status,
    isRunning,
    isInterrupted,
    statusMessage,
    refetch: refetchStatus
  } = useExecutionStatus(threadId);

  // Reload history when execution completes
  useEffect(() => {
    if (status && !status.has_active_execution && previousStatus?.has_active_execution) {
      // Execution just completed - reload history
      loadThreadHistory(threadId);
    }
  }, [status?.has_active_execution]);

  // Show reconnection status
  const renderReconnectionBanner = () => {
    if (isRunning) {
      return (
        <div className="reconnection-banner">
          <Spinner size="small" />
          <span>{statusMessage || 'Processing...'}</span>
        </div>
      );
    }

    if (isInterrupted) {
      return (
        <div className="reconnection-banner interrupt">
          <span>Waiting for your confirmation</span>
          <button onClick={() => loadThreadHistory(threadId)}>
            Show confirmation
          </button>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="chat-window">
      {renderReconnectionBanner()}
      {/* ... existing chat UI ... */}
    </div>
  );
}
```

#### Frontend: API Client Addition

Add to `frontend/src/lib/api.js`:

```javascript
/**
 * Get execution status for a thread.
 * Used for reconnection and visibility across page navigation.
 */
async getThreadStatus(threadId) {
  const response = await fetch(`${this.baseUrl}/threads/${threadId}/status`, {
    headers: this.getHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to get thread status: ${response.statusText}`);
  }

  return response.json();
}
```

---

### Phase 2: Redis Hybrid Architecture (Future)

When real-time status updates become a priority (sub-second granularity), add Redis as a caching layer.

#### Why Redis?

| Concern | PostgreSQL | Redis |
|---------|------------|-------|
| Write latency | 10-50ms | <1ms |
| Update frequency | Every 5+ seconds | Sub-second |
| Durability | High | Low (ephemeral) |
| TTL support | Manual cleanup | Native |
| Connection overhead | Pool management | Simple |

#### Hybrid Data Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Flow                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Node Execution                                                  │
│       │                                                          │
│       ▼                                                          │
│  emit_and_persist_status()                                       │
│       │                                                          │
│       ├──────────────────┬──────────────────┐                   │
│       ▼                  ▼                  ▼                    │
│   SSE Stream         Redis               PostgreSQL              │
│   (real-time)     (current status)    (lifecycle events)         │
│                                                                  │
│   - Token stream     - current_node     - execution start        │
│   - All events       - status_message   - execution complete     │
│                      - updated_at       - execution failed       │
│                      - TTL: 30 min      - interrupt state        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Redis Key Structure

```
# Current execution status (primary lookup)
execution:{thread_id}:current
  → Hash {
      run_id: "abc-123",
      status: "running",
      node: "course_search",
      message: "Found 8 ML courses, checking prerequisites...",
      started_at: "2024-01-30T10:00:00Z",
      updated_at: "2024-01-30T10:00:15Z",
      user_id: "user-uuid"
    }
  → TTL: 1800 seconds (30 minutes)

# Optional: Streaming state (for "thinking" indicator)
execution:{thread_id}:stream
  → Hash {
      is_streaming: "true",
      tokens_received: "142",
      last_chunk_at: "2024-01-30T10:00:16Z"
    }
  → TTL: 60 seconds (short-lived)
```

#### Update Frequency

| Event | Redis | PostgreSQL |
|-------|-------|------------|
| Execution starts | HSET + EXPIRE | INSERT |
| Node transition | HSET (node, message) | — |
| Status message | HSET (message, updated_at) | — |
| LLM streaming | HSET stream hash | — |
| Interrupt | HSET (status: interrupted) | UPDATE |
| Complete | DEL (or let expire) | UPDATE |
| Fail | HSET (status: failed) | UPDATE |

#### Infrastructure Requirements

**Local Development:**
```yaml
# Add to compose.yml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data

volumes:
  redis_data:
```

**Production (Fly.io):**
- Option 1: Upstash Redis (serverless, ~$0.20/100K requests)
- Option 2: Fly.io Redis (persistent, ~$5/month)

#### Code Changes for Redis

```python
# backend/cache/redis_client.py
import redis.asyncio as redis
from core import settings

class ExecutionCache:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.ttl = 1800  # 30 minutes

    async def set_status(
        self,
        thread_id: str,
        run_id: str,
        node: str,
        message: str,
        status: str = "running"
    ):
        key = f"execution:{thread_id}:current"
        await self.redis.hset(key, mapping={
            "run_id": run_id,
            "status": status,
            "node": node,
            "message": message,
            "updated_at": datetime.utcnow().isoformat()
        })
        await self.redis.expire(key, self.ttl)

    async def get_status(self, thread_id: str) -> Optional[dict]:
        key = f"execution:{thread_id}:current"
        data = await self.redis.hgetall(key)
        return {k.decode(): v.decode() for k, v in data.items()} if data else None

    async def clear_status(self, thread_id: str):
        key = f"execution:{thread_id}:current"
        await self.redis.delete(key)
```

---

## Implementation Checklist

### Phase 1: PostgreSQL MVP

- [ ] **Database**
  - [ ] Add `executions` table to schema
  - [ ] Run migration on Supabase
  - [ ] Add RLS policy

- [ ] **Backend Service**
  - [ ] Create `ExecutionService` class
  - [ ] Initialize in `lifespan()` alongside `StudentDatabaseService`
  - [ ] Pass to nodes via config

- [ ] **Status Tracking Integration**
  - [ ] Modify `message_generator` to call `start_execution` at stream start
  - [ ] Create `emit_and_persist_status` utility
  - [ ] Update `_emit_status` calls in nodes to use new utility
  - [ ] Call `complete_execution` on stream end / error

- [ ] **Status Endpoint**
  - [ ] Add `GET /threads/{thread_id}/status` endpoint
  - [ ] Combine execution tracking with LangGraph interrupt state
  - [ ] Test endpoint responses

- [ ] **Frontend Hook**
  - [ ] Create `useExecutionStatus` hook
  - [ ] Add visibility change listener
  - [ ] Add polling logic for running executions

- [ ] **Frontend Integration**
  - [ ] Add `getThreadStatus` to API client
  - [ ] Integrate hook into `ChatWindow`
  - [ ] Add reconnection banner UI
  - [ ] Auto-reload history on execution complete

- [ ] **Testing**
  - [ ] Test navigation away during execution
  - [ ] Test refresh during execution
  - [ ] Test return to pending interrupt
  - [ ] Test connection drop recovery

### Phase 2: Redis Hybrid (Future)

- [ ] Add Redis to infrastructure
- [ ] Create `ExecutionCache` class
- [ ] Modify `emit_and_persist_status` to write to Redis
- [ ] Update status endpoint to check Redis first
- [ ] Add TTL-based cleanup
- [ ] Performance testing

---

## Status Event Reference

Current status events emitted throughout the graph:

| Node | Event | Message Example |
|------|-------|-----------------|
| `orchestrator` | route_decision | "Routing to course_search" |
| `course_search` | search_start | "Searching for courses matching your interests" |
| `search_agent/orchestrator` | task_created | "Created 3 search tasks" |
| `search_agent/tool_executor` | search_executing | "Executing search: ML courses" |
| `search_agent/tool_executor` | search_complete | "Found 12 courses" |
| `search_agent/finalizer` | summarizing | "Summarizing search results" |
| `plan_builder` | building_plan | "Building course recommendations" |
| `course_path` | executing_operation | "Adding COSC 89.18 to Fall 2025" |
| `course_path` | awaiting_confirmation | "Waiting for your confirmation" |
| `modify_profile` | generating_update | "Generating profile update" |
| `modify_profile` | awaiting_confirmation | "Waiting for your confirmation" |
| `rebuild` | rebuilding | "Rebuilding course path from scratch" |
| `finalize` | generating_response | "Generating final response" |

---

## Key Files Reference

| Component | File | Purpose |
|-----------|------|---------|
| Database Schema | `database/schema/supabase_schema.sql` | Table definitions |
| Execution Service | `database/execution_service.py` | CRUD for executions |
| Status Endpoint | `service/thread_routes.py` | `GET /threads/{thread_id}/status` |
| Status Emission | `service/service.py`, nodes | `emit_and_persist_status` |
| Frontend Hook | `hooks/useExecutionStatus.js` | Polling and state |
| Chat Integration | `components/ChatWindow.jsx` | UI integration |
| API Client | `lib/api.js` | `getThreadStatus` |

---

## Open Questions

1. **Cleanup strategy:** How long to keep completed executions? 24 hours? 7 days?
2. **Error recovery:** Should we auto-retry failed executions?
3. **Multiple tabs:** How to handle same thread open in multiple tabs?
4. **Offline support:** Should we queue messages when offline?

---

## Related Documentation

- [STREAMING_AND_DB_UPDATES.md](./STREAMING_AND_DB_UPDATES.md) - How SSE streaming works
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Production deployment
- [CLAUDE.md](../CLAUDE.md) - Overall architecture
