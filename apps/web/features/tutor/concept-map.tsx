"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { Download, List, Network } from "lucide-react";
import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Notice } from "@/components/ui/feedback";
import { api, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import styles from "./concept-map.module.css";
import { connectionText, edgesOf, layoutGraph, nodeAriaLabel, NODE_H, NODE_W } from "./graph-layout";
import { IdlePreview } from "./library";
import { PassageList } from "./passages";
import { Announce, BusyIcon, PendingPanel, useToolRequest } from "./pending";
import { useLiveTheme } from "./use-live-theme";

type View = "map" | "list";

export function ConceptMap() {
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<View>("map");
  const theme = useLiveTheme();
  const input = useRef<HTMLInputElement>(null);

  const { run: map, cancel, cancelled, error } = useToolRequest(
    async (t: string, signal: AbortSignal) => unwrap(await api.http.POST("/api/v1/concept-map", { body: { topic: t }, signal })),
    { onMutate: () => setSelected(null) },
  );
  const data = map.data;

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[] };
    const positioned = layoutGraph(data.nodes, data.edges);
    const touching = new Set<string>();
    if (selected) for (const e of data.edges) if (e.from === selected || e.to === selected) touching.add(e.from).add(e.to);
    const dimmed = (id: string) => touching.size > 0 && !touching.has(id);
    const flowNodes: Node[] = positioned.map((n) => ({
      id: n.id,
      position: { x: n.x, y: n.y },
      data: { label: n.label },
      ariaLabel: nodeAriaLabel(n, data.edges),
      // Fixed dimensions: these node objects are rebuilt whenever the selection changes, and React Flow
      // hides a rebuilt node until it is measured again, which a node whose size did not change never is.
      width: NODE_W,
      height: NODE_H,
      selected: n.id === selected,
      style: {
        width: NODE_W,
        height: NODE_H,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        fontSize: 13,
        fontWeight: n.id === selected ? 600 : 500,
        borderRadius: 10,
        border: `${n.id === selected ? 2 : 1}px ${dimmed(n.id) ? "dashed" : "solid"} ${n.id === selected ? "var(--color-accent-2)" : "var(--color-border)"}`,
        background: "var(--map-node-bg)",
        // Dimmed nodes change colour, not opacity, so their text still meets contrast.
        color: dimmed(n.id) ? "var(--color-muted)" : "var(--color-fg)",
        boxShadow: "none",
      },
      sourcePosition: Position.Right, // the layout flows left to right
      targetPosition: Position.Left,
      draggable: false,
      connectable: false,
    }));
    const flowEdges: Edge[] = data.edges.map((e, i) => {
      const active = selected !== null && (e.from === selected || e.to === selected);
      return {
        id: `${e.from}-${e.to}-${i}`,
        source: e.from,
        target: e.to,
        label: e.label ?? undefined,
        animated: active,
        focusable: false,
        labelStyle: { fontSize: 10, fill: "var(--color-muted)" },
        labelBgStyle: { fill: "var(--map-bg)" },
        style: { stroke: active ? "var(--color-accent-2)" : "var(--color-muted)", strokeWidth: active ? 2 : 1 },
      };
    });
    return { nodes: flowNodes, edges: flowEdges };
  }, [data, selected]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (topic.trim().length >= 2) map.mutate(topic.trim());
  };
  const toggle = (id: string) => setSelected((cur) => (cur === id ? null : id));
  // Enter or Space on a focused canvas node selects it (React Flow only handles the mouse).
  const onCanvasKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const el = (e.target as HTMLElement).closest<HTMLElement>(".react-flow__node");
    const id = el?.dataset.id;
    if (!id) return;
    e.preventDefault();
    toggle(id);
  };

  const slug = topic.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "concept-map";
  const selectedLabel = data?.nodes.find((n) => n.id === selected)?.label;
  const related = data && selected ? edgesOf(selected, data.edges) : [];

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Label htmlFor="map-topic">Topic</Label>
            <Input ref={input} id="map-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Graph algorithms" maxLength={200} />
          </div>
          <Button type="submit" disabled={map.isPending || topic.trim().length < 2}>
            {map.isPending ? <BusyIcon /> : <Network className="h-4 w-4" aria-hidden />}
            {map.isPending ? "Generating…" : "Generate map"}
          </Button>
        </form>
      </Card>

      <PendingPanel running={map.isPending} onCancel={cancel} />
      <Announce>
        {cancelled ? "Cancelled." : data ? `Concept map ready: ${plural(data.nodes.length, "concept")}, ${plural(data.edges.length, "link")}.` : ""}
      </Announce>

      {!data && !map.isPending && !error ? (
        <IdlePreview
          items={[
            "A map of the main concepts in the topic and how they link (for example “Heap → implements → Priority queue”).",
            "A text list of the same map, and the passages it was built from.",
            "JSON and Graphviz DOT downloads.",
          ]}
          onPick={(t) => {
            setTopic(t);
            input.current?.focus();
          }}
        />
      ) : null}

      {error ? <LlmError error={error} /> : null}
      <FallbackNotice warning={data?.warning} />
      {data?.grounding_note ? <Notice>{data.grounding_note}</Notice> : null}

      {data ? (
        <div className="space-y-4" aria-busy={map.isPending}>
          <Card className="p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-2">
              <p className="text-sm text-muted">
                {plural(data.nodes.length, "concept")} · {plural(data.edges.length, "link")} · select a concept to highlight its neighbours
              </p>
              <div className="flex flex-wrap gap-1">
                <div className="mr-2 flex rounded-lg border border-border p-0.5" role="group" aria-label="Show as">
                  {(["map", "list"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      aria-pressed={view === v}
                      onClick={() => setView(v)}
                      className={cn(
                        "inline-flex min-h-9 items-center gap-1.5 rounded-md px-2.5 text-xs pointer-coarse:min-h-11",
                        view === v ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
                      )}
                    >
                      {v === "map" ? <Network className="h-3.5 w-3.5" aria-hidden /> : <List className="h-3.5 w-3.5" aria-hidden />}
                      {v === "map" ? "Map" : "List view"}
                    </button>
                  ))}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Download as JSON"
                  onClick={() =>
                    downloadBlob(new Blob([JSON.stringify({ nodes: data.nodes, edges: data.edges }, null, 2)], { type: "application/json" }), `${slug}.json`)
                  }
                >
                  <Download className="h-4 w-4" aria-hidden /> JSON
                </Button>
                <Button variant="ghost" size="sm" aria-label="Download as DOT" onClick={() => downloadBlob(new Blob([data.dot], { type: "text/plain" }), `${slug}.dot`)}>
                  <Download className="h-4 w-4" aria-hidden /> DOT
                </Button>
              </div>
            </div>

            {view === "map" ? (
              <div
                className={cn("h-[28rem] overflow-hidden rounded-lg border border-border", styles.canvas)}
                data-testid="concept-graph"
                onKeyDown={onCanvasKey}
              >
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  colorMode={theme}
                  fitView
                  minZoom={0.2}
                  nodesConnectable={false}
                  nodesDraggable={false}
                  edgesFocusable={false}
                  onNodeClick={(_, n) => toggle(n.id)}
                  onPaneClick={() => setSelected(null)}
                >
                  <Background gap={20} />
                  <Controls showInteractive={false} />
                </ReactFlow>
              </div>
            ) : (
              <ConceptList nodes={data.nodes} edges={data.edges} selected={selected} onSelect={toggle} />
            )}

            {selectedLabel ? (
              <div className="mt-3 px-2 text-sm" aria-live="polite" data-testid="concept-neighbours">
                <span className="font-medium">{selectedLabel}</span>
                {related.length ? (
                  <ul className="mt-1 list-disc pl-5 text-muted">
                    {related.map((e, i) => (
                      <li key={i}>{connectionText(e, data.nodes)}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-muted"> has no links.</span>
                )}
              </div>
            ) : null}
          </Card>

          <PassageList chunks={data.chunks ?? []} prefix="map" query={topic} />
        </div>
      ) : null}
    </div>
  );
}

/** The same map as text: every concept with its connections. */
function ConceptList({
  nodes,
  edges,
  selected,
  onSelect,
}: {
  nodes: { id: string; label: string }[];
  edges: { from: string; to: string; label?: string | null }[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="space-y-2 px-2" aria-label="Concepts and their connections" data-testid="concept-list">
      {nodes.map((n) => {
        const links = edgesOf(n.id, edges);
        return (
          <li key={n.id} className="rounded-lg border border-border p-2.5">
            <button
              type="button"
              aria-pressed={selected === n.id}
              onClick={() => onSelect(n.id)}
              className={cn("min-h-8 text-left text-sm font-medium hover:text-accent-2 pointer-coarse:min-h-11", selected === n.id && "text-accent-2")}
            >
              {n.label}
            </button>
            {links.length ? (
              <ul className="mt-1 list-disc pl-5 text-sm text-muted">
                {links.map((e, i) => (
                  <li key={i}>{connectionText(e, nodes)}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-muted">No connections.</p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
