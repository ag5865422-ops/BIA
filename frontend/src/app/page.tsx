"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { uploadCsv } from "@/lib/api";

const SAMPLE_NAME = "sample_sales.csv";

async function fetchSampleCsvFile(): Promise<File> {
  const res = await fetch(`/${SAMPLE_NAME}`);
  if (!res.ok) throw new Error("Could not load sample dataset.");
  const blob = await res.blob();
  return new File([blob], SAMPLE_NAME, { type: "text/csv" });
}

export default function HomePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filename = useMemo(() => file?.name ?? "No file selected", [file]);

  async function onUpload(selected?: File | null) {
    setError(null);
    const f = selected ?? file;
    if (!f) return;
    setBusy(true);
    try {
      const resp = await uploadCsv(f);
      localStorage.setItem("datasetId", resp.dataset_id);
      localStorage.setItem("datasetFilename", resp.filename);
      localStorage.removeItem("sessionId");
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <div className="header">
        <div className="brand">
          <div className="badge">
            <span>Conversational BI</span>
            <span className="mono">Next.js + FastAPI + DuckDB + Gemini</span>
          </div>
        </div>
        <a className="pill" href="/dashboard">
          Open dashboard →
        </a>
      </div>

      <div className="row">
        <section className="card">
          <div className="cardInner">
            <h2 style={{ margin: "0 0 8px" }}>Upload a CSV</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              The app will infer schema, generate SQL, and render charts from your prompt.
            </p>

            <div style={{ display: "grid", gap: 12 }}>
              <input
                className="input"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                disabled={busy}
              />

              <div className="muted">
                Selected: <span className="mono">{filename}</span>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn btnPrimary" onClick={() => onUpload()} disabled={!file || busy}>
                  {busy ? "Uploading..." : "Upload & Continue"}
                </button>
                <button
                  className="btn"
                  onClick={async () => {
                    setBusy(true);
                    setError(null);
                    try {
                      const sample = await fetchSampleCsvFile();
                      setFile(sample);
                      await onUpload(sample);
                    } catch (e) {
                      setError(e instanceof Error ? e.message : String(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                  disabled={busy}
                >
                  Use sample dataset
                </button>
              </div>

              {error ? (
                <div className="card" style={{ borderColor: "rgba(255,85,122,0.35)", background: "rgba(255,85,122,0.10)" }}>
                  <div className="cardInner">
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Upload failed</div>
                    <div className="mono" style={{ whiteSpace: "pre-wrap" }}>
                      {error}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <aside className="card">
          <div className="cardInner">
            <h3 style={{ margin: "0 0 10px" }}>Try prompts like</h3>
            <div style={{ display: "grid", gap: 10 }}>
              <div className="pill">
                “Show monthly sales revenue for Q3 broken down by region.”
              </div>
              <div className="pill">
                “Highlight the top-performing product category and explain why.”
              </div>
              <div className="pill">
                “Now filter this to only show the East Coast.”
              </div>
            </div>
            <p className="muted" style={{ marginTop: 14 }}>
              If a request is ambiguous, the system will ask targeted clarification questions.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}

