"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js-dist-min";

import type { DashboardTile } from "@/lib/types";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

function normalizeNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function normalizeString(v: unknown): string {
  if (v == null) return "";
  return String(v);
}

function pickField(tile: DashboardTile, key: keyof DashboardTile["encoding"]): string | null {
  const raw = tile.encoding?.[key];
  return raw ? String(raw) : null;
}

function applyTopK(tile: DashboardTile, rows: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  const topK = tile.options?.topK ?? null;
  const x = pickField(tile, "x");
  const y = pickField(tile, "y");
  if (!topK || !x || !y) return rows;

  const scored = rows
    .map((r) => ({ r, score: normalizeNumber(r[y]) ?? 0 }))
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map(({ r }) => r);

  return scored;
}

export function ChartTile({ tile }: { tile: DashboardTile }) {
  const xField = pickField(tile, "x");
  const yField = pickField(tile, "y");
  const colorField = pickField(tile, "color");

  const rows = applyTopK(tile, tile.data ?? []);

  if (tile.chart_type === "table") {
    const cols = rows.length ? Object.keys(rows[0]) : [];
    return (
      <div className="card">
        <div className="cardInner">
          <div className="tileHeader">
            <div>
              <div style={{ fontWeight: 700 }}>{tile.title}</div>
              {tile.description ? <div className="muted">{tile.description}</div> : null}
            </div>
            <span className="pill">{rows.length} rows</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {cols.map((c) => (
                    <th
                      key={c}
                      className="mono"
                      style={{
                        textAlign: "left",
                        padding: "8px 10px",
                        borderBottom: "1px solid var(--stroke)",
                        color: "var(--muted)"
                      }}
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 30).map((r, idx) => (
                  <tr key={idx}>
                    {cols.map((c) => (
                      <td key={c} style={{ padding: "8px 10px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                        <span className="mono">{normalizeString(r[c])}</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (!xField || (!yField && tile.chart_type !== "pie")) {
    return (
      <div className="card">
        <div className="cardInner">
          <div style={{ fontWeight: 700 }}>{tile.title}</div>
          <div className="muted">This tile is missing required encodings (x/y).</div>
        </div>
      </div>
    );
  }

  const x = rows.map((r) => normalizeString(r[xField]));
  const y = yField ? rows.map((r) => normalizeNumber(r[yField]) ?? 0) : [];
  const color = colorField ? rows.map((r) => normalizeString(r[colorField])) : undefined;

  const baseLayout: Partial<Layout> = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "rgba(255,255,255,0.86)" },
    margin: { l: 45, r: 20, t: 10, b: 40 },
    xaxis: { gridcolor: "rgba(255,255,255,0.10)", zerolinecolor: "rgba(255,255,255,0.10)" },
    yaxis: { gridcolor: "rgba(255,255,255,0.10)", zerolinecolor: "rgba(255,255,255,0.10)" },
    legend: { orientation: "h" }
  };

  let trace: Partial<Data>[];

  if (tile.chart_type === "pie") {
    const labels = x;
    const values = yField ? y : rows.map(() => 1);
    trace = [
      {
        type: "pie",
        labels,
        values,
        textinfo: "label+percent",
        hoverinfo: "label+value+percent"
      }
    ];
  } else if (tile.chart_type === "scatter") {
    trace = [
      {
        type: "scatter",
        mode: "markers",
        x,
        y,
        marker: { color: color ? color : "rgba(113,247,159,0.9)" }
      }
    ];
  } else if (tile.chart_type === "bar") {
    if (color && colorField) {
      // grouped bars by color field (best-effort)
      const groups = new Map<string, { x: string[]; y: number[] }>();
      rows.forEach((r) => {
        const g = normalizeString(r[colorField]);
        const gx = normalizeString(r[xField]);
        const gy = yField ? (normalizeNumber(r[yField]) ?? 0) : 0;
        const cur = groups.get(g) ?? { x: [], y: [] };
        cur.x.push(gx);
        cur.y.push(gy);
        groups.set(g, cur);
      });
      trace = Array.from(groups.entries()).map(([g, v]) => ({
        type: "bar",
        name: g,
        x: v.x,
        y: v.y
      }));
    } else {
      trace = [
        {
          type: "bar",
          x,
          y,
          marker: { color: "rgba(113,247,159,0.75)" }
        }
      ];
    }
  } else {
    // line/area default
    trace = [
      {
        type: "scatter",
        mode: "lines+markers",
        x,
        y,
        line: { color: "rgba(113,247,159,0.95)", width: 2 },
        marker: { color: "rgba(113,247,159,0.95)", size: 6 },
        fill: tile.chart_type === "area" ? "tozeroy" : undefined
      }
    ];
  }

  return (
    <div className="card">
      <div className="cardInner">
        <div className="tileHeader">
          <div>
            <div style={{ fontWeight: 700 }}>{tile.title}</div>
            {tile.description ? <div className="muted">{tile.description}</div> : null}
          </div>
          <span className="pill">{tile.chart_type}</span>
        </div>
        <div style={{ height: 360 }}>
          <Plot
            data={trace as Data[]}
            layout={baseLayout as Layout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      </div>
    </div>
  );
}

