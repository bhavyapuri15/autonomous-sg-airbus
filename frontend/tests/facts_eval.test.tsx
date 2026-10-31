import { fireEvent, render, screen } from "@testing-library/react";
import { FactsInput } from "@/components/FactsInput";
import { EvaluationView } from "@/components/EvaluationView";
import { buildFacts, parseMissing } from "@/lib/facts";
import { findShortQuoteSpan } from "@/lib/match";
import { joinModels } from "@/lib/loose";

const MISSING = "free_text:A MAIN CARGO DOOR (MCD) (equipped with a main cargo door (MCD))";

describe("facts", () => {
  it("parses backend 'key (text)' entries", () => {
    expect(parseMissing(MISSING).key).toBe("free_text:A MAIN CARGO DOOR (MCD)");
    expect(parseMissing("part_number_installed:B851 (hoist harness P/N B851)").key).toBe("part_number_installed:B851");
    expect(parseMissing("serial").key).toBe("serial");
  });
  it("buildFacts omits Unknown", () => {
    expect(buildFacts({ "a:x (t)": "yes", "b:y (u)": "no", "c:z (v)": "unknown" })).toEqual({ "a:x": true, "b:y": false });
  });
  it("toggle rows produce the right payload on Re-check", () => {
    const onRecheck = vi.fn();
    render(<FactsInput missing={[MISSING, "modification_incorporated:SB 1 (SB 1 done)"]} onRecheck={onRecheck} />);
    fireEvent.click(screen.getAllByRole("radio", { name: "yes" })[0]);
    fireEvent.click(screen.getAllByRole("radio", { name: "no" })[1]);
    fireEvent.click(screen.getByText("Re-check"));
    expect(onRecheck).toHaveBeenCalledWith({ "free_text:A MAIN CARGO DOOR (MCD)": true, "modification_incorporated:SB 1": false });
  });
  it("defaults to Unknown and sends empty facts", () => {
    const onRecheck = vi.fn();
    render(<FactsInput missing={[MISSING]} onRecheck={onRecheck} />);
    fireEvent.click(screen.getByText("Re-check"));
    expect(onRecheck).toHaveBeenCalledWith({});
  });
});

describe("evaluation", () => {
  it("renders {} as no results", () => {
    render(<EvaluationView data={{}} />);
    expect(screen.getByTestId("no-eval")).toHaveTextContent("No evaluation results yet");
  });
  it("renders nested metrics and failures", () => {
    render(<EvaluationView data={{ split: "dev", timestamp: "t1", metrics: { F3: { n: 2, acc: 0.5, failures: [{ id: "x1", q: "why" }] } } }} />);
    expect(screen.getByTestId("eval-header")).toHaveTextContent("dev");
    expect(screen.getByText("0.5")).toBeInTheDocument();
    expect(screen.getAllByText(/n = 2/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("failure-list")).toBeInTheDocument();
  });
});

describe("misc", () => {
  it("short quote span match", () => {
    expect(findShortQuoteSpan(["foo", "Model AS355NP,", "AS355NP"], "AS355NP")).toBe(1);
    expect(findShortQuoteSpan(["foo"], "AS355NP")).toBe(-1);
  });
  it("truncates models to 6", () => {
    expect(joinModels(["a", "b", "c", "d", "e", "f", "g", "h"])).toBe("a, b, c, d, e, f +2");
  });
});

describe("parseMissing separator format", () => {
  it("splits '<key> :: <label>' even when the key itself ends in a parenthesis", () => {
    const r = parseMissing("free_text:A MAIN CARGO DOOR (MCD) :: equipped with a main cargo door (MCD)");
    expect(r.key).toBe("free_text:A MAIN CARGO DOOR (MCD)");
    expect(r.text).toBe("equipped with a main cargo door (MCD)");
  });
});
