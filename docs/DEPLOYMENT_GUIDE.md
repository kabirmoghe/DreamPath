# DreamPath Deployment Guide

Complete guide for deploying and maintaining the DreamPath application in production.

**Last Updated:** December 2, 2025

---

## Production Architecture

### Services & URLs

| Service | Platform | URL | Purpose |
|---------|----------|-----|---------|
| **Frontend** | Vercel | `https://dreampath.live` | React + Vite UI |
| **Backend** | Fly.io | `https://dreampath-backend.fly.dev` | FastAPI service |
| **Weaviate** | Fly.io | `dreampath-weaviate.internal:50051` | Vector database (private network) |
| **PostgreSQL** | Supabase | `aws-0-us-east-2.pooler.supabase.com:6543` | User data & checkpoints |

### Cost Breakdown

- **Fly.io (Backend):** ~$5/month (1GB RAM)
- **Fly.io (Weaviate):** ~$5/month (1GB RAM)
- **Vercel (Frontend):** $0 (Hobby tier)
- **Supabase (PostgreSQL):** $0 (Free tier)
- **Custom Domain (dreampath.live):** ~$24/year (~$2/month)
- **Total:** ~$12/month

---

## Quick Deployment Commands

### Backend (Fly.io)

**Automatic Deployment (GitHub Actions):**
Backend auto-deploys on push to `dev` branch via GitHub Actions.

**Manual Deployment:**
```bash
# Deploy backend
flyctl deploy -a dreampath-backend

# View logs
flyctl logs -a dreampath-backend

# SSH into machine
flyctl ssh console -a dreampath-backend

# Set secrets
flyctl secrets set -a dreampath-backend KEY=value
```

### Frontend (Vercel)

Vercel auto-deploys on push to `dev` branch (configured in Vercel dashboard).

**Manual redeploy:**
- Vercel Dashboard → Deployments → Redeploy

### Weaviate (Fly.io)

```bash
# Check status
flyctl status -a dreampath-weaviate

# View logs
flyctl logs -a dreampath-weaviate

# Access metrics
open https://dreampath-weaviate.fly.dev/v1/.well-known/ready
```

---

## CI/CD Setup (GitHub Actions)

### Overview

The backend automatically deploys to Fly.io when you push to the `dev` branch via GitHub Actions. This mirrors the frontend's Vercel auto-deployment workflow.

### Initial Setup (One-Time)

**1. Add Fly.io API Token to GitHub Secrets:**

The token has already been generated:
```
fm2_lJPECAAAAAAAC2IUxBBB358djnWq3BtMnEOPDf+EwrVodHRwczovL2FwaS5mbHkuaW8vdjGUAJLOABTdnB8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDzLIck3r82l9km5aOsw6wSYZZOWuke+DJQ+ZEp8hma0xIH6E/UqvV/z/yxC73As1PeZw13CDT0I6UgM8ubETjgxvbB9ZEYwWSA38pNJ+fV67MTbjwXlDcElGgzPUuHYYWMzh2rInqVg6+8kt0cvVxIQbHmtP4gN9gKntNpLAiDkV/PZQmQAWEXFDMHPoMQg+AindVCIf4QqclKVN2wxVV7sLtIGcU0+HpTEnUVwKgk=,fm2_lJPETjgxvbB9ZEYwWSA38pNJ+fV67MTbjwXlDcElGgzPUuHYYWMzh2rInqVg6+8kt0cvVxIQbHmtP4gN9gKntNpLAiDkV/PZQmQAWEXFDMHPoMQQnvScsPRbJ/TL1sUpf0u898O5aHR0cHM6Ly9hcGkuZmx5LmlvL2FhYS92MZYEks5pL6fWzmkvqkwXzgAUCoYKkc4AFAqGxCAVXmMEJL0TxjWHLgSTP/EyTRnSZVV3qu2cTyjpqePfxg==,fo1_ZskUdkGskUtgOjOCTQMAsaziBZR2xrJCGSKJg8_03tQ
```

