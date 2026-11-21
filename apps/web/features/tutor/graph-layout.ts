import dagre from "@dagrejs/dagre";

export interface GraphNode {
  id: string;
  label: string;
}
export interface GraphEdge {
  from: string;
  to: string;
  label?: string | null;
}
export interface Positioned extends GraphNode {
  x: number;
  y: number;
}

export const NODE_W = 150;
export const NODE_H = 44;

/** Left-to-right layered layout; returns top-left positions suitable for React Flow. */
export function layoutGraph(nodes: GraphNode[], edges: GraphEdge[]): Positioned[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 24, ranksep: 56 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  const ids = new Set(nodes.map((n) => n.id));
  for (const e of edges) if (ids.has(e.from) && ids.has(e.to)) g.setEdge(e.from, e.to);
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 };
  });
}

/** "Linked list → has → Node" for one edge (labels, not ids). */
export function connectionText(edge: GraphEdge, nodes: GraphNode[]): string {
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  return `${label(edge.from)} → ${edge.label || "related to"} → ${label(edge.to)}`;
}

/** The edges touching a node, in map order. */
export function edgesOf(id: string, edges: GraphEdge[]): GraphEdge[] {
  return edges.filter((e) => e.from === id || e.to === id);
}

/** Screen-reader name for a node on the canvas. */
export function nodeAriaLabel(node: GraphNode, edges: GraphEdge[]): string {
  const n = edgesOf(node.id, edges).length;
  if (n === 0) return `${node.label}, no connections.`;
  return `${node.label}, ${n} ${n === 1 ? "connection" : "connections"}. Press Enter to show ${n === 1 ? "it" : "them"}.`;
}

export function toDot(nodes: GraphNode[], edges: GraphEdge[]): string {
  const q = (s: string) => `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  return [
    "digraph G {",
    "  rankdir=LR;",
    ...nodes.map((n) => `  ${q(n.id)} [label=${q(n.label)}];`),
    ...edges.map((e) => `  ${q(e.from)} -> ${q(e.to)} [label=${q(e.label ?? "related")}];`),
    "}",
  ].join("\n");
}
