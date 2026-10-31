import type { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";

/** Application shell (workspace routes): navy sidebar, scrolling main, persistent disclaimer. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="relative min-h-0 flex-1 overflow-y-auto">{children}</main>
        <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-1.5 text-xs text-slate-600">
          Decision support only. Not an official determination or a compliance determination. Current authoritative status is not verified.
        </footer>
      </div>
    </div>
  );
}
