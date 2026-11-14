"""Pydantic request/response models for the public API.

The scientific payloads are deeply nested and deliberately kept as typed
dictionaries in the service layer. These models validate *inputs* strictly and
document the stable top-level response shape for OpenAPI consumers.
"""

from __future__ import annotations

from datetime import datetime as DateTime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_MISSION_TIME = DateTime.fromisoformat("2026-11-24T12:00:00+00:00")


class PrioritiesModel(BaseModel):
    power: float = Field(35.0, ge=0, le=100, description="Weight for solar power / illumination")
    comms: float = Field(30.0, ge=0, le=100, description="Weight for direct-to-Earth geometry")
    terrain: float = Field(20.0, ge=0, le=100, description="Weight for slope, roughness and sky view")
    timing: float = Field(15.0, ge=0, le=100, description="Weight for conditions at landing time")

    @model_validator(mode="after")
    def _not_all_zero(self) -> "PrioritiesModel":
        if self.power + self.comms + self.terrain + self.timing <= 0:
            raise ValueError("At least one priority weight must be greater than zero")
        return self


class AnalyzeRequest(BaseModel):
    site_id: str | None = Field(None, description="Candidate site id; overrides lat/lon when set")
    lat: float | None = Field(None, ge=-90, le=90, description="Selenographic latitude (deg, south negative)")
    lon: float | None = Field(None, ge=-360, le=360, description="Selenographic east longitude (deg)")
    datetime: DateTime | None = Field(None, description="Landing instant in UTC (ISO 8601)")
    window_days: float = Field(7.0, gt=0, le=30, description="Analysis window length in days")
    step_minutes: int = Field(10, ge=1, le=120, description="Timeline sampling step in minutes")
    priorities: PrioritiesModel = Field(default_factory=PrioritiesModel)
    name: str | None = Field(None, max_length=120, description="Optional label for custom coordinates")
    include_timeline: bool = True

    @model_validator(mode="after")
    def _need_location(self) -> "AnalyzeRequest":
        if self.site_id and self.lat is not None:
            # Site ids win; this is documented rather than an error so the UI can
            # keep a stale coordinate while switching to a preset.
            return self
        if not self.site_id and (self.lat is None or self.lon is None):
            raise ValueError("Provide either site_id or both lat and lon")
        return self

    @field_validator("datetime")
    @classmethod
    def _aware(cls, value: DateTime | None) -> DateTime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=DEFAULT_MISSION_TIME.tzinfo)
        return value


class CompareScenario(BaseModel):
    site_id: str | None = None
    name: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-360, le=360)
    datetime: DateTime | None = None
    window_days: float = Field(7.0, gt=0, le=30)
    step_minutes: int = Field(15, ge=1, le=120)

    @model_validator(mode="after")
    def _need_location(self) -> "CompareScenario":
        if not self.site_id and (self.lat is None or self.lon is None):
            raise ValueError("Each scenario needs site_id or both lat and lon")
        return self

    @field_validator("datetime")
    @classmethod
    def _aware(cls, value: DateTime | None) -> DateTime | None:
        if value is None:
            return None
        return value.replace(tzinfo=DEFAULT_MISSION_TIME.tzinfo) if value.tzinfo is None else value


class CompareRequest(BaseModel):
    scenarios: list[CompareScenario] = Field(..., min_length=2, max_length=6)
    priorities: PrioritiesModel = Field(default_factory=PrioritiesModel)
    include_timelines: bool = False


class SeriesRequest(BaseModel):
    site_id: str | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-360, le=360)
    start: DateTime | None = None
    end: DateTime | None = None
    step_minutes: int = Field(30, ge=1, le=120)

    @model_validator(mode="after")
    def _need_location(self) -> "SeriesRequest":
        if not self.site_id and (self.lat is None or self.lon is None):
            raise ValueError("Provide either site_id or both lat and lon")
        if self.start and self.end and self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ReportRequest(AnalyzeRequest):
    include_timeline: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    version: str
    environment: str
    terrain_available: bool
    dem_product: str
    horizons_enabled: bool
    default_mission_time_utc: str
    server_time_utc: str


class DataSourceRecord(BaseModel):
    id: str
    name: str
    provider: str
    url: str
    dataset_id: str | None = None
    retrieved_at: str | None = None
    status: str
    units: str
    frame: str
    used_for: str
    limitations: str
    live: bool


class DataSourcesResponse(BaseModel):
    sources: list[DataSourceRecord]
    default_mission_time_utc: str
    generated_at_utc: str
    notes: list[str]


class HorizonsRecord(BaseModel):
    body: Literal["sun", "earth", "moon"]
    time_utc: str
    azimuth_deg: float | None = None
    elevation_deg: float | None = None
    distance_km: float | None = None


class HorizonsCheckResponse(BaseModel):
    status: Literal["live", "cached", "unavailable", "disabled"]
    requested_at_utc: str
    retrieved_at: str | None
    source_url: str
    records: list[HorizonsRecord]
    message: str
    limitations: str


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"


class AnyPayload(BaseModel):
    """OpenAPI placeholder for the rich analysis payload."""

    data: dict[str, Any]
