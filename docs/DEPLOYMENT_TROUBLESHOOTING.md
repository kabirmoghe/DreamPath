# Deployment Troubleshooting

This document tracks deployment issues encountered when deploying DreamPath to production, specifically focusing on cross-cloud connectivity between Railway (backend) and Fly.io (Weaviate vector database).

## Architecture

**Working Local Setup:**
- Frontend: `localhost:5173` (Vite dev server)
- Backend: `localhost:8080` (FastAPI)
- Weaviate: `dreampath-weaviate.fly.dev` (Fly.io)
  - HTTP API: `https://dreampath-weaviate.fly.dev:443`
  - gRPC: `dreampath-weaviate.fly.dev:50051`

**Target Production Setup:**
- Frontend: Vercel (not yet deployed)
- Backend: Railway (`dreampath-production.up.railway.app`)
- Weaviate: Fly.io (`dreampath-weaviate.fly.dev`)

## Issue: Railway Backend Cannot Connect to Fly.io Weaviate via gRPC

### Background

**What Works:**
- ✅ Local backend → Fly.io Weaviate (both HTTP and gRPC)
- ✅ Railway backend → Fly.io Weaviate HTTP API (port 443)
- ✅ Local machine → Fly.io gRPC port (telnet confirms port 50051 is open)

**What Fails:**
- ❌ Railway backend → Fly.io Weaviate gRPC (port 50051)

### Error Timeline

#### Error 1: IPv6 Network Unreachable (Initial)
```
ipv6:[2a09:8280:1::b5:dc46:0]:50051: connect: Network is unreachable (101)
```

**Configuration:**
- `WEAVIATE_GRPC_HOST=dreampath-weaviate.fly.dev`
- `WEAVIATE_GRPC_PORT=50051`
- `WEAVIATE_GRPC_SECURE=false`

**Cause:**
Railway's DNS resolver prefers IPv6, resolving `dreampath-weaviate.fly.dev` to IPv6 address `2a09:8280:1::b5:dc46:0`. Railway's network cannot route to this IPv6 address.

**Local Machine Difference:**
Local machine resolves to IPv4 (`66.241.125.250`) or has better IPv6 routing, which is why local backend works.

#### Error 2: Connection Reset by Peer (After IPv4 Fix Attempt)
```
ipv4:66.241.125.250:50051: recvmsg:Connection reset by peer
```

**Configuration:**
- `WEAVIATE_GRPC_HOST=66.241.125.250` (forced IPv4)
- `WEAVIATE_GRPC_PORT=50051`
- `WEAVIATE_GRPC_SECURE=false`

**Cause:**
Using the raw IPv4 address bypasses the IPv6 routing issue, but Fly.io's proxy requires the **hostname** for routing decisions. gRPC includes an `:authority` header with the hostname, which Fly.io uses to route to the correct app. When using a raw IP, this routing fails and the connection is reset.

**Key Insight:**
This confirms Fly.io needs the hostname, not just the IP address, even for raw TCP connections on port 50051.

#### Error 3: Validation Error (Port 443 Attempt)
```
Value error, http.port and grpc.port must be different if using the same host
[type=value_error, input_value={'http': ProtocolParams(host='dreampath-weaviate.fly.dev', port=443, secure=True), 'grpc': ProtocolParams(host='dreampath-weaviate.fly.dev', port=443, secure=True)}, input_type=dict]
```

**Configuration:**
- `WEAVIATE_HTTP_HOST=dreampath-weaviate.fly.dev`
- `WEAVIATE_HTTP_PORT=443`
- `WEAVIATE_HTTP_SECURE=true`
- `WEAVIATE_GRPC_HOST=dreampath-weaviate.fly.dev`
- `WEAVIATE_GRPC_PORT=443`
- `WEAVIATE_GRPC_SECURE=true`

**Cause:**
Weaviate's Python client validates that HTTP and gRPC must use different ports when using the same hostname. This is a client-side validation, not a server-side limitation.

