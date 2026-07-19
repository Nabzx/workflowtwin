import { Background, Controls, MarkerType, MiniMap, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { RotateCcw, X } from "lucide-react";
import { useMemo, useState } from "react";

import "@xyflow/react/dist/style.css";
import { useWorkflow } from "../api/queries";
import type { Workflow } from "../api/schemas";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatMetric, shortId } from "../lib/format";

type ViewMode = "frequency" | "performance";
type Selection = { kind: "node"; value: Workflow["nodes"][number] } | { kind: "edge"; value: Workflow["edges"][number] } | null;

export function WorkflowPage() {
  const query = useWorkflow();
  const [mode, setMode] = useState<ViewMode>("performance");
  const [serviceLine, setServiceLine] = useState("All");
  const [source, setSource] = useState("All");
  const [selection, setSelection] = useState<Selection>(null);
  const [variantId, setVariantId] = useState<string | null>(null);

  if (query.isPending) return <PageLoading label="Reconstructing the referral workflow" />;
  if (query.error) return <PageError error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;

  return (
    <div className="page-container workflow-page">
      <PageHeader eyebrow="Observed process · 1,000 fictional referrals" title="Referral workflow" description="Compare intended and observed behaviour, then inspect the transitions where waiting, handoffs, and rework accumulate." />
      <FictionalNotice compact />
      <section className="workflow-summary" aria-label="Process complexity">{data.complexity.map((metric) => <MetricCard key={metric.key} label={metric.label} value={formatMetric(metric.value, metric.unit)} unit={metric.unit} />)}</section>
      <section className="process-workspace" aria-labelledby="process-map-title">
        <div className="process-toolbar">
          <div><p className="eyebrow">Discovered process</p><h2 id="process-map-title">Observed referral paths</h2></div>
          <div className="toolbar-controls">
            <label>Service line<select value={serviceLine} onChange={(event) => setServiceLine(event.target.value)}>{data.filters.service_lines.map((option) => <option key={option}>{option}</option>)}</select></label>
            <label>Referral source<select value={source} onChange={(event) => setSource(event.target.value)}>{data.filters.referral_sources.map((option) => <option key={option}>{option}</option>)}</select></label>
            <div className="segmented-control" aria-label="Graph display mode">{(["frequency", "performance"] as const).map((item) => <button key={item} aria-pressed={mode === item} onClick={() => setMode(item)}>{item === "frequency" ? "Frequency" : "Performance"}</button>)}</div>
          </div>
        </div>
        {(serviceLine !== "All" || source !== "All") && <p className="filter-note" role="status">Presentation graph remains the overall process; cohort filters frame the inspection context: {serviceLine}, {source}.</p>}
        <ProcessMap data={data} mode={mode} onSelection={setSelection} />
        <GraphLegend mode={mode} />
      </section>

      {selection && <SelectionPanel selection={selection} onClose={() => setSelection(null)} />}

      <section className="conformance-section" aria-labelledby="conformance-title"><SectionHeading eyebrow="Conformance" title="Strict rules versus governed reality" description="The governed model recognises legitimate retries and terminal outcomes instead of treating every exception as failure." /><div className="conformance-grid" id="conformance-title">{[data.strict, data.governed].map((item) => <article key={item.model}><div><span>{item.model === data.governed.model ? "Governed model" : "Strict model"}</span><StatusBadge tone={item.model === data.governed.model ? "success" : "warning"}>{`${formatMetric(item.fully_conforming_rate * 100, "%")}% fully conforming`}</StatusBadge></div><strong>{formatMetric(item.average_fitness * 100, "%")}%</strong><small>average fitness</small><p>{item.interpretation}</p></article>)}</div></section>

      <section aria-labelledby="variants-title"><SectionHeading eyebrow="Top variants" title="Common paths through the workflow" description="Select a row to expose the complete activity sequence." /><div className="data-table-wrap"><table className="data-table" id="variants-title"><thead><tr><th>Variant</th><th>Cases</th><th>Median duration</th><th>Outcome</th><th><span className="sr-only">Inspect</span></th></tr></thead><tbody>{data.variants.map((variant) => <tr key={variant.id} className={variantId === variant.id ? "is-selected" : ""}><td><code>{shortId(variant.id)}</code></td><td>{variant.case_count}</td><td>{variant.median_duration_hours.toFixed(1)} hours</td><td><StatusBadge tone={variant.outcome === "completed" ? "success" : "neutral"}>{variant.outcome}</StatusBadge></td><td><button className="text-button" onClick={() => setVariantId(variantId === variant.id ? null : variant.id)}>{variantId === variant.id ? "Hide path" : "Inspect path"}</button></td></tr>)}</tbody></table></div>{variantId && <VariantPath activities={data.variants.find((item) => item.id === variantId)?.activities ?? []} />}</section>
    </div>
  );
}

