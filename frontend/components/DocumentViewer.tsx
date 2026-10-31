"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { findQuote } from "@/lib/match";
import type { CitationRef } from "@/lib/types";
import { ErrorState } from "./ErrorState";
import { TierBadge } from "./Badges";

type HlState = "pending" | "ok" | "failed";

function PdfView({ citation, onHl }: { citation: CitationRef; onHl: (s: HlState) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<unknown>(null);
  const page = citation.pdf_page ?? 1;

  useEffect(() => {
    let cancelled = false;
    let task: { destroy: () => Promise<void> } | null = null;
    (async () => {
      onHl("pending");
      setErr(null);
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        const loading = pdfjs.getDocument({ url: api.pdfUrl(citation.fr_docnum) });
        task = loading;
        const doc = await loading.promise;
        const pg = await doc.getPage(Math.min(Math.max(page, 1), doc.numPages));
        const viewport = pg.getViewport({ scale: 1.3 });
        if (cancelled || !wrap.current) return;
        const host = wrap.current;
        host.innerHTML = "";
        host.style.width = `${viewport.width}px`;
        host.style.height = `${viewport.height}px`;
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width; canvas.height = viewport.height;
        host.appendChild(canvas);
        await pg.render({ canvas, viewport }).promise;
        const layer = document.createElement("div");
        layer.className = "textLayer";
        layer.style.cssText = "position:absolute;inset:0;overflow:hidden;line-height:1;";
        layer.style.setProperty("--scale-factor", String(viewport.scale));
        layer.style.setProperty("--total-scale-factor", String(viewport.scale));
        host.appendChild(layer);
        const tl = new pdfjs.TextLayer({ textContentSource: pg.streamTextContent(), container: layer, viewport });
        await tl.render();
        if (cancelled) return;
        // Style text spans: transparent text, positioned by pdf.js.
        layer.querySelectorAll("span").forEach((s) => { (s as HTMLElement).style.color = "transparent"; });
        const divs = tl.textDivs as HTMLElement[];
        let joined = ""; const ranges: [number, number][] = [];
        divs.forEach((d) => { const t = d.textContent || ""; ranges.push([joined.length, joined.length + t.length]); joined += t + " "; });
        const m = findQuote(joined, citation.quote);
        if (!m) { onHl("failed"); return; }
        let n = 0;
        divs.forEach((d, i) => {
          if (ranges[i][1] > m[0] && ranges[i][0] < m[1]) { d.style.background = "rgba(250,204,21,0.45)"; n++; }
        });
        onHl(n > 0 ? "ok" : "failed");
      } catch (e) {
        if (!cancelled) { setErr(e instanceof Error ? e : new Error(String(e))); onHl("failed"); }
      }
    })();
    return () => { cancelled = true; task?.destroy().catch(() => {}); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citation.fr_docnum, page, citation.quote]);

  return (
    <div className="overflow-auto bg-slate-300 p-2">
      {err ? <ErrorState error={err} /> : null}
      <div ref={wrap} className="relative mx-auto bg-white" aria-label={`PDF page ${page}`} />
    </div>
  );
}

function TextView({ citation }: { citation: CitationRef }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const page = citation.pdf_page;
  useEffect(() => {
    if (page == null) return;
    let off = false;
    api.page(citation.fr_docnum, page).then((d) => !off && setData(d)).catch((e) => !off && setErr(e));
    return () => { off = true; };
  }, [citation.fr_docnum, page]);
  if (page == null) return <p className="p-3 text-sm">No PDF page recorded for this citation.</p>;
  if (err) return <ErrorState error={err} />;
  if (!data) return <p className="p-3 text-sm">Loading page text…</p>;
  const text = String(data.text ?? data.page_text ?? "");
  const m = findQuote(text, citation.quote);
  return (
    <div className="p-3">
      {!m && <p className="mb-2 rounded border border-amber-500 bg-amber-50 p-2 text-xs">Quote could not be located in this page&apos;s text; the cited page is shown unhighlighted.</p>}
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed" data-testid="page-text">
        {m ? <>{text.slice(0, m[0])}<mark className="hl">{text.slice(m[0], m[1])}</mark>{text.slice(m[1])}</> : text}
      </pre>
    </div>
  );
}

export function DocumentViewer({ citation, onClose }: { citation: CitationRef; onClose: () => void }) {
  const [tab, setTab] = useState<"pdf" | "text">("pdf");
  const [hl, setHl] = useState<HlState>("pending");
  const isSheet = citation.source_tier !== "FR_FULL_TEXT";
  return (
    <aside className="flex h-full flex-col rounded-lg border border-slate-400 bg-white shadow-lg" aria-label="Document viewer">
      <div className="flex items-center gap-2 border-b border-slate-300 bg-slate-100 px-3 py-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-sm font-semibold">FR Doc. {citation.fr_docnum}</div>
          <div className="text-xs text-slate-700">FR p. {citation.fr_page ?? "n/a"} · PDF p. {citation.pdf_page ?? "n/a"} {citation.label ? `· ${citation.label}` : ""}</div>
        </div>
        <TierBadge tier={citation.source_tier} />
        <button onClick={onClose} className="rounded border border-slate-500 px-2 py-0.5 text-sm hover:bg-slate-200" aria-label="Close viewer">Close</button>
      </div>
      <div className="border-b border-slate-300 p-3">
        <div className="text-xs font-semibold uppercase text-slate-600">Cited quote</div>
        <blockquote className="mt-1 max-h-32 overflow-auto border-l-4 border-yellow-400 bg-yellow-50 p-2 font-mono text-xs whitespace-pre-wrap">{citation.quote}</blockquote>
        {!isSheet && tab === "pdf" && hl === "failed" && (
          <p className="mt-2 rounded border border-amber-600 bg-amber-50 p-2 text-xs text-amber-950" data-testid="hl-unavailable">
            Exact highlight unavailable — quote shown above; cited page is {citation.fr_page ?? "n/a"}
          </p>
        )}
        {!isSheet && tab === "pdf" && hl === "ok" && <p className="mt-1 text-xs text-emerald-800">Quote located and highlighted on the page (approximate match; verify wording).</p>}
        <div className="mt-2 flex gap-3 text-xs">
          {citation.pdf_url && <a className="text-sky-800 underline" href={citation.pdf_url} target="_blank" rel="noreferrer">Official FR PDF</a>}
          {citation.xml_url && <a className="text-sky-800 underline" href={citation.xml_url} target="_blank" rel="noreferrer">Official FR XML</a>}
        </div>
      </div>
      {isSheet ? (
        <p className="p-3 text-sm">This evidence comes from the spreadsheet (row {citation.sheet_row ?? "n/a"}), not from Federal Register text, so there is no page to display.</p>
      ) : (
        <>
          <div role="tablist" className="flex border-b border-slate-300 text-sm">
            {(["pdf", "text"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={`px-4 py-1.5 ${tab === t ? "border-b-2 border-slate-900 font-semibold" : "text-slate-600"}`}>
                {t === "pdf" ? "PDF view" : "Text view"}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {tab === "pdf" ? <PdfView citation={citation} onHl={setHl} /> : <TextView key={`${citation.fr_docnum}-${citation.pdf_page}`} citation={citation} />}
          </div>
        </>
      )}
    </aside>
  );
}
