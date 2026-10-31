# AD Trace: design system

Next 16 + Tailwind 3. Source of truth for the look is the Stitch reference (see the last section); the regulatory-UX rules below override it.

## Tokens
Colours (Tailwind config + slate/blue/amber/red defaults)
- Navy rail `navy` #0B1B33 (800 #12294a, 700 #1b3560); canvas `canvas` #F7F8FA; cards white with 1px slate-200 border.
- Blue-600 #2563EB: actions, focus, TRUE / proposed applicability. Slate: neutral / INFO. Amber (50/300/900): UNKNOWN, uncertainty, enforceability not verified. Red: FALSE and errors only. Never green for applicability.
- Source highlight: `mark.hl` #fde047 (citron) on the page text layer.
Type: Inter (`font-sans`) for UI, JetBrains Mono (`font-mono`) for identifiers (docket, FR docnum, serials). Scale: 11px captions, 12px labels (uppercase, tracking-wide, slate-500), 14px body, 16px section/brand, 20-24px page titles.
Spacing: 4px rhythm (Tailwind 1 = 4px); card padding 16px, page gutters 16-24px.
Radius: 4px everywhere (`rounded-md` and `rounded-lg` both map to 4px). Shadow: `shadow-card` only.
Focus: global `:focus-visible` 2px blue outline, 2px offset; inputs also get a blue ring.

## Components (`components/ui/index.tsx`, helpers `lib/cn.ts`, `lib/useMedia.ts`)
Button (primary/secondary/ghost/danger; sm/md/lg), Card, CardTitle, Badge (tones slate/blue/amber/red/violet/outline), Input, Textarea, Skeleton, Separator, Tooltip (native title), Tabs (role=tablist), Mono. Feature components: Sidebar, QueryPanel, FactsInput, AnswerPanel, Provenance, DocumentViewer, EvaluationView, EmptyState, ErrorState, Disclaimer, Badges.

## Layout
- Sidebar: 232px navy rail with nav and real corpus counts from `/health`; below 1100px it collapses to a 64px icon rail (labels hidden, `title` tooltips kept).
- Search workspace (`/`): three resizable panes (react-resizable-panels): query/facts, answer and provenance, source viewer (default about 480px). Below 768px (`useMedia`) the panes stack vertically and the page scrolls.
- No horizontal page scroll at 768, 1024, 1280, 1440; wide content (tables, mono identifiers) scrolls inside its own container or wraps.

## Application routes and added components
Routes (`app/(app)`): `/dashboard` (live /health corpus counts, headline metrics from `GET /evaluation/runs`, quick actions, real demo queries as deep links), `/search` (Regulatory Intelligence Workspace; deep link `?q=&directive=&model=&serial=&make=` pre-fills and auto-runs once), `/directives`, `/directives/[id]`, `/applicability` (posts `/query`, use_llm false), `/evaluation`, `/dev/fixtures`. Wordmark links to `/` (landing).

- `components/fx/ThinkingDots.tsx`: 3x3 pulsing dot grid + "Retrieving and verifying evidence...", rendered only while the real request is pending; static under reduced motion. No fake step progress.
- `components/fx/LineChart.tsx`: SVG line chart, animated path draw (reduced-motion aware), one marker per measured point (distinct shapes per series), null = gap (never interpolated), values on hover/focus, table fallback. Palette #2563eb / #c2410c / #0e9aa7 validated with the dataviz validator (light mode).
- `components/Activity.tsx`: real `timings_ms` stages via React Bits `AnimatedList`.
- `components/EvaluationDashboard.tsx`: metric cards from the latest run containing each family (shows run + n), Dev/Locked tabs (locked = pre-fix corpus), applicability accuracy "Not measured".
- `components/ApplicabilityLegend.tsx`: the three outcomes (blue / slate / amber, never green).
- React Bits (free, vendored): `StarBorder` around the query card, `AnimatedList` for Activity. Citation cards use `motion` stagger. React Bits Pro is not used.
- Sidebar: Dashboard, AI Search, Directives, Applicability, Evaluation; blue left indicator on the active item; collapses to icons below 1100px.

## Regulatory-UX rules (binding)
- Regulatory stage, proposed applicability (plus final-rule applicability when present) and current enforceability are three separate cells; never merged.
- Applicability label text comes from the API. UNKNOWN reads "Applicability not determined" (amber). No green applicability. Never use "compliant", "approved", "certified", "legally safe".
- "Current authoritative status NOT verified" and the persistent disclaimer always shown. Timeline is labelled "(not legal status)".
- Citations open the source viewer with a highlight, or fall back to a page-level notice when no span can be located. Source-text-unavailable results show an explicit message instead of an empty viewer.
- No mock data in production paths; fixtures live only under `/dev/fixtures` behind a banner.

## Stitch reference
`design/stitch/screen.png` and `design/stitch/README.md` (Stitch project 8689161558297948706). Adopted: navy rail, canvas and card styling, Inter/JetBrains Mono, 4px radius, mono identifier chips, three status cards, evidence chips, source pane header with page nav and zoom, citron highlight, persistent disclaimer.
Deliberately NOT adopted (fabricated or unsupported by the backend): verification latency, token fidelity %, SHA-256 / trace hash, "System Status: Verified", LIVE, version tag, Federal Register daily feed, active bench scope panel, read-only lock label, user avatar, Export Docket, Tuning, History, Govinfo link, invented subject lines, and green check icons on applicability steps (use blue TRUE, slate INFO, amber UNKNOWN, red FALSE). Real values only: latency from `timings_ms`, counts from `/health`.
