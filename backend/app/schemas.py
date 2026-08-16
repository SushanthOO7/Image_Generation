from enum import StrEnum
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: str
    email: str
    role: str


class GenerationLimitsResponse(BaseModel):
    rate_limit_per_minute: int
    rate_limit_remaining: int
    rate_limit_reset_seconds: int
    concurrent_limit: int
    active_jobs: int


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GenerationStatus(StrEnum):
    queued = "QUEUED"
    generating = "GENERATING"
    completed = "COMPLETED"
    failed = "FAILED"
    cancelled = "CANCELLED"


class GenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3"] = "1:1"
    quality: Literal["fast", "standard", "ultra"] = "fast"
    style: Literal["none", "cinematic", "product", "editorial"] = "none"
    num_outputs: int = Field(default=1, ge=1, le=4)


class GenerationSubmitResponse(BaseModel):
    job_id: str
    status: GenerationStatus


class GenerationImage(BaseModel):
    id: str
    url: str
    selected: bool = False
    score: float | None = None


class GenerationStatusResponse(BaseModel):
    job_id: str
    status: GenerationStatus
    status_message: str | None = None
    progress: float = Field(ge=0, le=1)
    prompt: str
    expanded_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    candidate_count: int = 1
    images: list[GenerationImage] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class GenerationHistoryItem(GenerationStatusResponse):
    created_at: datetime
    completed_at: datetime | None = None
    archived_at: datetime | None = None


class GenerationHistoryResponse(BaseModel):
    generations: list[GenerationHistoryItem]


class ArchiveGenerationResponse(BaseModel):
    job_id: str
    archived_at: datetime


class SelectOutputRequest(BaseModel):
    output_id: str


class SelectOutputResponse(BaseModel):
    job_id: str
    output_id: str
    status: GenerationStatus


class CancelGenerationResponse(BaseModel):
    job_id: str
    status: GenerationStatus


class FeedbackRequest(BaseModel):
    output_id: str | None = None
    liked: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    id: str
    generation_id: str
    output_id: str | None = None
    liked: bool | None = None
    rating: int | None = None