function ProcessMap({ data, mode, onSelection }: { data: Workflow; mode: ViewMode; onSelection: (selection: Selection) => void }) {
  const { nodes, edges } = useMemo(() => {
    const graphNodes: Node[] = data.nodes.map((item) => ({ id: item.id, position: { x: item.x, y: item.y }, data: { label: <div className="process-node"><span>{item.stage}</span><strong>{item.label}</strong><small>{item.frequency.toLocaleString("en-GB")} events</small></div> }, className: `flow-node ${item.id === "checked" ? "flow-node--focus" : ""}`, sourcePosition: Position.Right, targetPosition: Position.Left }));
    const graphEdges: Edge[] = data.edges.map((item) => ({ id: item.id, source: item.source, target: item.target, label: mode === "frequency" ? item.frequency.toLocaleString("en-GB") : `${item.median_delay_hours.toFixed(1)}h`, animated: item.rework, markerEnd: { type: MarkerType.ArrowClosed }, className: `${item.bottleneck ? "flow-edge--bottleneck" : ""} ${item.handoff ? "flow-edge--handoff" : ""}`, style: { strokeWidth: mode === "frequency" ? Math.max(1.5, Math.min(5, item.frequency / 240)) : item.bottleneck ? 3 : 1.5 } }));
    return { nodes: graphNodes, edges: graphEdges };
  }, [data, mode]);
  return <div className="process-canvas" aria-label={`Interactive process graph in ${mode} mode`}><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.35} maxZoom={1.6} nodesDraggable={false} nodesConnectable={false} onNodeClick={(_, node) => { const value = data.nodes.find((item) => item.id === node.id); if (value) onSelection({ kind: "node", value }); }} onEdgeClick={(_, edge) => { const value = data.edges.find((item) => item.id === edge.id); if (value) onSelection({ kind: "edge", value }); }}><Background gap={24} size={1} /><Controls showInteractive={false} /><MiniMap pannable zoomable nodeColor="var(--accent)" /></ReactFlow></div>;
}

function GraphLegend({ mode }: { mode: ViewMode }) {
  return <div className="graph-legend"><span><i className="legend-line legend-line--bottleneck" /> Bottleneck</span><span><i className="legend-line legend-line--handoff" /> Handoff</span><span><RotateCcw /> Rework loop</span><span>{mode === "frequency" ? "Line width = transition volume" : "Labels = median elapsed hours"}</span></div>;
}

function SelectionPanel({ selection, onClose }: { selection: NonNullable<Selection>; onClose: () => void }) {
  return <aside className="selection-panel" aria-live="polite"><button className="icon-button" onClick={onClose} aria-label="Close details"><X /></button>{selection.kind === "node" ? <><p className="eyebrow">Activity</p><h2>{selection.value.label}</h2><dl><div><dt>Event frequency</dt><dd>{selection.value.frequency.toLocaleString("en-GB")}</dd></div><div><dt>Manual work rate</dt><dd>{(selection.value.manual_work_rate * 100).toFixed(0)}%</dd></div><div><dt>Stage</dt><dd>{selection.value.stage}</dd></div></dl></> : <><p className="eyebrow">Transition</p><h2>{selection.value.source} → {selection.value.target}</h2><dl><div><dt>Frequency</dt><dd>{selection.value.frequency.toLocaleString("en-GB")}</dd></div><div><dt>Median delay</dt><dd>{selection.value.median_delay_hours.toFixed(1)} hours</dd></div><div><dt>Markers</dt><dd>{[selection.value.bottleneck && "bottleneck", selection.value.handoff && "handoff", selection.value.rework && "rework"].filter(Boolean).join(", ") || "none"}</dd></div></dl></>}</aside>;
}

function VariantPath({ activities }: { activities: string[] }) {
  return <div className="variant-path" aria-label="Selected variant activity sequence">{activities.map((activity, index) => <span key={`${activity}-${index}`}><b>{activity}</b>{index < activities.length - 1 && <span aria-hidden="true">→</span>}</span>)}</div>;
}
