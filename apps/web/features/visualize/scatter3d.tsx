"use client";

import type { components } from "@ai-study-mentor/api-client";
import { useEffect, useRef, useState } from "react";
import { ErrorNotice, Notice } from "@/components/ui/feedback";

type Point = components["schemas"]["ProjectionPoint"];

export function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") ?? c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Group points by document, so each document is one legend entry (click to hide or isolate). */
export function groupByDoc(points: Point[]): Map<string, Point[]> {
  const groups = new Map<string, Point[]>();
  for (const p of points) {
    const g = groups.get(p.doc);
    if (g) g.push(p);
    else groups.set(p.doc, [p]);
  }
  return groups;
}

export function Scatter3D({ points, onSelect }: { points: Point[]; onSelect: (p: Point) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [webgl] = useState(() => (typeof document === "undefined" ? true : hasWebGL()));
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  useEffect(() => {
    const el = ref.current;
    if (!el || !webgl || points.length === 0) return;
    let cancelled = false;
    let purge: (() => void) | undefined;
    (async () => {
      const Plotly = (await import("plotly.js-gl3d-dist-min")).default;
      if (cancelled) return;
      const traces = [...groupByDoc(points)].map(([doc, pts]) => ({
        type: "scatter3d",
        mode: "markers",
        name: doc.length > 28 ? `${doc.slice(0, 27)}…` : doc,
        x: pts.map((p) => p.x),
        y: pts.map((p) => p.y),
        z: pts.map((p) => p.z),
        customdata: pts.map((p) => p.index),
        text: pts.map((p) => `${p.text.slice(0, 120)}${p.text.length > 120 ? "…" : ""}`),
        hovertemplate: `<b>${doc.replace(/[<>&]/g, "")}</b><br>%{text}<extra></extra>`,
        marker: { size: 4, opacity: 0.85 },
      }));
      const axis = { showgrid: true, gridcolor: "#263050", zeroline: false, showticklabels: false, title: { text: "" }, backgroundcolor: "rgba(0,0,0,0)" };
      const plot = await Plotly.react(
        el,
        traces,
        {
          paper_bgcolor: "rgba(0,0,0,0)",
          font: { color: "#95a0bd", size: 11 },
          margin: { l: 0, r: 0, t: 0, b: 0 },
          legend: { x: 0, y: 1, xanchor: "left", yanchor: "top", bgcolor: "rgba(11,16,32,0.6)", font: { size: 10 } },
          scene: { xaxis: axis, yaxis: axis, zaxis: axis, bgcolor: "rgba(0,0,0,0)" },
        },
        { responsive: true, displaylogo: false, displayModeBar: false },
      );
      if (cancelled) return;
      plot.on("plotly_click", (ev) => {
        const idx = ev.points[0]?.customdata;
        const hit = points.find((p) => p.index === idx);
        if (hit) onSelectRef.current(hit);
      });
      purge = () => Plotly.purge(el);
    })().catch((e) => setError(e instanceof Error ? e.message : "Could not draw the plot"));
    return () => {
      cancelled = true;
      purge?.();
    };
  }, [points, webgl]);

  if (!webgl) {
    return <Notice>Your browser cannot draw WebGL graphics, so the 3D view is unavailable. The passage list below still works.</Notice>;
  }
  return (
    <>
      {error ? <ErrorNotice>{error}</ErrorNotice> : null}
      <div ref={ref} className="h-[30rem] w-full" data-testid="scatter3d" />
    </>
  );
}
