from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb


_SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b("
    r"attach|detach|copy|create|drop|alter|insert|update|delete|merge|"
    r"pragma|install|load|export|import|call|execute|set|"
    r"read_parquet|read_json|httpfs|"
    r"shell|system"
    r")\b",
    re.IGNORECASE,
)


class UnsafeSqlError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetProfile:
    columns: list[str]
    types: dict[str, str]
    row_count: int
    sample_rows: list[dict[str, Any]]


def _json_safe_value(v: Any) -> Any:
    # pandas.Timestamp is a datetime subclass; this also covers date/datetime.
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    # duckdb / pandas may emit numpy scalar types, which generally cast cleanly
    try:
        import numpy as np  # type: ignore

        if isinstance(v, (np.generic,)):
            return v.item()
    except Exception:
        pass

    return v


def _json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: _json_safe_value(v) for k, v in r.items()})
    return out


def _validate_sql(sql: str) -> str:
    if not _SELECT_ONLY.search(sql):
        raise UnsafeSqlError("Only SELECT statements are allowed.")
    m = _FORBIDDEN.search(sql)
    if m:
        raise UnsafeSqlError(f"SQL contains forbidden token: {m.group(0)!r}")
    if ";" in sql.strip().rstrip(";"):
        # Disallow multi-statement
        raise UnsafeSqlError("Only a single SELECT statement is allowed per query.")
    return sql.strip().rstrip(";")


def profile_csv(csv_path: Path, sample_limit: int = 10) -> DatasetProfile:
    con = duckdb.connect(database=":memory:")
    try:
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_csv_auto('{str(csv_path)}');")
        # types
        info = con.execute("DESCRIBE t").fetchall()
        types = {row[0]: row[1] for row in info}
        columns = [row[0] for row in info]
        row_count = int(con.execute("SELECT COUNT(*) FROM t").fetchone()[0])
        sample = con.execute(
            "SELECT * FROM t LIMIT ?",
            [int(sample_limit)],
        ).fetchdf()
        sample_rows = _json_safe_rows(sample.to_dict(orient="records"))
        return DatasetProfile(columns=columns, types=types, row_count=row_count, sample_rows=sample_rows)
    finally:
        con.close()


def run_query_over_csv(
    csv_path: Path,
    sql: str,
    *,
    max_rows: int = 5000,
) -> list[dict[str, Any]]:
    sql = _validate_sql(sql)

    con = duckdb.connect(database=":memory:")
    try:
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_csv_auto('{str(csv_path)}');")
        limited_sql = f"SELECT * FROM ({sql}) q LIMIT {int(max_rows)}"
        df = con.execute(limited_sql).fetchdf()
        return _json_safe_rows(df.to_dict(orient="records"))
    finally:
        con.close()

