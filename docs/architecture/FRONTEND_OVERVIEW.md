
# Frontend — Deep Dive

> For stack, key components, and colors, see the **Frontend Architecture** section in [`CLAUDE.md`](../../CLAUDE.md). This doc covers the full component tree and data flow details.

## Entry Point & Routing

- **main.jsx** → imports `App.jsx`
- **App.jsx** — `AuthProvider` context + `@tanstack/react-query` for data fetching/caching
  - Routes: `/` (LandingPage), `/login`, `/signup`, `/onboarding`, `/dashboard`, `/courses`, `/clubs`
  - Protected routes require authentication via `ProtectedRoute` component

## Components

| Component | Purpose |
|-----------|---------|
| `Dashboard.jsx` | Main dashboard with profile and chat integration |
| `Courses.jsx` | Course path visualization from PostgreSQL with detail modal (alignment, metrics, prereqs) |
| `Clubs.jsx` | Club path visualization with redesigned detail modal (alignment badges, status section, at-a-glance grid, 2x2 mini tiles) |
| `Login.jsx` / `Signup.jsx` | Authentication using AuthContext |
| `Onboarding.jsx` | Initial profile setup flow |
| `LandingPage.jsx` | Public landing page |
| `ProtectedRoute.jsx` | Authentication guard for protected routes |
| `CoursePathOperations.jsx` | Course path modification UI with confirmation cards (Confirm/Reject + note) |
| `ClubPathOperations.jsx` | Club path modification UI with confirmation cards (Confirm/Reject); supports add/remove/edit with per-field detail rendering |
| `ProfileUpdate.jsx` | Profile modification UI card with Accept/Reject confirmation and status footer |
| `InitLoadingOverlay.jsx` | Onboarding loading overlay with phase stepper timeline and node status |
| `OverlayTest.jsx` | Testing route for UI components |

## Authentication

**AuthContext.jsx** (`frontend/src/contexts/`)
- Supabase-based authentication with JWT
- Provides: `user`, `session`, `signIn()`, `signUp()`, `signOut()`

## API Client

**api.js** (`frontend/src/lib/`)
- Methods: `getProfile()`, `updateProfile()`, `getCoursePath()`, streaming chat, etc.
- Local dev: `http://localhost:8080` / Production: `https://dreampath-backend.fly.dev`
- Includes Supabase client for authentication

## Styling

- `index.css` → imports `styles/base.css`, `styles/components.css`, `styles/coursePath.css`
- Background gradients use light purple/blue tones

## Data Flow

1. User authenticates via `Login`/`Signup` → `AuthContext` manages Supabase session
2. Protected routes check `user` from `AuthContext`
3. Components use React Query to fetch data from FastAPI backend
4. Chat interface communicates with agent service via streaming API
5. Agent updates trigger React Query cache invalidation → UI refreshes

## SSE Streaming Events (ChatWindow.jsx)

During streaming, `ChatWindow.jsx` processes custom SSE events from `additional_kwargs`:

| Event Type | Handler |
|-----------|---------|
| `mode_change` | Updates mode pill immediately via `flushSync()` (`setAgentMode`); clears `buildPhases` on advise transition |
| `phase_update` | Updates build phase stepper (mini stepper above input in ChatWindow; full stepper in InitLoadingOverlay during onboarding) |
| `node_info` | Status updates from search agent (loading indicators) |
| `coursepath_operations` / `clubpath_operations` | HITL confirmation cards |
| `profile_update` | Profile modification cards with Accept/Reject |

Mode pill state (`agentMode`) is initialized from thread metadata on load and updated in real-time via `mode_change` events during streaming.

### Build Phase Stepper

Two implementations of the phase stepper exist:

1. **ChatWindow mini stepper** (`chat-phase-stepper` in `ChatWindow.css`) — Compact 36px-tall horizontal stepper above the textarea. 10px nodes with progress track. Appears only during build mode. Disappears on mode transition back to advise.

2. **InitLoadingOverlay stepper** (`phase-stepper` in `InitLoadingOverlay.css`) — Full-width stepper in the onboarding loading overlay. 16px nodes with labels. `Onboarding.jsx` passes `buildPhases` state from `phase_update` SSE events.

Both share the same `PHASE_LABELS` map (Plan, Profile, Courses, Activities, Curate, Build, Reflect, Refine, Finish) and compute progress fill from completed/active phase indices.