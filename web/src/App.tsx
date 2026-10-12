import { useEffect, useRef, useState } from "react";
import { getJob, isFinal, submitFile, submitText, type Job } from "./api";
import { ReportView } from "./ReportView";

const POLL_MS = 2000;
const HISTORY_KEY = "hakem.history";

type HistoryEntry = { id: string; title: string };

function loadHistory(): HistoryEntry[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, 10)));
  } catch {
    /* storage unavailable: history is a convenience only */
  }
}

export default function App() {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!job || isFinal(job.status)) return;
    timer.current = window.setTimeout(async () => {
      try {
        setJob(await getJob(job.id));
      } catch (e) {
        setError((e as Error).message);
      }
    }, POLL_MS);
    return () => window.clearTimeout(timer.current);
  }, [job]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = file ? await submitFile(file, title) : await submitText(title.trim(), text);
      setJob(created);
      const next = [{ id: created.id, title: created.title }, ...history.filter((h) => h.id !== created.id)];
      setHistory(next);
      saveHistory(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    setError(null);
    try {
      setJob(await getJob(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const canSubmit = !busy && (file !== null || (title.trim() !== "" && text.trim().length >= 200));

  return (
    <main>
      <header>
        <h1>Hakem</h1>
        <p className="muted">Pre-submission feedback for scholarly manuscripts: structural checks plus an LLM review.</p>
      </header>

      <form className="card" onSubmit={onSubmit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Manuscript title" />
        </label>
        <label>
          Manuscript text (Markdown or plain text)
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            disabled={file !== null}
            placeholder="Paste the full manuscript, including the reference list…"
          />
        </label>
        <label className="file">
          …or upload a .md / .txt file
          <input type="file" accept=".md,.markdown,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <button type="submit" disabled={!canSubmit}>{busy ? "Submitting…" : "Analyse"}</button>
        {error && <p className="error" role="alert">{error}</p>}
      </form>

      {job && (
        <>
          <h2>{job.title}</h2>
          <ReportView job={job} />
        </>
      )}

      {history.length > 0 && (
        <aside className="card">
          <h3>Recent</h3>
          <ul className="history">
            {history.map((h) => (
              <li key={h.id}>
                <button type="button" className="link" onClick={() => open(h.id)}>{h.title}</button>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </main>
  );
}
