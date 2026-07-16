"""Response schemas for foundation endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from workflowtwin.core.config import Environment


class ApiModel(BaseModel):
    """Base transport model with strict input validation."""

    model_config = ConfigDict(extra="forbid")


class RootResponse(ApiModel):
    """Service discovery response."""

    service: str
    version: str
    message: str
    docs_url: str


class HealthResponse(ApiModel):
    """Service liveness response."""

    status: Literal["ok"]
    service: str
    version: str
    environment: Environment
