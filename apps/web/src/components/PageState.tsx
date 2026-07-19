import { AlertTriangle, RefreshCw } from "lucide-react";

export function PageLoading({ label = "Loading evidence" }: { label?: string }) {
  return <div className="page-state" role="status"><span className="spinner" /><p>{label}</p></div>;
}

export function PageError({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="page-state page-state--error" role="alert">
      <AlertTriangle aria-hidden="true" /><h2>Evidence unavailable</h2><p>{error.message}</p>
      <button className="button button--secondary" onClick={retry}><RefreshCw />Retry</button>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><h3>{title}</h3><p>{detail}</p></div>;
}

