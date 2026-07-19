import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return <div className="page-state not-found"><span>404</span><h1>That evidence view does not exist</h1><p>The address is outside the eight supported WorkflowTwin product routes.</p><Link className="button button--secondary" to="/"><ArrowLeft />Return to Overview</Link></div>;
}

