# Streaming Architecture & Database Update Flow

This document explains how the DreamPath agent streams updates to the frontend and how database writes flow through the system.

## Overview

The system uses **Server-Sent Events (SSE)** via FastAPI's `StreamingResponse`. The frontend receives a continuous stream of events as the agent executes.

## Streaming Modes

The `message_generator` in `service.py` processes three stream modes:

```python
agent.astream(..., stream_mode=["updates", "messages", "custom"], subgraphs=True)
```

| Mode | Purpose | Example Events |
|------|---------|----------------|
| `updates` | Node state changes | Interrupts (confirmation cards), route changes |
| `messages` | LLM token streaming | Finalizer response tokens |
| `custom` | Status events via `writer` callback | "Thinking", "Searching", node status |

## Database Write Timing

### Course Path Operations (`course_path.py`)

```
1. Node executes → calls service.run_stateless()
2. Inside run_stateless(): DB WRITE HAPPENS (agent_v3.py:36-39)
3. interrupt() called with structured metadata
4. SSE yields interrupt → Frontend renders confirmation card
5. User confirms → loop continues or exits to orchestrator
```

**Key point:** DB write happens BEFORE the interrupt/confirmation card.

### Profile Modifications (`modify_profile.py`)

```
1. Node executes → generates modified profile via LLM
2. interrupt() with structured metadata
3. SSE yields → Frontend renders confirmation card
4. User confirms → THEN DB write happens (lines 108-131)
5. Returns to orchestrator
```

**Key point:** DB write happens AFTER user confirmation.

## Why The Last Operation Appears "Blocked"

After the final DB operation completes:
1. Control returns to orchestrator
2. Orchestrator routes to `finalize` node
3. `finalize_node` streams the full LLM response
4. Only when finalize completes does the graph reach `END`

The "blocking" is actually the finalizer's LLM call. The DB write already happened, but there's no explicit event telling the frontend "DB write complete."

### Current Visibility Gap

The frontend knows a DB write happened via:
- Structured metadata in the interrupt (indirect signal)
- Final response mentioning the changes
- Subsequent API calls (`getCoursePath()`, `getProfile()`)

**Missing:** An explicit "database updated" event.

## Potential Solutions

### Option 1: Emit DB Events via `writer` Callback (Recommended)

The `writer` callback is already passed through nodes. Emit custom events after DB writes:

**In `agent_v3.py` (after course path save):**
```python
await self.student_db_service.save_course_path(
    self.tools.cp, self.user_id, pending_approval=out.status == "ask"
)

# Emit DB update event
if writer:
    writer(AIMessage(
        content="",
        additional_kwargs={
            "event_type": "db_updated",
            "entity": "course_path",
            "user_id": self.user_id,
        }
    ))
```

**In `modify_profile.py` (after profile save):**
```python
await student_db_service.save_student_profile(current_profile, user_id)

# Emit DB update event
if writer:
    writer(AIMessage(
        content="",
        additional_kwargs={
            "event_type": "db_updated",
            "entity": "student_profile",
            "user_id": user_id
        }
    ))
```

**Frontend handling:**
```javascript
if (parsed.custom_data?.event_type === 'db_updated') {
    queryClient.invalidateQueries(['coursePath', parsed.custom_data.user_id]);
}
```

**Pros:**
- Uses existing infrastructure
- No new transport needed
- Events are part of same stream (ordering guaranteed)
- Minimal code changes

**Cons:**
- Requires passing `writer` down to `agent_v3.py` through `CoursePathAPIService`

### Option 2: WebSocket (More Complex)

Replace SSE with WebSocket for full duplex communication.

**Pros:**
- True bidirectional communication
- Can push DB updates independently

**Cons:**
- More complex implementation
- Need reconnection logic
- Overkill for current use case

### Option 3: Parallel Notification Channel

Keep SSE for agent stream, add separate channel for DB events.

**Pros:**
- Decouples DB events from agent execution
- Could use Postgres LISTEN/NOTIFY

**Cons:**
- Two streams to manage
- More frontend complexity
- No ordering guarantee between streams

## Implementation Status

**Current:** No explicit DB update events. Frontend infers from context.

**Recommended Next Step:** Implement Option 1 when latency perception becomes a priority.

## Key Files

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| SSE Streaming | `service.py` | 427-585 | `message_generator` |
| Interrupt Handling | `service.py` | 469-499 | Parse interrupts, extract metadata |
| Course Path Ops | `course_path.py` | 26-137 | Execute operations, handle interrupts |
| CP DB Write | `agent_v3.py` | 36-39 | `save_course_path()` call |
| Profile Mods | `modify_profile.py` | 62-139 | Generate, confirm, save profile |
| Finalizer | `finalize.py` | 107-145 | Stream final response |
| Frontend Stream | `api.js` | 84-157 | Parse SSE events |
