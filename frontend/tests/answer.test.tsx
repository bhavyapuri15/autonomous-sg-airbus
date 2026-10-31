import { render, screen, within } from "@testing-library/react";
import { AnswerPanel } from "@/components/AnswerPanel";
import { findQuote } from "@/lib/match";
import answered from "@/fixtures/answered.json";
import needs from "@/fixtures/needs_info.json";
import abstained from "@/fixtures/abstained.json";
import type { QueryResponse } from "@/lib/types";

const R = (x: unknown) => x as QueryResponse;
const noop = () => {};

describe("AnswerPanel", () => {
  it("renders ANSWERED with citation markers and tier badges", () => {
    render(<AnswerPanel response={R(answered)} onOpenCitation={noop} />);
    expect(within(screen.getByTestId("status-banner")).getByText("ANSWERED")).toBeInTheDocument();
    expect(screen.getByLabelText("Open citation 1")).toBeInTheDocument();
    expect(screen.getByText("Official FR text")).toBeInTheDocument();
    expect(screen.getByText("Spreadsheet metadata, not regulatory text")).toBeInTheDocument();
    expect(screen.getByText(/NPRM · Proposed rule \(not an enforceable AD\)/)).toBeInTheDocument();
    expect(screen.getByText("Source text for human review")).toBeInTheDocument();
  });
  it("renders NEEDS_MORE_INFORMATION with missing items", () => {
    render(<AnswerPanel response={R(needs)} onOpenCitation={noop} />);
    expect(screen.getByText("NEEDS MORE INFORMATION")).toBeInTheDocument();
    expect(within(screen.getByTestId("missing-info")).getByText("Aircraft model")).toBeInTheDocument();
  });
  it("renders ABSTAINED with reason and labelled did-you-mean", () => {
    render(<AnswerPanel response={R(abstained)} onOpenCitation={noop} />);
    expect(screen.getByText("ABSTAINED")).toBeInTheDocument();
    expect(screen.getByText(/Not in indexed dataset/)).toBeInTheDocument();
    expect(screen.getByText(/DIFFERENT directives/)).toBeInTheDocument();
  });
  it("UNKNOWN shows 'Applicability not determined' and never 'not applicable'", () => {
    const { container } = render(<AnswerPanel response={R(answered)} onOpenCitation={noop} />);
    const b = screen.getByTestId("applicability-badge");
    expect(b).toHaveAttribute("data-value", "UNKNOWN");
    expect(within(b).getByText("Applicability not determined")).toBeInTheDocument();
    expect(b.textContent?.toLowerCase()).not.toContain("not applicable");
    expect(container.textContent?.toLowerCase()).not.toContain("not applicable");
  });
  it("shows NOT verified badge when flag is false, hides it when true", () => {
    const { unmount } = render(<AnswerPanel response={R(answered)} onOpenCitation={noop} />);
    expect(screen.getByText("Current authoritative status NOT verified")).toBeInTheDocument();
    unmount();
    const r = R(JSON.parse(JSON.stringify(answered)));
    r.revision!.current_authoritative_status_verified = true;
    render(<AnswerPanel response={r} onOpenCitation={noop} />);
    expect(screen.queryByText("Current authoritative status NOT verified")).toBeNull();
  });
  it("disclaimer is present for every status, even if the response omits it", () => {
    for (const f of [answered, needs, abstained]) {
      const r = R({ ...f, disclaimer: "" });
      const { unmount } = render(<AnswerPanel response={r} onOpenCitation={noop} />);
      expect(screen.getByTestId("disclaimer")).toHaveTextContent(/Decision support only/);
      unmount();
    }
  });
  it("candidate revision edges are labelled unverified", () => {
    render(<AnswerPanel response={R(answered)} onOpenCitation={noop} />);
    expect(screen.getByText(/unverified — relationship not confirmed/)).toBeInTheDocument();
  });
});

describe("findQuote", () => {
  it("matches across hyphenation and whitespace", () => {
    const page = "we propose to require inspec-\ntion of widget\n  brackets on all airplanes";
    const m = findQuote(page, "propose to require inspection of widget brackets");
    expect(m).not.toBeNull();
    expect(page.slice(m![0], m![1])).toContain("brackets");
  });
  it("returns null when absent", () => {
    expect(findQuote("completely different text here", "propose to require inspection of widget brackets")).toBeNull();
  });
});

describe("final-rule applicability", () => {
  const withFinal = () => {
    const base = answered as unknown as QueryResponse;
    return R({
      ...base,
      applicability: { ...base.applicability, value: "APPLICABLE", label: "Applicable under the proposed rule", basis: "PROPOSED_RULE" },
      final_rule_docnum: "2022-08852",
      final_rule_applicability: {
        ...base.applicability, value: "APPLICABLE", basis: "FINAL_RULE", label: "Applicable under the published final rule",
        template_text: "the AD as published in this final rule applies to PA-34-200", explanation: [], missing: [],
      },
    });
  };
  it("shows proposed and final cards side by side with neutral styling", () => {
    render(<AnswerPanel response={withFinal()} onOpenCitation={noop} />);
    const container = screen.getByTestId("applicability-pair");
    expect(screen.getByRole("heading", { name: "Proposed rule" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Published final rule (FR 2022-08852)" })).toBeInTheDocument();
    expect(within(screen.getByTestId("card-final")).getByText("Applicable under the published final rule")).toBeInTheDocument();
    expect(screen.getByTestId("cell-final-applicability")).toBeInTheDocument();
    for (const b of screen.getAllByTestId("applicability-badge")) expect(b.className).not.toMatch(/green|emerald/);
    expect(screen.getByTestId("cell-final-applicability").className).not.toMatch(/green|emerald/);
    expect(container.textContent?.toLowerCase()).not.toContain("compliant");
  });
  it("shows a single card when there is no final rule", () => {
    render(<AnswerPanel response={R(answered)} onOpenCitation={noop} />);
    expect(screen.queryByTestId("card-final")).toBeNull();
  });
});