To add it to GitHub:
1. Go to your GitHub repo: `https://github.com/kabirmoghe/dreampath/settings/secrets/actions`
2. Click **"New repository secret"**
3. Name: `FLY_API_TOKEN`
4. Value: (paste the token above)
5. Click **"Add secret"**

**2. Workflow File:**

The workflow is already created at `.github/workflows/fly-deploy.yml`:
- Triggers on push to `dev` branch
- Can also be manually triggered from GitHub Actions tab
- Builds and deploys to Fly.io using `flyctl deploy --remote-only`

### Usage

**Automatic Deployment:**
```bash
git add .
git commit -m "Your commit message"
git push origin dev  # Triggers auto-deployment
```

**Monitor Deployment:**
- GitHub: Actions tab → "Deploy to Fly.io" workflow
- Fly.io: `flyctl logs -a dreampath-backend`

**Manual Trigger:**
- GitHub → Actions → "Deploy to Fly.io" → "Run workflow"

### Benefits

- Same workflow as frontend (push to `dev` → auto-deploy)
- No need to run `flyctl deploy` locally
- Deployment logs visible in GitHub Actions
- Consistent deployment environment (GitHub runners)

---

## Environment Variables

### Backend (Fly.io Secrets)

Required secrets (set via `flyctl secrets set`):

```bash
# LLM API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...  # Optional

# PostgreSQL (Supabase)
POSTGRES_USER=postgres.isxmguuvzmgeizitgbuk
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=aws-0-us-east-2.pooler.supabase.com
POSTGRES_PORT=6543
POSTGRES_DB=postgres

# Optional: Observability
LANGCHAIN_API_KEY=...
LANGSMITH_PROJECT=DreamPath  # TODO: Set this in production
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

**Non-secret env vars** (set in `fly.toml`):
- `WEAVIATE_HTTP_HOST=dreampath-weaviate.internal`
- `WEAVIATE_GRPC_HOST=dreampath-weaviate.internal`
- `DATABASE_TYPE=postgres`

### Frontend (Vercel)

Set in Vercel Dashboard → Settings → Environment Variables:

```bash
VITE_SUPABASE_URL=https://isxmguuvzmgeizitgbuk.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbG...
VITE_API_URL=https://dreampath-backend.fly.dev
```

### Weaviate (Fly.io Secrets)

```bash
# Only secret needed
OPENAI_APIKEY=sk-proj-...
```

---

## Critical Configuration Details

### 1. Supabase PostgreSQL Connection

**IMPORTANT:** Must use **transaction pooler** endpoint with prepared statements disabled.

**Connection String Format:**
```
postgres.isxmguuvzmgeizitgbuk@aws-0-us-east-2.pooler.supabase.com:6543/postgres
```

**Why:** Supabase's pgbouncer in transaction mode doesn't support prepared statements.

**Code Requirements:**
- `backend/dreampath_processing/database/connection.py` → `statement_cache_size=0`
- `backend/memory/postgres.py` (saver) → `prepare_threshold=None`
- `backend/memory/postgres.py` (store) → `prepare_threshold=None`

### 2. Fly.io Private Networking

**Backend → Weaviate uses `.internal` addresses:**
- HTTP: `dreampath-weaviate.internal:8080`
- gRPC: `dreampath-weaviate.internal:50051`

**Why this matters:**
- Private networking avoids cross-cloud gRPC issues (IPv6 routing failures)
- No public internet routing = better security and performance
- Works because both services are on Fly.io in same organization

### 3. Supabase Authentication URLs

**Configured in:** Supabase Dashboard → Authentication → URL Configuration

**Site URL:**
```
https://dreampath.live
```

**Redirect URLs:**
```
http://localhost:5173/onboarding
http://localhost:5173/dashboard
https://dreampath.live/
https://dreampath.live/**
https://dreampath-eight.vercel.app/**
```

**Note:** Keep the old Vercel URL in redirects during transition period.

**Why the wildcard (`**`):** Allows email confirmations to redirect to any path (e.g., `/dashboard`, `/onboarding`).

### 4. Vercel SPA Routing

**Configuration:** `frontend/vercel.json`

```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

