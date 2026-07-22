from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class SearchQuery(BaseModel):
    """
    [CDA-002] SearchQuery input boundary schema.
    Enforces required search parameter structures and query modes.
    """
    artist: str = Field(..., min_length=1, description="Target artist name")
    track: str = Field(..., min_length=1, description="Target track name")
    album: Optional[str] = Field(None, description="Optional target album")
    mode: str = Field("A", description="Search query generation mode")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        upper_v = v.upper().strip()
        if upper_v not in ("A", "B", "C"):
            raise ValueError("Search mode must be 'A', 'B', or 'C'")
        return upper_v


class SlskdResult(BaseModel):
    """
    [CDA-002] SlskdResult output boundary schema.
    Validates files returned by the Slskd client.
    """
    filename: str = Field(..., min_length=1, description="Full filepath of the candidate")
    size: int = Field(..., ge=0, description="File size in bytes")
    username: str = Field(..., min_length=1, description="Slskd peer sharing the file")
    format: str = Field(..., description="Audio file extension")
    bitrate: Optional[int] = Field(0, ge=0, description="Audio bitrate")
    sample_rate: Optional[int] = Field(0, ge=0, description="Audio sample rate in Hz")
    queue_length: int = Field(0, ge=0, description="Number of transfers in the peer's queue")

    # Optional enriched fields for SPA search engine results
    score: Optional[int] = Field(0, description="Confidence score")
    parsed_artist: Optional[str] = Field(None)
    parsed_track: Optional[str] = Field(None)
    parsed_album: Optional[str] = Field(None)
    parsed_year: Optional[int] = Field(None)
    beets_confidence: Optional[bool] = Field(False)

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        clean_v = v.lower().strip().lstrip(".")
        allowed = {"mp3", "flac", "wav", "m4a", "ogg", "alac", "wma", "aac", "aiff", "ape"}
        if clean_v not in allowed:
            raise ValueError(f"Unsupported audio format: {clean_v}. Allowed: {allowed}")
        return clean_v


class TelemetryData(BaseModel):
    """
    [CDA-002] TelemetryData schema for search/retrieval execution tracking.
    """
    autocomplete_latency: float = Field(..., ge=0.0)
    search_duration: float = Field(..., ge=0.0)
    ranking_duration: float = Field(..., ge=0.0)
    mb_requests: int = Field(..., ge=0)
    mb_enrich_time: float = Field(..., ge=0.0)
