import { AlertTriangle, RefreshCw } from "lucide-react";

export function PageLoading({ label = "Loading evidence" }: { label?: string }) {
  return <div className="page-state" role="status"><span className="spinner" /><p>{label}</p><div className="skeleton-lines" aria-hidden="true"><i /><i /><i /></div></div>;
}

export function PageError({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="page-state page-state--error" role="alert">
      <AlertTriangle aria-hidden="true" /><h2>{navigator.onLine ? "Evidence unavailable" : "You appear to be offline"}</h2><p>{navigator.onLine ? error.message : "Reconnect to load the prepared fictional evidence from the API."}</p>
      <button className="button button--secondary" onClick={retry}><RefreshCw />Retry</button>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><h3>{title}</h3><p>{detail}</p></div>;
}