**Why:** React Router handles routing client-side. Without this, direct URL access or page refreshes result in 404 errors.

---

## Deployment History & Lessons Learned

### Why Fly.io (Not Railway or Render)?

**Initial Attempts:**
1. **Render:** Failed due to 512MB RAM limit (insufficient for LangGraph + Weaviate client)
2. **Railway:** Failed due to cross-cloud IPv6 networking issue with Fly.io Weaviate

**Railway Issue Details:**
- Railway's DNS resolver prefers IPv6 → resolves `dreampath-weaviate.fly.dev` to IPv6 address
- Railway's network cannot route to Fly.io's IPv6 addresses
- Using raw IPv4 address broke Fly.io's hostname-based proxy routing
- **Solution:** Deploy backend to Fly.io for private networking (`.internal` addresses)

**Why Both on Fly.io:**
- Private networking eliminates cross-cloud issues
- Cheaper than alternatives (~$10/month total vs ~$30/month for AWS)
- Simple deployment workflow
- Proven reliability for vector databases

### Weaviate v4 Requirements

**Critical:** Weaviate v4 requires gRPC for all data operations. There is NO HTTP-only fallback.

**Attempted Workarounds:**
- ❌ Removing gRPC config → Client still tries gRPC, fails
- ❌ `skip_init_checks=True` → Bypasses health check but operations still fail
- ❌ HTTP-only mode → Doesn't exist in v4

**Correct Solution:** Ensure gRPC port 50051 is accessible (works via Fly.io private network).

---

## Common Issues & Solutions

### Issue: Backend Not Starting

**Symptoms:**
- Health checks failing
- Port 8080 not responding

**Check:**
```bash
flyctl logs -a dreampath-backend
```

**Common Causes:**
1. **Missing API keys** → Set secrets via `flyctl secrets set`
2. **Invalid env var format** → Check for comments in values (e.g., `6543 # comment` breaks parsing)
3. **Import errors** → Check for missing dependencies in `pyproject.toml`

### Issue: Course Search Not Working

**Symptoms:**
- Chat works but course search returns no results or errors

**Check Weaviate connectivity:**
```bash
# From backend machine
flyctl ssh console -a dreampath-backend
# Inside machine:
curl http://dreampath-weaviate.internal:8080/v1/meta
```

**Common Causes:**
1. **Wrong env vars** → Verify `WEAVIATE_GRPC_HOST` uses `.internal` address
2. **Weaviate not running** → Check `flyctl status -a dreampath-weaviate`
3. **Missing OpenAI key** → Weaviate needs it for embeddings

### Issue: Frontend 404 on Refresh

**Cause:** Missing `vercel.json` or Vercel hasn't picked it up

**Solution:**
1. Verify `frontend/vercel.json` exists and is committed
2. Redeploy in Vercel dashboard

### Issue: Email Confirmations Link to Localhost

**Cause:** Supabase Site URL is set to localhost

**Solution:**
- Supabase Dashboard → Authentication → URL Configuration
- Set Site URL to `https://dreampath-eight.vercel.app`

---

## Monitoring & Debugging

### Health Checks

**Backend:**
```bash
curl https://dreampath-backend.fly.dev/health
# Expected: {"status":"ok"}
```

**Weaviate:**
```bash
curl https://dreampath-weaviate.fly.dev/v1/.well-known/ready
# Expected: {"ready":true}
```

### View Logs

```bash
# Backend
flyctl logs -a dreampath-backend

# Weaviate
flyctl logs -a dreampath-weaviate

# Frontend (in Vercel dashboard)
Vercel → Project → Deployments → View Function Logs
```

### Database Queries

**Supabase Dashboard:**
- SQL Editor → Run queries directly
- Table Editor → View/edit data
- Database → Manage schema

