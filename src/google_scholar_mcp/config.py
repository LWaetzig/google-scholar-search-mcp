from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class ProxyType(str, Enum):
    NONE = "none"
    FREE = "free"
    SINGLE = "single"
    SCRAPERAPI = "scraperapi"


@dataclass(frozen=True)
class Config:
    min_delay_seconds: float
    max_delay_seconds: float
    max_retries: int
    proxy_type: ProxyType
    proxy_http: str | None
    proxy_https: str | None
    scraperapi_key: str | None
    timeout_seconds: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            min_delay_seconds=float(os.getenv("GS_MIN_DELAY", "5.0")),
            max_delay_seconds=float(os.getenv("GS_MAX_DELAY", "15.0")),
            max_retries=int(os.getenv("GS_MAX_RETRIES", "3")),
            proxy_type=ProxyType(os.getenv("GS_PROXY_TYPE", "none").lower()),
            proxy_http=os.getenv("GS_PROXY_HTTP"),
            proxy_https=os.getenv("GS_PROXY_HTTPS"),
            scraperapi_key=os.getenv("GS_SCRAPERAPI_KEY"),
            timeout_seconds=int(os.getenv("GS_TIMEOUT", "30")),
        )
