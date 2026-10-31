import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type BtnVariant = "primary" | "secondary" | "ghost" | "danger";
type BtnSize = "sm" | "md" | "lg";
const btnV: Record<BtnVariant, string> = {
  primary: "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300 border border-transparent",
  secondary: "bg-white text-slate-800 border border-slate-300 hover:bg-slate-50 disabled:opacity-50",
  ghost: "bg-transparent text-slate-700 border border-transparent hover:bg-slate-100 disabled:opacity-50",
  danger: "bg-white text-red-700 border border-red-300 hover:bg-red-50",
};
const btnS: Record<BtnSize, string> = { sm: "h-7 px-2 text-xs", md: "h-9 px-3 text-sm", lg: "h-10 px-4 text-sm" };

export function Button({ variant = "secondary", size = "md", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: BtnSize }) {
  return <button type="button" {...p} className={cn("inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed", btnV[variant], btnS[size], className)} />;
}

export function Card({ className, ...p }: HTMLAttributes<HTMLElement>) {
  return <section {...p} className={cn("rounded-lg border border-slate-200 bg-white p-4 shadow-card", className)} />;
}
export function CardTitle({ className, icon, children, ...p }: HTMLAttributes<HTMLHeadingElement> & { icon?: ReactNode }) {
  return <h2 {...p} className={cn("mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500", className)}>{icon}{children}</h2>;
}

type Tone = "slate" | "blue" | "amber" | "red" | "violet" | "outline";
const tones: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  blue: "bg-blue-50 text-blue-800 border-blue-200",
  amber: "bg-amber-50 text-amber-900 border-amber-300",
  red: "bg-red-50 text-red-800 border-red-300",
  violet: "bg-indigo-50 text-indigo-800 border-indigo-200",
  outline: "bg-white text-slate-700 border-slate-300",
};
export function Badge({ tone = "slate", className, ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span {...p} className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium", tones[tone], className)} />;
}

const field = "w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30";
export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cn(field, "h-9", className)} />;
}
export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cn(field, "py-2", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-md bg-slate-200", className)} />;
}
export function Separator({ className }: { className?: string }) {
  return <hr className={cn("border-0 border-t border-slate-200", className)} />;
}
export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return <span title={text} className="inline-flex">{children}</span>;
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void; label?: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 border-b border-slate-200">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn("-mb-px border-b-2 px-3 py-1.5 text-sm font-medium", value === t.id ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-800")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Mono({ className, ...p }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...p} className={cn("font-mono text-[0.92em]", className)} />;
}
