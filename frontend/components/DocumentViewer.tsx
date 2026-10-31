"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { findQuote, findShortQuoteSpan } from "@/lib/match";
import type { CitationRef } from "@/lib/types";
import { ChevronLeft, ChevronRight, ExternalLink, X, ZoomIn, ZoomOut } from "lucide-react";
import { Button, Tabs } from "@/components/ui";
import { ErrorState } from "./ErrorState";
import { TierBadge } from "./Badges";
import { CitationLine, StagePill } from "./Provenance";

type HlState = "pending" | "ok" | "failed";

function PdfView({ citation, page, scale, onHl, onPages }: { citation: CitationRef; page: number; scale: number; onHl: (s: HlState) => void; onPages: (n: number) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<unknown>(null);
  const isCited = page === (citation.pdf_page ?? 1);

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
        onPages(doc.numPages);
        const pg = await doc.getPage(Math.min(Math.max(page, 1), doc.numPages));
        const viewport = pg.getViewport({ scale });
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
        if (!isCited) { onHl("pending"); return; }
        // Style text spans: transparent text, positioned by pdf.js.
        layer.querySelectorAll("span").forEach((s) => { (s as HTMLElement).style.color = "transparent"; });
        const divs = tl.textDivs as HTMLElement[];
        let joined = ""; const ranges: [number, number][] = [];
        divs.forEach((d) => { const t = d.textContent || ""; ranges.push([joined.length, joined.length + t.length]); joined += t + " "; });
        const m = findQuote(joined, citation.quote);
        if (!m) {
          const si = findShortQuoteSpan(divs.map((d) => d.textContent || ""), citation.quote);
          if (si >= 0) { divs[si].style.background = "rgba(254,240,138,0.75)"; onHl("ok"); } else onHl("failed");
          return;
        }
        let n = 0;
        divs.forEach((d, i) => {
          if (ranges[i][1] > m[0] && ranges[i][0] < m[1]) { d.style.background = "rgba(254,240,138,0.75)"; n++; }
        });
        onHl(n > 0 ? "ok" : "failed");
      } catch (e) {
        if (!cancelled) { setErr(e instanceof Error ? e : new Error(String(e))); onHl("failed"); }
      }
    })();
    return () => { cancelled = true; task?.destroy().catch(() => {}); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citation.fr_docnum, page, scale, citation.quote]);

  return (
    <div className="overflow-auto bg-slate-200 p-3">
      {err ? <ErrorState error={err} /> : null}
      <div ref={wrap} className="relative mx-auto bg-white" aria-label={`PDF page ${page}`} />
    </div>
  );
}

function TextView({ citation, page }: { citation: CitationRef; page: number | null }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<unknown>(null);
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
  const m = page === citation.pdf_page ? findQuote(text, citation.quote) : null;
  return (
    <div className="p-3">
      {!m && page === citation.pdf_page && <p className="mb-2 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950">Quote could not be located in this page&apos;s text; the cited page is shown unhighlighted.</p>}
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed" data-testid="page-text">
        {m ? <>{text.slice(0, m[0])}<mark className="hl">{text.slice(m[0], m[1])}</mark>{text.slice(m[1])}</> : text}
      </pre>
    </div>
  );
}

