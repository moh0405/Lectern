import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

// The link preview card, drawn at build time from the app's own font (no external assets).
export const alt = "Lectern: an AI tutor that shows its sources";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  const [manrope, plex] = await Promise.all([
    readFile(join(process.cwd(), "app/fonts/manrope-600.ttf")),
    readFile(join(process.cwd(), "app/fonts/plex-mono-400.ttf")),
  ]);
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#10151b", color: "#e8edf3", fontFamily: "Manrope" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "72px 64px" }}>
          <div style={{ display: "flex", fontFamily: "Plex", fontSize: 22, letterSpacing: 4, color: "#c4afff", textTransform: "uppercase" }}>
            Lectern · Computer Science tutor
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 76, lineHeight: 1.05, letterSpacing: -3 }}>An AI tutor that</div>
            <div style={{ fontSize: 76, lineHeight: 1.05, letterSpacing: -3 }}>shows its sources.</div>
            <div style={{ marginTop: 28, fontSize: 28, color: "#a0acba" }}>Answers show the passages they came from, and citations are checked.</div>
          </div>
        </div>
        <div style={{ width: 360, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 40px", background: "#efede7", color: "#2b3033" }}>
          <div style={{ display: "flex", fontFamily: "Plex", fontSize: 16, letterSpacing: 3, color: "#5c5d55", textTransform: "uppercase" }}>Source · page 132</div>
          <div style={{ marginTop: 18, display: "flex", fontSize: 26, lineHeight: 1.45 }}>
            A heap is a complete binary tree in which every parent is ordered before its children.
          </div>
          <div style={{ marginTop: 22, display: "flex", width: 120, height: 6, borderRadius: 3, background: "#6a4fa3" }} />
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Manrope", data: manrope, weight: 600, style: "normal" },
        { name: "Plex", data: plex, weight: 400, style: "normal" },
      ],
    },
  );
}
