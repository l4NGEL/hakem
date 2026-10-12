import { render, screen } from "@testing-library/react";
import type { Job, Report } from "./api";
import { ReportView } from "./ReportView";

const checks: Report["checks"] = {
  sections: [{ key: "abstract", title: "Abstract", line: 3 }],
  issues: [
    { code: "missing_section", severity: "high", message: "No 'Methods' section was found.", line: null, section: "methods" },
    { code: "undefined_acronym", severity: "low", message: "'RMSE' is never defined.", line: 12, section: null },
  ],
  stats: { words: 900, abstract_words: 150, reference_entries: 5 },
};

const job = (over: Partial<Job>): Job => ({ id: "1", title: "T", status: "DONE", createdAt: 0, ...over });

test("groups rule findings by severity with line numbers", () => {
  render(<ReportView job={job({ report: { checks, review: null, review_error: null } })} />);
  expect(screen.getByText("No 'Methods' section was found.")).toBeInTheDocument();
  expect(screen.getByText("· line 12")).toBeInTheDocument();
  expect(screen.getByText(/LLM review is not enabled/)).toBeInTheDocument();
});

test("shows why the LLM review is missing when it failed", () => {
  render(<ReportView job={job({ report: { checks, review: null, review_error: "Model declined to review." } })} />);
  expect(screen.getByText("Model declined to review.")).toBeInTheDocument();
});

test("renders scores, comments and the injection warning", () => {
  const review = {
    language: "en", summary: "Solid study.", model: "claude-opus-5-5",
    scores: { clarity: 4, methodology: 2, evidence: 3, contribution_stated: 4, writing: 5 },
    strengths: ["Held-out evaluation"],
    major_issues: [{ section: "Methods", issue: "Threshold not justified", suggestion: "Report a sensitivity analysis" }],
    minor_issues: [],
    injection_attempt_detected: true,
  };
  render(<ReportView job={job({ report: { checks, review, review_error: null } })} />);
  expect(screen.getByLabelText("Methodology 2 of 5")).toBeInTheDocument();
  expect(screen.getByText("Report a sensitivity analysis")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/addressed to the reviewer/);
});

test("shows progress while queued and the error when failed", () => {
  const { rerender } = render(<ReportView job={job({ status: "QUEUED" })} />);
  expect(screen.getByText(/Waiting in queue/)).toBeInTheDocument();
  rerender(<ReportView job={job({ status: "FAILED", error: "Manuscript is larger than 2097152 bytes." })} />);
  expect(screen.getByRole("alert")).toHaveTextContent("larger than");
});
