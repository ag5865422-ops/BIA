from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    line = "line"
    bar = "bar"
    area = "area"
    scatter = "scatter"
    pie = "pie"
    table = "table"


class TileEncoding(BaseModel):
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    text: str | None = None


class TileOptions(BaseModel):
    stacked: bool | None = None
    sort: Literal["asc", "desc"] | None = None
    topK: int | None = Field(default=None, ge=1, le=50)


class DashboardTile(BaseModel):
    id: str
    chart_type: ChartType
    title: str
    description: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    encoding: TileEncoding = Field(default_factory=TileEncoding)
    options: TileOptions = Field(default_factory=TileOptions)


class DashboardSpec(BaseModel):
    title: str
    summary: str | None = None
    tiles: list[DashboardTile] = Field(default_factory=list)


class ClarificationNeeded(BaseModel):
    type: Literal["clarification_needed"] = "clarification_needed"
    questions: list[str] = Field(default_factory=list)


class CannotAnswer(BaseModel):
    type: Literal["cannot_answer"] = "cannot_answer"
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


ChartResultType = Literal["line", "bar", "pie", "table"]


class ChartResult(BaseModel):
    title: str
    chart: ChartResultType
    x: str | None = None
    y: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    type: Literal["dashboard"] = "dashboard"
    session_id: str
    dataset_id: str
    sql: str
    explanation: str | None = None
    dashboard: DashboardSpec
    charts: list[ChartResult] = Field(default_factory=list)


ChatResponse = DashboardResponse | ClarificationNeeded | CannotAnswer


class UploadDatasetResponse(BaseModel):
    dataset_id: str
    filename: str
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str | None = None
    dataset_id: str
    message: str