**From Backend:**
```bash
flyctl ssh console -a dreampath-backend
# Inside machine:
python
>>> from dreampath_processing.database.student_service import StudentDatabaseService
>>> service = StudentDatabaseService()
>>> # Run queries...
```

---

## Security Considerations

### API Keys Rotation

**When to rotate:**
- Keys exposed in logs or error messages
- Regular rotation (every 90 days)
- After team member leaves

**How to rotate:**
1. Generate new key from provider (OpenAI, Anthropic, etc.)
2. Update Fly.io secrets: `flyctl secrets set -a dreampath-backend OPENAI_API_KEY=new-key`
3. App automatically restarts with new key
4. Revoke old key in provider dashboard

### Exposed Secrets

**Known exposures (from deployment):**
- OpenAI API key visible in error logs during initial deployment
- **Action Required:** Rotate OpenAI API key

**Prevention:**
- Never commit `.env` files
- Use `flyctl secrets` for sensitive values
- Review logs before sharing/posting

### CORS Configuration

**Current:** `backend/service/service.py` allows:
- `localhost:5173` (dev)
- `https://dreampath.live` (production)
- `https://www.dreampath.live` (production www)
- `https://*.vercel.app` (all Vercel deployments, for staging/preview)

---

## Future Improvements

### Infrastructure

- [x] **CI/CD for Backend:** GitHub Actions to auto-deploy Fly.io on push ✅
- [x] **Custom Domain:** dreampath.live configured on Vercel and Cloudflare ✅
- [ ] **Monitoring:** Set up UptimeRobot or Fly.io metrics alerts
- [ ] **Staging Environment:** Deploy separate staging instances for testing

### Security

- [ ] **Rate Limiting:** Add rate limiting to API endpoints
- [ ] **API Key Rotation:** Implement automatic rotation schedule
- [ ] **Supabase Email Verification:** Enable email verification requirement
- [ ] **Content Security Policy:** Add CSP headers to frontend

### Performance

- [ ] **CDN for Frontend:** Vercel provides this by default, verify edge caching
- [ ] **Database Indexing:** Review Supabase query performance
- [ ] **Weaviate Optimization:** Tune vector search parameters
- [ ] **Backend Caching:** Consider Redis for frequently accessed data

---

## Support & Resources

### Documentation
- **Fly.io Docs:** https://fly.io/docs/
- **Vercel Docs:** https://vercel.com/docs
- **Supabase Docs:** https://supabase.com/docs
- **Weaviate Docs:** https://weaviate.io/developers/weaviate

### Project-Specific Guides
- `CLAUDE.md` - Instructions for Claude Code (development)
- `DEPLOYMENT_TROUBLESHOOTING.md` - Detailed Railway gRPC issue analysis
- `README.md` - Project overview and local development setup

### Quick Reference

**Fly.io Pricing:** https://fly.io/docs/about/pricing/
**Vercel Limits:** https://vercel.com/docs/limits/overview
**Supabase Limits:** https://supabase.com/docs/guides/platform/org-based-billing#free-plan

---

## Appendix: File Structure

### Configuration Files

```
dreampath/
├── fly.toml                    # Backend Fly.io config
├── fly.weaviate.toml           # Weaviate Fly.io config
├── Dockerfile                  # Backend container
├── Dockerfile.weaviate         # Weaviate container
├── frontend/
│   ├── vercel.json            # Vercel SPA routing
│   └── .env                   # Frontend env vars (not committed)
└── backend/
    ├── .env                   # Backend env vars (not committed)
    └── run_service.py         # FastAPI entrypoint
```

### Key Directories

- `backend/dreampath_processing/` - Core DreamPath logic
- `backend/agents/` - Agent service toolkit integration
- `backend/service/` - FastAPI service layer
- `backend/memory/` - LangGraph checkpointing
- `frontend/src/` - React components and routing

---

**End of Deployment Guide**

*For development setup and local testing, see `CLAUDE.md` and `README.md`.*
