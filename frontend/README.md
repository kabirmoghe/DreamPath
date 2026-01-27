# Frontend

React + Vite app for DreamPath UI.

## Structure

```
frontend/
├── index.html                  # HTML entry point
├── vite.config.js              # Vite configuration
├── vercel.json                 # Vercel deployment config
│
└── src/
    ├── main.jsx                # React entry point
    ├── App.jsx                 # Router and providers
    │
    ├── components/
    │   ├── Dashboard.jsx       # Main dashboard with chat
    │   ├── Courses.jsx         # Course path visualization
    │   ├── Onboarding.jsx      # Profile setup flow
    │   ├── ChatWindow.jsx      # Chat interface
    │   ├── CoursePathOperations.jsx  # Course modification UI
    │   ├── LandingPage.jsx     # Public landing page
    │   ├── ProtectedRoute.jsx  # Auth guard
    │   ├── Auth/
    │   │   ├── Login.jsx
    │   │   └── Signup.jsx
    │   └── icons/              # SVG icon components
    │
    ├── contexts/
    │   └── AuthContext.jsx     # Supabase auth state
    │
    ├── lib/
    │   └── api.js              # Backend API client
    │
    └── styles/
        ├── base.css            # Global styles, CSS variables
        ├── components.css      # Reusable component styles
        ├── coursePath.css      # Course visualization
        └── ChatWindow.css      # Chat UI styles
```

## Quick Start

```bash
npm install
npm run dev
# App at http://localhost:5173
```

## Build

```bash
npm run build
# Output in dist/
```
