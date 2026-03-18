from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import orjson
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .llm.openrouter_client import OpenRouterClient, OpenRouterError
from .llm.json_utils import extract_json
from .llm.prompts import (
    DASHBOARD_SPEC_INSTRUCTIONS,
    MULTI_CHART_QUERY_INSTRUCTIONS,
    QUERY_PLAN_INSTRUCTIONS,
    system_prompt,
)
from .models import ChatRequest, ChatResponse, ChartResult, ChartResultType, DashboardSpec, UploadDatasetResponse
from .query.duckdb_engine import UnsafeSqlError, profile_csv, run_query_over_csv


APP_ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = (APP_ROOT / "storage").resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="Conversational BI Backend", version="0.1.0")

_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_env_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=(_env_origins or _default_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _SessionState(dict):
    # Prototype: in-memory store
    pass


SESSIONS: dict[str, _SessionState] = {}


def _dataset_dir(dataset_id: str) -> Path:
    return STORAGE_ROOT / dataset_id


def _dataset_csv_path(dataset_id: str) -> Path:
    return _dataset_dir(dataset_id) / "source.csv"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/datasets/upload", response_model=UploadDatasetResponse)
async def upload_dataset(file: UploadFile = File(...)) -> UploadDatasetResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    dataset_id = uuid.uuid4().hex
    ddir = _dataset_dir(dataset_id)
    ddir.mkdir(parents=True, exist_ok=True)
    out_path = _dataset_csv_path(dataset_id)

    contents = await file.read()
    out_path.write_bytes(contents)

    # Lightweight profiling for UX + prompts (kept minimal here; expanded in query-engine todo)
    try:
        prof = profile_csv(out_path, sample_limit=5)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}") from e

    return UploadDatasetResponse(
        dataset_id=dataset_id,
        filename=file.filename,
        row_count=int(prof.row_count),
        column_count=int(len(prof.columns)),
        columns=[str(c) for c in prof.columns],
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> Any:
    csv_path = _dataset_csv_path(req.dataset_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found. Upload a CSV first.")

    session_id = req.session_id or uuid.uuid4().hex
    SESSIONS.setdefault(session_id, _SessionState(dataset_id=req.dataset_id))

    prof = profile_csv(csv_path, sample_limit=10)
    dataset_profile = {
        "columns": prof.columns,
        "types": prof.types,
        "row_count": prof.row_count,
        "sample_rows": prof.sample_rows,
    }

    sys = system_prompt(dataset_profile=dataset_profile)
    client = OpenRouterClient.from_env()

    def _coerce_chart_type(v: Any) -> ChartResultType:
        s = str(v or "").strip().lower()
        if s in ("line", "bar", "pie"):
            return s  # type: ignore[return-value]
        return "bar"

    async def _llm_query_plan_multi() -> dict[str, Any]:
        user_1 = f"User request:\n{req.message}\n\n{MULTI_CHART_QUERY_INSTRUCTIONS}"
        text_1 = await client.generate_text(system=sys, user=user_1)
        return extract_json(text_1)

    async def _llm_query_plan_legacy(*, rejection: str | None = None) -> dict[str, Any]:
        if rejection:
            user_1 = (
                f"User request:\n{req.message}\n\n"
                f"Your previous SQL was rejected: {rejection}\n"
                "Rewrite the SQL to comply with the rules.\n"
                "- Query ONLY from the existing table/view named t\n"
                "- Do NOT use read_csv_auto/read_csv or any external file reference\n\n"
                f"{QUERY_PLAN_INSTRUCTIONS}"
            )
        else:
            user_1 = f"User request:\n{req.message}\n\n{QUERY_PLAN_INSTRUCTIONS}"
        text_1 = await client.generate_text(system=sys, user=user_1)
        return extract_json(text_1)

    try:
        obj_1 = await _llm_query_plan_multi()
    except OpenRouterError as e:
        msg = str(e)
        if "OpenRouter API error 429" in msg:
            raise HTTPException(status_code=429, detail=msg) from e
        if "OpenRouter API error 503" in msg:
            raise HTTPException(status_code=503, detail=msg) from e
        raise HTTPException(status_code=500, detail=msg) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not parse LLM output: {e}.",
        ) from e

    if obj_1.get("type") == "clarification_needed":
        return {"type": "clarification_needed", "questions": obj_1.get("questions", [])}
    if obj_1.get("type") == "cannot_answer":
        return {
            "type": "cannot_answer",
            "reason": obj_1.get("reason", "Cannot answer from available data."),
            "missing_fields": obj_1.get("missing_fields", []),
        }
    charts_obj = obj_1.get("charts")
    if isinstance(charts_obj, list) and charts_obj:
        charts_out: list[ChartResult] = []
        tiles: list[dict[str, Any]] = []

        async def _execute_multi(obj: dict[str, Any]) -> list[ChartResult]:
            raw = obj.get("charts")
            if not isinstance(raw, list) or not raw:
                raise ValueError("Missing charts array.")
            out: list[ChartResult] = []
            for i, c in enumerate(raw):
                if not isinstance(c, dict):
                    raise ValueError(f"charts[{i}] must be an object.")
                title = str(c.get("title", f"Chart {i+1}")).strip() or f"Chart {i+1}"
                sql_i = str(c.get("sql", "")).strip()
                chart_type = _coerce_chart_type(c.get("chart"))
                x_i = str(c.get("x", "")).strip()
                y_i = str(c.get("y", "")).strip()
                if not sql_i:
                    raise ValueError(f"charts[{i}].sql is required.")
                if not x_i:
                    raise ValueError(f"charts[{i}].x is required.")
                if not y_i:
                    raise ValueError(f"charts[{i}].y is required.")
                data_i = run_query_over_csv(csv_path, sql_i, max_rows=5000)
                out.append(ChartResult(title=title, chart=chart_type, x=x_i, y=y_i, data=data_i))
            return out

        try:
            charts_out = await _execute_multi(obj_1)
        except UnsafeSqlError as e:
            # Retry once: ask for corrected charts JSON.
            try:
                user_retry = (
                    f"User request:\n{req.message}\n\n"
                    f"One of your chart SQL queries was rejected: {e}\n"
                    "Return corrected JSON in the same format.\n"
                    "- Query ONLY from the existing table/view named t\n"
                    "- Do NOT use read_csv_auto/read_csv or any external file reference\n"
                    "- Each charts[i].sql must be a single SELECT statement\n\n"
                    f"{MULTI_CHART_QUERY_INSTRUCTIONS}"
                )
                text_retry = await client.generate_text(system=sys, user=user_retry)
                obj_retry = extract_json(text_retry)
                charts_out = await _execute_multi(obj_retry)
            except Exception as e2:
                return {
                    "type": "cannot_answer",
                    "reason": f"Generated SQL was rejected by safety checks: {e2}",
                    "missing_fields": [],
                }
        except Exception as e:
            return {
                "type": "cannot_answer",
                "reason": f"Query failed: {e}",
                "missing_fields": [],
            }

        for idx, c in enumerate(charts_out):
            tile_id = uuid.uuid4().hex
            tiles.append(
                {
                    "id": tile_id,
                    "chart_type": c.chart,
                    "title": c.title,
                    "description": None,
                    "data": c.data,
                    "encoding": {"x": c.x, "y": c.y},
                    "options": {},
                }
            )

        dashboard = DashboardSpec(title="Dashboard", summary=None, tiles=tiles)
        sql_summary = "; ".join([f"[{c.title}] {len(c.data)} rows" for c in charts_out])

        SESSIONS[session_id].update(
            {
                "dataset_id": req.dataset_id,
                "last_message": req.message,
                "last_sql": sql_summary,
            }
        )

        return {
            "type": "dashboard",
            "session_id": session_id,
            "dataset_id": req.dataset_id,
            "sql": sql_summary,
            "explanation": None,
            "dashboard": dashboard.model_dump(),
            "charts": [c.model_dump() for c in charts_out],
        }

    # Legacy single-query path (backwards compatible)
    if obj_1.get("type") != "query_plan":
        # If multi-chart prompting returned something unexpected, fall back to legacy instruction set.
        try:
            obj_1 = await _llm_query_plan_legacy()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected LLM response shape: {e}") from e
        if obj_1.get("type") == "clarification_needed":
            return {"type": "clarification_needed", "questions": obj_1.get("questions", [])}
        if obj_1.get("type") == "cannot_answer":
            return {
                "type": "cannot_answer",
                "reason": obj_1.get("reason", "Cannot answer from available data."),
                "missing_fields": obj_1.get("missing_fields", []),
            }
        if obj_1.get("type") != "query_plan":
            raise HTTPException(status_code=500, detail=f"Unexpected LLM response type: {obj_1.get('type')}")

    sql = str(obj_1.get("sql", "")).strip()
    explanation = str(obj_1.get("explanation", "")).strip() or None

    try:
        rows = run_query_over_csv(csv_path, sql, max_rows=5000)
    except UnsafeSqlError as e:
        try:
            obj_retry = await _llm_query_plan_legacy(rejection=str(e))
        except Exception:
            return {
                "type": "cannot_answer",
                "reason": f"Generated SQL was rejected by safety checks: {e}",
                "missing_fields": [],
            }
        if obj_retry.get("type") != "query_plan":
            return {
                "type": "cannot_answer",
                "reason": f"Generated SQL was rejected by safety checks: {e}",
                "missing_fields": [],
            }

        sql = str(obj_retry.get("sql", "")).strip()
        explanation = str(obj_retry.get("explanation", "")).strip() or explanation
        try:
            rows = run_query_over_csv(csv_path, sql, max_rows=5000)
        except Exception as e2:
            return {
                "type": "cannot_answer",
                "reason": f"Generated SQL was rejected by safety checks: {e2}",
                "missing_fields": [],
            }
    except Exception as e:
        return {
            "type": "cannot_answer",
            "reason": f"Query failed: {e}",
            "missing_fields": [],
        }

    # Step 2: Dashboard spec (no data, only structure)
    user_2 = (
        "Given the user request and the query result sample, propose a dashboard spec.\n\n"
        f"User request:\n{req.message}\n\n"
        f"SQL:\n{sql}\n\n"
        f"Result sample rows (JSON):\n{orjson.dumps(rows[:25]).decode('utf-8')}\n\n"
        f"{DASHBOARD_SPEC_INSTRUCTIONS}"
    )
    try:
        text_2 = await client.generate_text(system=sys, user=user_2)
        obj_2 = extract_json(text_2)
    except OpenRouterError as e:
        msg = str(e)
        if "OpenRouter API error 429" in msg:
            raise HTTPException(status_code=429, detail=msg) from e
        if "OpenRouter API error 503" in msg:
            raise HTTPException(status_code=503, detail=msg) from e
        raise HTTPException(status_code=500, detail=msg) from e
    except Exception as e:
        snippet = ""
        try:
            snippet = (text_2 or "")[:800]
        except Exception:
            snippet = ""
        raise HTTPException(
            status_code=500,
            detail=f"Could not parse LLM output: {e}. Output snippet: {snippet!r}",
        ) from e

    if obj_2.get("type") != "dashboard_spec":
        raise HTTPException(status_code=500, detail=f"Unexpected dashboard spec type: {obj_2.get('type')}")

    # Attach full data to each tile for prototype simplicity.
    # (Later: allow multiple queries/tiles; for now one result set feeds all tiles.)
    tiles = obj_2.get("tiles", []) or []
    for t in tiles:
        t["data"] = rows

    dashboard = DashboardSpec(
        title=obj_2.get("title", "Dashboard"),
        summary=obj_2.get("summary"),
        tiles=tiles,
    )

    SESSIONS[session_id].update(
        {
            "dataset_id": req.dataset_id,
            "last_message": req.message,
            "last_sql": sql,
        }
    )

    return {
        "type": "dashboard",
        "session_id": session_id,
        "dataset_id": req.dataset_id,
        "sql": sql,
        "explanation": explanation,
        "dashboard": dashboard.model_dump(),
        "charts": [
            {
                "title": dashboard.title,
                "chart": "table",
                "x": None,
                "y": None,
                "data": rows,
            }
        ],
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return orjson.loads(orjson.dumps(state))

