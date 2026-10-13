"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMutation } from "@tanstack/react-query";
import { Download, Network } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Spinner } from "@/components/ui/feedback";
import { api, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { layoutGraph, NODE_H, NODE_W } from "./graph-layout";

export function ConceptMap() {
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const map = useMutation({
    mutationFn: async (t: string) => unwrap(await api.http.POST("/api/v1/concept-map", { body: { topic: t } })),
    onMutate: () => setSelected(null),
  });

  const { nodes, edges } = useMemo(() => {
    const data = map.data;
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[] };
    const positioned = layoutGraph(data.nodes, data.edges);
    const touching = new Set<string>();
    if (selected) for (const e of data.edges) if (e.from === selected || e.to === selected) touching.add(e.from).add(e.to);
    const flowNodes: Node[] = positioned.map((n) => ({
      id: n.id,
      position: { x: n.x, y: n.y },
      data: { label: n.label },
      style: {
        width: NODE_W,
        height: NODE_H,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        fontSize: 13,
        fontWeight: 500,
        borderRadius: 10,
        border: `1px solid ${n.id === selected ? "var(--color-accent-2)" : "var(--color-border)"}`,
        background: touching.size && !touching.has(n.id) ? "var(--color-surface)" : "var(--color-surface-2)",
        color: "var(--color-fg)",
        opacity: touching.size && !touching.has(n.id) ? 0.45 : 1,
      },
      sourcePosition: Position.Right, // the layout flows left to right
      targetPosition: Position.Left,
      draggable: false,
    }));
    const flowEdges: Edge[] = data.edges.map((e, i) => ({
      id: `${e.from}-${e.to}-${i}`,
      source: e.from,
      target: e.to,
      label: e.label ?? undefined,
      animated: selected !== null && (e.from === selected || e.to === selected),
      labelStyle: { fontSize: 10, fill: "var(--color-muted)" },
      labelBgStyle: { fill: "var(--color-bg)" },
      style: { stroke: "var(--color-border)" },
    }));
    return { nodes: flowNodes, edges: flowEdges };
  }, [map.data, selected]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (topic.trim().length >= 2) map.mutate(topic.trim());
  };
  const slug = topic.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "concept-map";
  const selectedLabel = map.data?.nodes.find((n) => n.id === selected)?.label;
  const related = map.data?.edges.filter((e) => e.from === selected || e.to === selected) ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Label htmlFor="map-topic">Topic</Label>
            <Input id="map-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Graph algorithms" maxLength={200} />
          </div>
          <Button type="submit" disabled={map.isPending || topic.trim().length < 2}>
            {map.isPending ? <Spinner /> : <Network className="h-4 w-4" />}
            Generate map
          </Button>
        </form>
      </Card>

      {map.isError ? <LlmError error={map.error} /> : null}
      <FallbackNotice warning={map.data?.warning} />

      {map.data ? (
        <Card className="p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-2">
            <p className="text-sm text-muted">
              {map.data.nodes.length} concepts · {map.data.edges.length} links · click a concept to highlight its neighbours
            </p>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  downloadBlob(
                    new Blob([JSON.stringify({ nodes: map.data.nodes, edges: map.data.edges }, null, 2)], { type: "application/json" }),
                    `${slug}.json`,
                  )
                }
              >
                <Download className="h-4 w-4" /> JSON
              </Button>
              <Button variant="ghost" size="sm" onClick={() => downloadBlob(new Blob([map.data.dot], { type: "text/plain" }), `${slug}.dot`)}>
                <Download className="h-4 w-4" /> DOT
              </Button>
            </div>
          </div>
          <div className="h-[28rem] overflow-hidden rounded-lg border border-border" data-testid="concept-graph">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              colorMode="dark"
              fitView
              minZoom={0.2}
              nodesConnectable={false}
              proOptions={{ hideAttribution: true }}
              onNodeClick={(_, n) => setSelected((cur) => (cur === n.id ? null : n.id))}
              onPaneClick={() => setSelected(null)}
            >
              <Background gap={20} color="var(--color-border)" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          {selectedLabel ? (
            <div className="mt-3 px-2 text-sm" aria-live="polite">
              <span className="font-medium">{selectedLabel}</span>
              {related.length ? (
                <ul className="mt-1 list-disc pl-5 text-muted">
                  {related.map((e, i) => (
                    <li key={i}>
                      {map.data.nodes.find((n) => n.id === e.from)?.label} → {e.label ?? "related to"} →{" "}
                      {map.data.nodes.find((n) => n.id === e.to)?.label}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted"> has no links.</span>
              )}
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
