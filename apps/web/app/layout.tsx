import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "Lectern", template: "%s · Lectern" },
  description: "A RAG tutor for Computer Science: ask your own material, get cited answers.",
};

// The hosted app talks to the API through the key-holding proxy; unless the owner lifted the limits, it is the public demo.
const isDemo = () => Boolean(process.env.BACKEND_URL) && process.env.BACKEND_ALLOW_WRITES !== "1";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">
        <Providers demo={isDemo()}>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
