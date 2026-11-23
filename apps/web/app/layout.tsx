import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import "./globals.css";
import { Providers } from "./providers";

// Manrope and IBM Plex Mono (SIL Open Font License, see app/fonts/*-OFL.txt), served from this app rather than a font CDN.
const manrope = localFont({
  src: [
    { path: "./fonts/manrope-400.ttf", weight: "400", style: "normal" },
    { path: "./fonts/manrope-600.ttf", weight: "600", style: "normal" },
  ],
  variable: "--font-manrope",
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});
const plexMono = localFont({
  src: "./fonts/plex-mono-400.ttf",
  weight: "400",
  variable: "--font-plex",
  fallback: ["ui-monospace", "SFMono-Regular", "monospace"],
});

const DESCRIPTION = "A RAG tutor for Computer Science: ask your own material, get cited answers.";
const SHARE_DESCRIPTION = "Ask your Computer Science material and get answers that show the passages they came from, with citations checked.";

export const metadata: Metadata = {
  title: { default: "Lectern", template: "%s · Lectern" },
  description: DESCRIPTION,
  applicationName: "Lectern",
  openGraph: {
    type: "website",
    siteName: "Lectern",
    title: "Lectern: an AI tutor that shows its sources",
    description: SHARE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Lectern: an AI tutor that shows its sources",
    description: SHARE_DESCRIPTION,
  },
};

// The hosted app talks to the API through the key-holding proxy; unless the owner lifted the limits, it is the public demo.
const isDemo = () => Boolean(process.env.BACKEND_URL) && process.env.BACKEND_ALLOW_WRITES !== "1";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${manrope.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `try{var d=document.documentElement;if(localStorage.getItem("lectern-reading-theme")==="light")d.dataset.theme="light";if(localStorage.getItem("lectern-demo-strip-dismissed"))d.dataset.demoStrip="dismissed"}catch{}` }} /></head>
      <body className="font-sans antialiased">
        <Providers demo={isDemo()}>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
