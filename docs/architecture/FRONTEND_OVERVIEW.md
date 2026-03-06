
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
| `phase_update` | Updates build phase progress display |
| `node_info` | Status updates from search agent (loading indicators) |
| `coursepath_operations` / `clubpath_operations` | HITL confirmation cards |
| `profile_update` | Profile modification cards with Accept/Reject |

Mode pill state (`agentMode`) is initialized from thread metadata on load and updated in real-time via `mode_change` events during streaming.