**Workaround Consideration:**
Could use different hosts (hostname vs IP) to satisfy the validation, but this hits Error 2 (connection reset with IP).

## Root Cause Analysis

The fundamental issue is a **cross-cloud networking incompatibility**:

1. **Railway's Network:** Cannot route to Fly.io's IPv6 addresses
2. **Fly.io's Proxy:** Requires hostname-based routing, even for raw TCP on port 50051
3. **DNS Resolution:** Railway resolves hostname → IPv6 (fails), using IP directly breaks Fly.io routing

**Why Local Works:**
- Local machine resolves hostname to IPv4 **OR** has functional IPv6 routing to Fly.io
- Same hostname-based routing requirement, but connectivity succeeds

## Weaviate v4 gRPC Requirement

**Important:** Weaviate v4 requires gRPC for all data operations. There is NO HTTP-only fallback mode.

From Weaviate community forum:
> "Weaviate v3 (implying v4) does not support anything outside gRPC for data operations"

Attempted workarounds:
- ❌ Removing gRPC env vars (client still tries to use gRPC, fails)
- ❌ `skip_init_checks=True` (bypasses health check but operations still fail)
- ❌ HTTP-only mode (doesn't exist in v4)

## Fly.io Weaviate Configuration

**fly.toml Services:**
```toml
[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["http", "tls"]

[[services]]
  internal_port = 50051
  protocol = "tcp"

  [[services.ports]]
    port = 50051
    handlers = []  # Raw TCP passthrough for gRPC
```

**Verification:**
- ✅ Fly.io logs show: `"grpc server listening at [::]:50051"`
- ✅ Port scan from local machine: Port 50051 is OPEN
- ✅ Fly.io dashboard: Both services active and healthy

**Conclusion:** Fly.io's Weaviate gRPC configuration is correct. The issue is Railway → Fly.io connectivity.

## Solutions Considered

### Solution 1: Force IPv4 Resolution in Code ❌
**Idea:** Resolve hostname to IPv4 in Python before passing to Weaviate client

**Why It Won't Work:**
Even if we resolve to IPv4 in code, we still need to pass the IP address to the Weaviate client, which triggers Error 2 (connection reset). Fly.io's proxy needs the hostname in the gRPC `:authority` header for routing.

### Solution 2: gRPC over Port 443 with TLS ❌
**Idea:** Multiplex gRPC over HTTPS on port 443 (common cloud pattern)

**Why It Won't Work:**
Weaviate client validation requires HTTP and gRPC to use different ports when using the same hostname. Using different hosts (hostname for HTTP, IP for gRPC) to bypass validation still hits Error 2.

### Solution 3: Deploy Backend to Fly.io ✅ RECOMMENDED
**Approach:** Deploy backend on Fly.io alongside Weaviate

**Advantages:**
- Private networking: Use `dreampath-weaviate.internal:50051` (no internet routing)
- Same platform = no cross-cloud networking issues
- Better performance (internal network)
- Similar cost (~$5/month for 256MB RAM)
- Proven reliability

**Disadvantages:**
- Requires migration from Railway to Fly.io
- New deployment configuration

**Status:** Not yet attempted (recommended next step)

### Solution 4: Weaviate Cloud ✅ ALTERNATIVE
**Approach:** Migrate from self-hosted Fly.io to Weaviate Cloud

**Advantages:**
- Managed service (no infrastructure to maintain)
- Professional support
- Optimized gRPC connectivity
- Likely works with Railway

**Disadvantages:**
- Cost: ~$25/month minimum (vs $5/month for Fly.io)
- Requires data migration
- Ongoing operational cost

**Status:** Not yet attempted (more expensive alternative)

## Recommended Next Steps

### Short-term: Deploy Backend to Fly.io

1. **Create Fly.io app for backend:**
   ```bash
   flyctl launch --name dreampath-backend --no-deploy
   ```

2. **Configure fly.toml:**
   ```toml
   app = "dreampath-backend"
   primary_region = "iad"

   [build]
     dockerfile = "Dockerfile"

   [env]
     PORT = "8080"
     # Add all other env vars (Supabase, API keys, etc.)
     WEAVIATE_HTTP_HOST = "dreampath-weaviate.internal"
     WEAVIATE_HTTP_PORT = "8080"
     WEAVIATE_HTTP_SECURE = "false"
     WEAVIATE_GRPC_HOST = "dreampath-weaviate.internal"
     WEAVIATE_GRPC_PORT = "50051"
     WEAVIATE_GRPC_SECURE = "false"

   [[services]]
     internal_port = 8080
     protocol = "tcp"

     [[services.ports]]
       port = 80
       handlers = ["http"]
       force_https = true

     [[services.ports]]
       port = 443
       handlers = ["http", "tls"]
   ```

3. **Deploy:**
   ```bash
   flyctl deploy
   ```

4. **Test connectivity:**
   - Verify gRPC works with private networking
   - Test chat with course search
   - Update frontend `.env` to point to new backend URL

### Long-term: Consider Weaviate Cloud

If ongoing infrastructure maintenance is not desired, migrate to Weaviate Cloud for professionally managed vector database with better cross-cloud connectivity.

## Environment Variables Reference

### Working Local Configuration
```bash
WEAVIATE_HTTP_HOST=dreampath-weaviate.fly.dev
WEAVIATE_HTTP_PORT=443
WEAVIATE_HTTP_SECURE=true
WEAVIATE_GRPC_HOST=dreampath-weaviate.fly.dev
WEAVIATE_GRPC_PORT=50051
WEAVIATE_GRPC_SECURE=false
```

### Recommended Fly.io Backend Configuration (Private Network)
```bash
WEAVIATE_HTTP_HOST=dreampath-weaviate.internal
WEAVIATE_HTTP_PORT=8080
WEAVIATE_HTTP_SECURE=false
WEAVIATE_GRPC_HOST=dreampath-weaviate.internal
WEAVIATE_GRPC_PORT=50051
WEAVIATE_GRPC_SECURE=false
```

## Technical Details

### Weaviate Client Connection Code
Located in: `backend/dreampath_processing/courses/data_retrieval/weaviate_course_service.py`

```python
self.client = weaviate.connect_to_custom(
    http_host=http_host,
    http_port=http_port,
    http_secure=http_secure,
    grpc_host=grpc_host,
    grpc_port=grpc_port,
    grpc_secure=grpc_secure,
    skip_init_checks=True,  # Skip gRPC health check for cloud deployments
)
```

### DNS Resolution Details

**From Railway:**
```bash
$ nslookup dreampath-weaviate.fly.dev
# Returns: 2a09:8280:1::b5:dc46:0 (IPv6)
```

**From Local Machine:**
```bash
$ host dreampath-weaviate.fly.dev
dreampath-weaviate.fly.dev has address 66.241.125.250 (IPv4)
dreampath-weaviate.fly.dev has IPv6 address 2a09:8280:1::b5:dc46:0
```

**Key Difference:** Local resolver returns both but likely prefers IPv4, Railway prefers IPv6.

## Related Files

- `backend/dreampath_processing/courses/data_retrieval/weaviate_course_service.py` - Connection configuration
- `fly.toml` - Fly.io Weaviate configuration
- `Dockerfile` - Railway backend containerization
- `DEPLOYMENT_STATUS.md` - Overall deployment progress
- `.env` - Environment variables

## Status: BLOCKED

**Current State:** Railway backend cannot connect to Fly.io Weaviate via gRPC due to cross-cloud networking incompatibility.

**Blocking Issue:** Railway's IPv6 DNS resolution + inability to route to Fly.io's IPv6 addresses + Fly.io's hostname-based routing requirement = deadlock.

**Next Action:** Deploy backend to Fly.io for private networking (Solution 3).