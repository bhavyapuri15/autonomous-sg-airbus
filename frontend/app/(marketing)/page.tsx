import Link from "next/link";

/** Placeholder landing page; replaced by the full marketing page. */
export default function Landing() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#101B30] text-white">
      <Link href="/search" className="rounded bg-blue-600 px-4 py-2">Launch Workspace</Link>
    </main>
  );
}
