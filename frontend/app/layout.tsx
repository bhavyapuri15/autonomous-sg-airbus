import "./globals.css";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jbmono", display: "swap" });

export const metadata = { title: "AD Trace - traceable search for FAA AD proposed rules" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <main className="relative min-h-0 flex-1 overflow-y-auto">{children}</main>
            <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-1.5 text-xs text-slate-600">
              Decision support only. Not an official determination or a compliance determination. Current authoritative status is not verified.
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
