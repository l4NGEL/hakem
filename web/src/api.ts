export type Severity = "high" | "medium" | "low";

export interface Issue {
  code: string;
  severity: Severity;
  message: string;
  line: number | null;
  section: string | null;
}

export interface Comment {
  section: string;
  issue: string;
  suggestion: string;
}

export interface Review {
  language: string;
  summary: string;
  scores: Record<string, number>;
  strengths: string[];
  major_issues: Comment[];
  minor_issues: Comment[];
  injection_attempt_detected: boolean;
  model: string;
}

export interface Report {
  checks: {
    sections: { key: string | null; title: string; line: number }[];
    issues: Issue[];
    stats: Record<string, number | null>;
  };
  review: Review | null;
  review_error: string | null;
  elapsed_ms?: number;
}

export type Status = "QUEUED" | "PROCESSING" | "DONE" | "FAILED";

export interface Job {
  id: string;
  title: string;
  status: Status;
  createdAt: number;
  updatedAt?: number;
  error?: string;
  report?: Report;
}

async function asJob(res: Response): Promise<Job> {
  const body = await res.json().catch(() => null);
  if (!res.ok && !(res.status === 503 && body?.id)) {
    throw new Error(body?.detail ?? body?.message ?? `Request failed (${res.status})`);
  }
  return body as Job;
}

export async function submitText(title: string, text: string): Promise<Job> {
  return asJob(await fetch("/api/manuscripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  }));
}

export async function submitFile(file: File, title: string): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  if (title.trim()) form.append("title", title.trim());
  return asJob(await fetch("/api/manuscripts", { method: "POST", body: form }));
}

export async function getJob(id: string): Promise<Job> {
  return asJob(await fetch(`/api/manuscripts/${id}`));
}

export const isFinal = (s: Status) => s === "DONE" || s === "FAILED";
