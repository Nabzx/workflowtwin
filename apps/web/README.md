# WorkflowTwin web

Recruiter-facing React client for the fictional Northstar Clinics demonstration.

```bash
npm install
npm run dev
```

Vite proxies `/api`, `/health`, and `/ready` to `http://127.0.0.1:8000` by default.
Set `VITE_API_BASE_URL` only when the API is hosted on a different origin.

