import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface State { error: Error | null }

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State { return { error }; }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("WorkflowTwin page error", { error: error.message, componentStack: info.componentStack });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return <div className="page-state page-state--error" role="alert"><AlertTriangle /><h1>This view could not be rendered</h1><p>The error was contained before it could affect the pilot state.</p><button className="button button--secondary" onClick={() => { this.setState({ error: null }); window.location.reload(); }}><RefreshCw />Reload view</button></div>;
  }
}

