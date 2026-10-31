import { render, screen, within } from "@testing-library/react";
import { AnswerPanel } from "@/components/AnswerPanel";
import { CitationLine } from "@/components/Provenance";
import answered from "@/fixtures/answered.json";
import type { CitationRef, QueryResponse } from "@/lib/types";

const noop = () => {};
const cite = {
  citation_id: "abc", fr_docnum: "2026-12345", quote: "This AD applies to ...", source_tier: "FR_FULL_TEXT",
  record_ids: ["NPRM-001"], federal_register_citation: "91 FR 66022", section: "(c) Applicability",
  source_url: "https://www.federalregister.gov/d/2026-12345",
} as CitationRef;

function build(over: Partial<QueryResponse> = {}, applicability: object = {}): QueryResponse {
  const base = JSON.parse(JSON.stringify(answered)) as QueryResponse;
  return {
    ...base,
    applicability: { ...base.applicability, ...applicability },
    directive: { ...base.directive, record_ids: ["NPRM-001"], regulatory_stage: "PROPOSED_RULE", source_url: "https://example.gov/x", sheet_rows: [] },
    revision: {
      ...base.revision!, regulatory_stage: "PROPOSED_RULE", enforceability: "NOT_VERIFIED", status_flags: ["LATEST_IN_DATASET"],
      dataset_history: {
        docket: "FAA-2026-1", versions_total: 2, this_version: 2, dataset_status: "LATEST_IN_DATASET", latest_record_id: "NPRM-002",
        source: "x", note: "Latest publish date = latest version in the supplied dataset.", warnings: ["tie on date"],
        history: [
          { record_id: "NPRM-001", publish_date: "2026-01-01", doc_class: "NPRM", fr_docnum: "2026-1", is_latest: false },
          { record_id: "NPRM-002", publish_date: "2026-02-01", doc_class: "SNPRM", fr_docnum: "2026-2", is_latest: true },
        ],
      },
      proposed_supersedes: [{ ad_number: "2020-01-02", source: "organiser_supersedes_ad_field", operative_supersession_verified: false }],
    },
    ...over,
  } as QueryResponse;
}

describe("provenance UI", () => {
  it("status strip shows three separate items", () => {
    render(<AnswerPanel response={build({}, { value: "APPLICABLE", label: "Applicable under the proposed rule", basis: "PROPOSED_RULE" })} onOpenCitation={noop} />);
    const strip = screen.getByTestId("status-strip");
    expect(within(screen.getByTestId("cell-stage")).getByText("Proposed rule (NPRM)")).toBeInTheDocument();
    const app = within(screen.getByTestId("cell-applicability"));
    expect(app.getByText("APPLICABLE")).toBeInTheDocument();
    expect(app.getByText("Applicable under the proposed rule")).toBeInTheDocument();
    expect(within(screen.getByTestId("cell-enforceability")).getByText("Not verified")).toBeInTheDocument();
    expect(strip).toHaveTextContent("Record NPRM-001");
  });
  it("never uses the words compliant or approved", () => {
    for (const v of ["APPLICABLE", "NOT_APPLICABLE", "UNKNOWN", "NOT_EVALUATED"]) {
      const { container, unmount } = render(<AnswerPanel response={build({}, { value: v })} onOpenCitation={noop} />);
      expect(container.textContent?.toLowerCase()).not.toMatch(/compliant|approved/);
      unmount();
    }
  });
  it("UNKNOWN shows Applicability not determined in the strip", () => {
    render(<AnswerPanel response={build({}, { value: "UNKNOWN", label: null })} onOpenCitation={noop} />);
    expect(within(screen.getByTestId("cell-applicability")).getByText("Applicability not determined")).toBeInTheDocument();
  });
  it("timeline marks latest entry as not legal status", () => {
    render(<AnswerPanel response={build()} onOpenCitation={noop} />);
    const items = within(screen.getByLabelText("Dataset history timeline")).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[1]).toHaveTextContent("Latest in supplied dataset (not legal status)");
    expect(items[0]).not.toHaveTextContent("not legal status");
    expect(screen.getByText("tie on date")).toBeInTheDocument();
  });
  it("proposed supersession says not an operative supersession", () => {
    render(<AnswerPanel response={build()} onOpenCitation={noop} />);
    expect(screen.getByTestId("supersession")).toHaveTextContent(/not an operative supersession/);
  });
  it("citation line renders record_id and FR citation", () => {
    render(<CitationLine c={cite} />);
    expect(screen.getByTestId("citation-line")).toHaveTextContent("NPRM-001 · 91 FR 66022 · (c) Applicability");
    expect(screen.getByText("source")).toHaveAttribute("href", cite.source_url);
  });
  it("renders defensively when new fields are absent", () => {
    render(<AnswerPanel response={JSON.parse(JSON.stringify(answered))} onOpenCitation={noop} />);
    expect(screen.getByTestId("cell-enforceability")).toHaveTextContent("Not verified");
  });
});
