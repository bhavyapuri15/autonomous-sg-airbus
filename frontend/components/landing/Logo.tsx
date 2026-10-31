import Link from "next/link";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`inline-flex items-center gap-2.5 rounded-md text-white ${className}`} aria-label="AD Trace home">
      <span aria-hidden className="grid h-7 w-7 place-items-center rounded bg-blue-600 text-[11px] font-bold tracking-tight text-white">AD</span>
      <span className="text-[15px] font-semibold tracking-tight">AD Trace</span>
    </Link>
  );
}
