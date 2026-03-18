from __future__ import annotations

import json
from typing import Any


def system_prompt(*, dataset_profile: dict[str, Any]) -> str:
    return (
        "You are an analytics engineer and BI assistant.\n"
        "You MUST only use fields that exist in the provided dataset profile.\n"
        "If the user request is ambiguous, ask 1-3 short clarification questions.\n"
        "If the user request cannot be answered from the available fields, say so explicitly.\n"
        "\n"
        "Dataset profile (JSON):\n"
        f"{json.dumps(dataset_profile, ensure_ascii=False, default=str)}\n"
    )


QUERY_PLAN_INSTRUCTIONS = """\
Return ONLY valid JSON matching this schema:
{
  "type": "query_plan" | "clarification_needed" | "cannot_answer",
  "questions": string[] (only if clarification_needed),
  "reason": string (only if cannot_answer),
  "missing_fields": string[] (only if cannot_answer),
  "sql": string (only if query_plan),
  "explanation": string (only if query_plan),
  "assumptions": string[] (only if query_plan)
}

SQL rules:
- Use DuckDB SQL.
- Query from a table/view named t.
- Only SELECT (no DDL/DML).
- Prefer explicit column names, and alias computed fields.
"""

MULTI_CHART_QUERY_INSTRUCTIONS = """\
Return ONLY valid JSON.

If you can answer, return exactly this shape:
{
  "charts": [
    {
      "title": string,
      "sql": string,
      "chart": "line"|"bar"|"pie",
      "x": string,
      "y": string
    }
  ]
}

If the user request is ambiguous, return:
{
  "type": "clarification_needed",
  "questions": string[]
}

If the request cannot be answered from available fields, return:
{
  "type": "cannot_answer",
  "reason": string,
  "missing_fields": string[]
}

SQL rules (for each charts[i].sql):
- Use DuckDB SQL.
- Query from a table/view named t.
- Only SELECT (no DDL/DML).
- Prefer explicit column names, and alias computed fields.

Axis rules:
- charts[i].x should be the grouping column (e.g., month, region, product).
- charts[i].y should be the aggregated value column (e.g., SUM(revenue) AS revenue).
"""


DASHBOARD_SPEC_INSTRUCTIONS = """\
Return ONLY valid JSON matching this schema:
{
  "type": "dashboard_spec",
  "title": string,
  "summary": string,
  "tiles": [
    {
      "id": string,
      "chart_type": "line"|"bar"|"area"|"scatter"|"pie"|"table",
      "title": string,
      "description": string,
      "encoding": {"x": string|null, "y": string|null, "color": string|null, "size": string|null, "text": string|null},
      "options": {"stacked": boolean|null, "sort": "asc"|"desc"|null, "topK": number|null}
    }
  ]
}

Guidelines:
- Keep output short and guaranteed to fit: MAX 3 tiles, short titles/descriptions.
- Time series: line/area.
- Ranking/categorical: bar.
- Parts-of-whole: pie (only when categories <= 8) otherwise stacked bar.
- If result is already aggregated, do NOT propose extra aggregation in the frontend.
"""