export function DocumentViewer({ citation, onClose, stage }: { citation: CitationRef; onClose: () => void; stage?: string | null }) {
  const [tab, setTab] = useState<"pdf" | "text">("pdf");
  const [hl, setHl] = useState<HlState>("pending");
  const [page, setPage] = useState<number>(citation.pdf_page ?? 1);
  const [pages, setPages] = useState<number | null>(null);
  const [scale, setScale] = useState(1.1);
  const isSheet = citation.source_tier !== "FR_FULL_TEXT";
  const onCited = page === (citation.pdf_page ?? 1);
  const go = (n: number) => setPage(Math.min(Math.max(n, 1), pages ?? Math.max(n, 1)));
  const official = citation.source_url || citation.pdf_url;
  return (
    <aside className="flex h-full min-h-0 flex-col rounded-lg border border-slate-200 bg-white shadow-card" aria-label="Document viewer">
      <div className="space-y-2 border-b border-slate-200 px-3 py-2">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-mono text-sm font-semibold">FR Doc. {citation.fr_docnum}</span>
              {citation.record_ids?.length ? <span className="font-mono text-xs text-slate-600">{citation.record_ids.join(", ")}</span> : null}
              {stage && <StagePill stage={stage} />}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2"><CitationLine c={citation} /></div>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close viewer"><X size={14} aria-hidden />Close</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <TierBadge tier={citation.source_tier} />
          <span>FR p. {citation.fr_page ?? "n/a"} · PDF p. {citation.pdf_page ?? "n/a"} {citation.label ? `· ${citation.label}` : ""}</span>
          {!isSheet && (
            <div className="ml-auto flex items-center gap-1">
              <Button size="sm" aria-label="Previous page" disabled={page <= 1} onClick={() => go(page - 1)}><ChevronLeft size={14} aria-hidden /></Button>
              <span className="min-w-[4.5rem] text-center font-mono" data-testid="page-nav">{page}{pages ? ` / ${pages}` : ""}</span>
              <Button size="sm" aria-label="Next page" disabled={pages !== null && page >= pages} onClick={() => go(page + 1)}><ChevronRight size={14} aria-hidden /></Button>
              <Button size="sm" aria-label="Zoom out" disabled={scale <= 0.6} onClick={() => setScale((x) => Math.max(0.6, +(x - 0.2).toFixed(1)))}><ZoomOut size={14} aria-hidden /></Button>
              <Button size="sm" aria-label="Zoom in" disabled={scale >= 2.2} onClick={() => setScale((x) => Math.min(2.2, +(x + 0.2).toFixed(1)))}><ZoomIn size={14} aria-hidden /></Button>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-3 text-xs">
          {official && <a className="inline-flex items-center gap-1 text-blue-600 hover:underline" href={official} target="_blank" rel="noreferrer"><ExternalLink size={12} aria-hidden />Open official source</a>}
          {citation.pdf_url && <a className="text-blue-600 hover:underline" href={citation.pdf_url} target="_blank" rel="noreferrer">Official FR PDF</a>}
          {citation.xml_url && <a className="text-blue-600 hover:underline" href={citation.xml_url} target="_blank" rel="noreferrer">Official FR XML</a>}
        </div>
      </div>
      <div className="border-b border-slate-200 px-3 py-2">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Cited quote</div>
        <blockquote className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap rounded-lg border-l-4 border-yellow-300 bg-yellow-50 p-2 font-mono text-xs">{citation.quote}</blockquote>
        {!isSheet && tab === "pdf" && onCited && hl === "failed" && (
          <p className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950" data-testid="hl-unavailable">
            Exact highlight unavailable — quote shown above; cited page is {citation.fr_page ?? "n/a"}
          </p>
        )}
        {!isSheet && tab === "pdf" && onCited && hl === "ok" && <p className="mt-1 text-xs text-slate-600">Quote located and highlighted on the page (approximate match; verify wording).</p>}
        {!isSheet && !onCited && <p className="mt-1 text-xs text-slate-600">Viewing a different page than the cited one. <button className="text-blue-600 underline" onClick={() => setPage(citation.pdf_page ?? 1)}>Back to cited page</button></p>}
      </div>
      {isSheet ? (
        <p className="p-3 text-sm">This evidence comes from the spreadsheet (row {citation.sheet_row ?? "n/a"}), not from Federal Register text, so there is no page to display.</p>
      ) : (
        <>
          <Tabs label="Viewer mode" value={tab} onChange={setTab} tabs={[{ id: "pdf", label: "PDF view" }, { id: "text", label: "Text view" }]} />
          <div className="min-h-0 flex-1 overflow-auto">
            {tab === "pdf" ? <PdfView citation={citation} page={page} scale={scale} onHl={setHl} onPages={setPages} /> : <TextView key={`${citation.fr_docnum}-${page}`} citation={citation} page={page} />}
          </div>
        </>
      )}
    </aside>
  );
}
