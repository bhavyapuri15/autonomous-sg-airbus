"use client";
import { cn } from "@/lib/cn";

/**
 * Small animated dot grid shown ONLY while a real request is pending.
 * It renders nothing when `pending` is false and never implies step-by-step progress.
 * Animation is pure CSS and disabled under prefers-reduced-motion (see globals.css).
 */
export function ThinkingDots({ pending, text = "Retrieving and verifying evidence...", className }: { pending: boolean; text?: string; className?: string }) {
  if (!pending) return null;
  return (
    <div role="status" aria-live="polite" data-testid="thinking-dots" className={cn("flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50/60 px-4 py-3 text-sm text-blue-950", className)}>
      <span className="thinking-grid" aria-hidden>
        {Array.from({ length: 9 }).map((_, i) => <i key={i} style={{ animationDelay: `${(i % 3) * 120 + Math.floor(i / 3) * 120}ms` }} />)}
      </span>
      <span>{text}</span>
    </div>
  );
}
