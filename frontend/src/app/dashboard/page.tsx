"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { chat } from "@/lib/api";
import type { ChatResponse, DashboardResponse } from "@/lib/types";
import { ChartTile } from "@/components/ChartTile";

function useLocalStorageString(key: string) {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    setValue(localStorage.getItem(key));
  }, [key]);
  return { value, setValue };
}

export default function DashboardPage() {
  const { value: datasetId } = useLocalStorageString("datasetId");
  const { value: datasetFilename } = useLocalStorageString("datasetFilename");
  const { value: sessionId, setValue: setSessionId } = useLocalStorageString("sessionId");

  const [message, setMessage] = useState("");
  const [busyStep, setBusyStep] = useState<0 | 1 | 2 | 3>(0);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ChatResponse | null>(null);

  const dashboard = useMemo(() => {
    if (!resp || resp.type !== "dashboard") return null;
    return resp as DashboardResponse;
  }, [resp]);

  const tiles = useMemo(() => {
    if (!dashboard) return [];
    if (dashboard.charts?.length) {
      return dashboard.charts.map((c, idx) => ({
        id: `chart_${idx}`,
        chart_type: c.chart,
        title: c.title,
        description: null,
        data: c.data ?? [],
        encoding: { x: c.x ?? null, y: c.y ?? null },
        options: {}
      }));
    }
    return dashboard.dashboard.tiles;
  }, [dashboard]);

  async function onSend() {
    setError(null);
    if (!datasetId) {
      setError("No dataset selected. Upload a CSV first.");
      return;
    }
    if (!message.trim()) return;
    setBusyStep(1);
    try {
      setBusyStep(2);
      const out = await chat({ sessionId, datasetId, message: message.trim() });
      setResp(out);
      if (out.type === "dashboard") {
        localStorage.setItem("sessionId", out.session_id);
        setSessionId(out.session_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyStep(0);
    }
  }

  return (
    <main className="container">
      <div className="header">
        <div className="brand">
          <div>
            <div style={{ fontWeight: 800, fontSize: 18 }}>Dashboard</div>
            <div className="muted">
              Dataset: <span className="mono">{datasetFilename ?? datasetId ?? "none"}</span>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Link className="btn" href="/">
            Upload new CSV
          </Link>
        </div>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="cardInner">
          <div className="steps" style={{ marginBottom: 10 }}>
            <span className={`step ${busyStep === 1 ? "stepActive" : ""}`}>Understanding</span>
            <span className={`step ${busyStep === 2 ? "stepActive" : ""}`}>Querying</span>
            <span className={`step ${busyStep === 3 ? "stepActive" : ""}`}>Building dashboard</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10 }}>
            <textarea
              className="textarea"
              placeholder="Ask a business question… (e.g., Show monthly revenue for Q3 by region)"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              disabled={busyStep !== 0}
            />
            <button className="btn btnPrimary" onClick={onSend} disabled={busyStep !== 0 || !datasetId}>
              {busyStep !== 0 ? "Working..." : "Generate"}
            </button>
          </div>

          {resp?.type === "clarification_needed" ? (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Clarification needed</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {resp.questions.map((q, i) => (
                  <li key={i} className="muted">
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {resp?.type === "cannot_answer" ? (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Cannot answer from this dataset</div>
              <div className="muted">{resp.reason}</div>
              {resp.missing_fields?.length ? (
                <div className="muted">
                  Missing: <span className="mono">{resp.missing_fields.join(", ")}</span>
                </div>
              ) : null}
            </div>
          ) : null}

          {error ? (
            <div style={{ marginTop: 12, color: "var(--danger)" }}>
              <span className="mono">{error}</span>
            </div>
          ) : null}
        </div>
      </section>

      {dashboard ? (
        <>
          <section className="card" style={{ marginBottom: 16 }}>
            <div className="cardInner">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontWeight: 900, fontSize: 20 }}>{dashboard.dashboard.title}</div>
                  {dashboard.dashboard.summary ? <div className="muted">{dashboard.dashboard.summary}</div> : null}
                </div>
                <div className="pill">
                  SQL: <span className="mono" style={{ marginLeft: 8 }}>{dashboard.sql}</span>
                </div>
              </div>
              {dashboard.explanation ? (
                <div className="muted" style={{ marginTop: 10 }}>
                  {dashboard.explanation}
                </div>
              ) : null}
            </div>
          </section>

          <section className="grid">
            {tiles.map((t) => (
              <div className="tile" key={t.id}>
                <ChartTile tile={t} />
              </div>
            ))}
          </section>
        </>
      ) : (
        <section className="card">
          <div className="cardInner">
            <div style={{ fontWeight: 700, marginBottom: 8 }}>No dashboard yet</div>
            <div className="muted">
              Upload a CSV, then ask a question to generate charts. Try:{" "}
              <span className="mono">Show monthly revenue for Q3 broken down by region</span>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

