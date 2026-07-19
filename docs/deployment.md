# Deployment

WorkflowTwin uses two public Vercel projects. The product project has `apps/web` as its root
directory and deploys a static Vite application. The API project deploys FastAPI separately from
the repository root. This keeps frontend routing independent from API routing and prevents the
product URL from being captured by the Python function.

The multi-stage `Dockerfile.deploy` still provides a supported single-service container option for
environments where serving both applications from FastAPI is useful. A Render Docker blueprint
remains available for that owner-managed deployment model.

- Product and frontend: <https://workflowtwin.vercel.app>
- API and OpenAPI: <https://workflowtwin-api.vercel.app/docs>
- API health: <https://workflowtwin-api.vercel.app/health>

## Vercel deployment

Configure the `workflowtwin` frontend project with:

- Root Directory: `apps/web`
- Framework Preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`
- `VITE_API_BASE_URL`: `https://workflowtwin-api.vercel.app`

`apps/web/vercel.json` records the build contract and rewrites all browser routes to `index.html`,
allowing React Router routes to load directly and survive refreshes. Deploy from the repository root
with `vercel deploy --prod` after linking the `workflowtwin` project.

The `workflowtwin-api` project retains the FastAPI root deployment. Configure
`WORKFLOWTWIN_ENVIRONMENT=production` and
`WORKFLOWTWIN_CORS_ORIGINS=https://workflowtwin.vercel.app`; do not configure a reset token in any
client-visible environment variable. API documentation belongs to this backend project, not the
frontend domain.

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
| `WORKFLOWTWIN_CORS_ORIGINS` | API deployment | Allowed frontend origin |
| `WORKFLOWTWIN_DEMO_RESET_TOKEN` | No | Enables token-protected HTTP reset when set |
| `VITE_API_BASE_URL` | Frontend deployment | Public origin of the separate FastAPI project |

Do not expose the reset token through a `VITE_` variable. Public deployments should leave reset
disabled unless an operator needs it. A process restart always restores the deterministic pilot.

## Free-service limitations

Render free web services sleep after 15 minutes without traffic and can take about one minute to
wake. Their filesystem is ephemeral. This is acceptable because WorkflowTwin does not rely on
runtime files for public state: restarting restores the same fictional dataset and guarded pilot.
The shared in-memory API state is intentionally not production multi-user infrastructure. Vercel
can recycle or run more than one function instance, so state can reset between requests. Approval and
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

Verify the container's `/`, `/workflow`, `/api/v1/demo/overview`, `/api/v1/pilot/summary`, `/docs`,
and human-approved rollback flow before announcing a unified container deployment URL. For Vercel,
verify every frontend route on `workflowtwin.vercel.app` and API health and docs on
`workflowtwin-api.vercel.app` independently.
