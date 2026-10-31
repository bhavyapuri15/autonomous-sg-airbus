import { render, screen } from "@testing-library/react";
import { ThinkingDots } from "@/components/fx/ThinkingDots";
import { LineChart } from "@/components/fx/LineChart";
import { ApplicabilityBadge } from "@/components/Badges";
import { ApplicabilityLegend } from "@/components/ApplicabilityLegend";
import { EvaluationDashboard } from "@/components/EvaluationDashboard";
import { latestWith, parseRuns } from "@/lib/evaluation";

describe("ThinkingDots", () => {
  it("renders only while pending, with the exact text", () => {
    const { rerender } = render(<ThinkingDots pending={false} />);
    expect(screen.queryByTestId("thinking-dots")).toBeNull();
    rerender(<ThinkingDots pending />);
    expect(screen.getByText("Retrieving and verifying evidence...")).toBeInTheDocument();
    rerender(<ThinkingDots pending={false} />);
    expect(screen.queryByTestId("thinking-dots")).toBeNull();
  });
});

describe("Applicability label rules", () => {
  it("UNKNOWN reads 'Applicability not determined' in amber, never green, even if the API label differs", () => {
    const { container } = render(<ApplicabilityBadge value="UNKNOWN" label="Applicable" />);
    expect(screen.getByText("Applicability not determined")).toBeInTheDocument();
    expect(container.innerHTML).toContain("amber");
    expect(container.innerHTML).not.toMatch(/green|emerald|lime/);
  });
  it("APPLICABLE uses the API label and blue", () => {
    const { container } = render(<ApplicabilityBadge value="APPLICABLE" label="Applicable under the proposed rule" />);
    expect(screen.getByText("Applicable under the proposed rule")).toBeInTheDocument();
    expect(container.innerHTML).toContain("blue");
    expect(container.innerHTML).not.toMatch(/green|emerald|lime/);
  });
  it("legend lists the three outcomes without green", () => {
    const { container } = render(<ApplicabilityLegend />);
    expect(screen.getByText("Applicable under the proposed rule")).toBeInTheDocument();
    expect(screen.getByText("Not applicable under the proposed rule")).toBeInTheDocument();
    expect(screen.getByText("Applicability not determined")).toBeInTheDocument();
    expect(container.innerHTML).not.toMatch(/green|emerald|lime/);
  });
});

describe("LineChart", () => {
  const s = [{ id: "a", name: "A", color: "#2563eb", points: [{ x: "r1", y: 0.5 }, { x: "r2", y: null }, { x: "r3", y: 0.7 }] }];
  it("renders one point per measured run and none for gaps", () => {
    render(<LineChart title="t" series={s} xLabels={["r1", "r2", "r3"]} xLabel="run" yLabel="score" />);
    expect(screen.getAllByTestId("line-point")).toHaveLength(2);
  });
  it("table view says Not measured for the gap", () => {
    render(<LineChart title="t" series={s} xLabels={["r1", "r2", "r3"]} xLabel="run" yLabel="score" />);
    expect(screen.getByText("Not measured")).toBeInTheDocument();
  });
});

const runs = parseRuns([
  { file: "1_dev.json", split: "dev", timestamp: "2026-10-31T10:00:00", families: ["F2"], runtime_s: 1, metrics: { F2: { n: 42, doc_recall_at5: 0.8, doc_mrr_at10: 0.6 } } },
  { file: "2_dev.json", split: "dev", timestamp: "2026-10-31T11:00:00", families: ["F7"], runtime_s: 1, metrics: { F7: { abstention: { f1: 0.9, n: 50 } } } },
]);
describe("evaluation helpers", () => {
  it("takes the most recent run that contains the family, never inventing values", () => {
    expect(latestWith(runs, "F2.doc_recall_at5", "F2.n")).toMatchObject({ value: 0.8, n: 42 });
    expect(latestWith(runs, "F1.acc_at1", "F1.n").value).toBeNull();
  });
  it("dashboard shows applicability accuracy as Not measured", () => {
    render(<EvaluationDashboard runs={runs} />);
    expect(screen.getByLabelText("Applicability accuracy")).toHaveTextContent("Not measured");
    expect(screen.getAllByTestId("line-point")).toHaveLength(2); // recall + mrr from the one run that measured F2
  });
});
