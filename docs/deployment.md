# Deployment

WorkflowTwin is packaged as one public web service for the portfolio demonstration. The
multi-stage `Dockerfile.deploy` builds the React application, installs the Python service, and
serves both from FastAPI on one origin. This avoids CORS configuration drift and keeps the
fictional pilot state in the same process as its API.

The verified portfolio deployment uses Vercel's Python runtime because its CLI can deploy the
local release without changing Git history or pushing the repository. `vercel.json` builds the
SPA and routes every request to one FastAPI function. The function serves client routes and API
routes from the same origin. A Render Docker blueprint remains available for an owner-managed
container deployment after the release is pushed.

- Product and frontend: <https://workflowtwin.vercel.app>
- API and OpenAPI: <https://workflowtwin.vercel.app/docs>
- Health: <https://workflowtwin.vercel.app/health>

## Vercel deployment

`pyproject.toml` declares the ASGI entry point. Configure
`WORKFLOWTWIN_WEB_DIST_PATH=apps/web/dist` and `WORKFLOWTWIN_ENVIRONMENT=production` in the
Vercel project, then deploy with `vercel deploy --prod`. Do not configure a reset token in any
client-visible environment variable.

The deployed Python function is approximately 431 MB uncompressed, below Vercel's current 500 MB
limit but close enough to constrain future dependency growth. Production verification covers the
recruiter walkthrough, bounded draft edit, atomic approval, fictional task creation, rollback,
forbidden clinical content, health, system status, and disabled anonymous reset.

## Render blueprint

`render.yaml` defines a free Render Docker web service with `/ready` as its health check. After
the repository owner pushes the release commits, create a Blueprint from the repository in the
Render dashboard. Render assigns the service a TLS-enabled `onrender.com` URL.

No database is required for the public prepared demo. Analytics artefacts are immutable package
data and pilot mutations use resettable in-memory state. PostgreSQL remains part of the supported
local and validation stack.

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `PORT` | Set by Render | Public HTTP listener |
| `WORKFLOWTWIN_ENVIRONMENT` | Yes | Set to `production` |
| `WORKFLOWTWIN_WEB_DIST_PATH` | Image default | Built SPA directory |
| `WORKFLOWTWIN_DEMO_RESET_TOKEN` | No | Enables token-protected HTTP reset when set |

Do not expose the reset token through a `VITE_` variable. Public deployments should leave reset
disabled unless an operator needs it. A process restart always restores the deterministic pilot.

## Free-service limitations

Render free web services sleep after 15 minutes without traffic and can take about one minute to
wake. Their filesystem is ephemeral. This is acceptable because WorkflowTwin does not rely on
runtime files for public state: restarting restores the same fictional dataset and guarded pilot.
The shared in-memory state is intentionally not production multi-user infrastructure. Vercel can
recycle or run more than one function instance, so state can reset between requests. Approval and
rollback requests carry only bounded fictional state needed to replay and verify deterministic
identifiers atomically when a fresh instance handles the request. The pilot is best viewed as a
short demonstration flow; audit views can return to their prepared state after instance recycling.

The public service cannot send messages, mutate referral events, select arbitrary recipients, or
perform clinical decisions. Draft fields and identifiers remain bounded by API contracts. No
visitor identity or personal information is collected.

## Local production-image check

```bash
docker build -f Dockerfile.deploy -t workflowtwin-deploy .
docker run --rm -p 10000:10000 \
  -e WORKFLOWTWIN_ENVIRONMENT=production workflowtwin-deploy
curl --fail http://localhost:10000/ready
```

Verify `/`, `/workflow`, `/api/v1/demo/overview`, `/api/v1/pilot/summary`, `/docs`, and the
human-approved rollback flow before announcing a deployment URL.
