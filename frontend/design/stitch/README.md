# Stitch design reference (Google Stitch project 8689161558297948706)

Generated 2026-10-31 via the Stitch MCP (`generate_screen_from_text`, desktop, Option C hybrid enterprise).
`screen.png` is the generated main-workspace screen. The Stitch design system (Inter + JetBrains Mono, navy #0B1B33 rail,
#F7F8FA canvas, white cards with 1px #E2E8F0 borders, 4px radius, blue #2563EB actions/proposed applicability,
amber #D97706/#FEF3C7 uncertainty, carmine #DC2626 errors only, citron #FEF08A source highlight, 4px spacing rhythm,
right source pane 480px resizable) is the visual source of truth.

## Opus regulatory-UX adaptation rules (override the mock)
Do NOT implement these mock elements (fabricated values or no backend support):
- "Verification latency: 184ms", "100% token fidelity", "SHA-256: 9e32a1", "Trace hash", "System Status: Verified FR
  Pipeline", "LIVE", "v4.8-FAA-FR", "14 CFR Part 39 Daily Feed", "Active bench scope" panel, "Read-Only Regulatory
  Record" lock label, user avatar, "Export Docket", "Tuning", "History", "Govinfo Docket" link.
- Green check icons on applicability steps: use blue (TRUE), slate (INFO), amber (UNKNOWN), red (FALSE).
- "Subject: Stabilator Control Cable Inspection": only show fields the API returns.
Real values only: latency comes from `timings_ms`, corpus counts from `/health`, page counts from the API.
Keep: navy rail + nav, query card with Cmd+Enter hint, inline ID/Model/Serial fields, answered banner, record header with
mono identifier chips, three separate status cards (stage / proposed applicability (blue) / enforceability (amber)),
"N/M conditions" counter computed from explanation steps, evidence chips "87 FR 6091 · (c) Applicability", source pane
header (FR doc, stage pill, FR citation, page nav, zoom), citron highlight box, cited-quote box, official FR PDF/XML links,
persistent footer disclaimer.
