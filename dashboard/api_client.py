"""HTTP Client for Borsel Handler FastAPI Backend.

Connects strictly via HTTP to the existing backend endpoints under /api/demo
and /health. Handles network timeouts, unavailable backend, and malformed responses.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_API_URL = os.getenv("BORSEL_API_URL", "http://localhost:8000").rstrip("/")


class ApiClientError(Exception):
    """Base exception for Borsel API client errors."""


class BackendUnavailableError(ApiClientError):
    """Raised when the FastAPI backend is completely unreachable."""


class ResourceNotFoundError(ApiClientError):
    """Raised when an API endpoint returns 404."""


class BorselApiClient:
    """Synchronous HTTP client for Streamlit frontend interaction with FastAPI."""

    def __init__(self, base_url: str | None = None, default_timeout: float = 10.0) -> None:
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self.default_timeout = default_timeout

    def check_health(self) -> dict[str, Any]:
        """Check if FastAPI backend and its health endpoint are responsive."""
        url = f"{self.base_url}/health"
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "is_healthy": True,
                        "status": data.get("status", "ok"),
                        "message": "Connected to Borsel API backend",
                        "url": self.base_url,
                    }
                return {
                    "is_healthy": False,
                    "status": "degraded",
                    "message": f"Backend returned HTTP {resp.status_code}",
                    "url": self.base_url,
                }
        except httpx.ConnectError:
            return {
                "is_healthy": False,
                "status": "offline",
                "message": f"Could not connect to {self.base_url}. Ensure Docker/FastAPI is running.",
                "url": self.base_url,
            }
        except httpx.TimeoutException:
            return {
                "is_healthy": False,
                "status": "timeout",
                "message": f"Health check timed out after 3.0s at {self.base_url}",
                "url": self.base_url,
            }
        except Exception as e:
            return {
                "is_healthy": False,
                "status": "error",
                "message": f"Unexpected health check error: {e}",
                "url": self.base_url,
            }

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        effective_timeout = timeout or self.default_timeout
        try:
            with httpx.Client(timeout=effective_timeout) as client:
                resp = client.request(method=method, url=url, params=params)
                if resp.status_code == 404:
                    raise ResourceNotFoundError(f"Resource not found at {path}")
                resp.raise_for_status()
                return resp.json()
        except ApiClientError:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise BackendUnavailableError(
                f"Backend service unreachable at {self.base_url}. Ensure the API server is running."
            ) from e
        except httpx.TimeoutException as e:
            raise ApiClientError(
                f"Request to {path} timed out after {effective_timeout}s."
            ) from e
        except httpx.HTTPStatusError as e:
            raise ApiClientError(
                f"API returned HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except Exception as e:
            raise ApiClientError(f"HTTP request error: {e}") from e

    def get_summary(self) -> dict[str, Any]:
        """Fetch high-level market data summary and ingestion metadata."""
        return self._request("GET", "/api/demo/summary")

    def get_stocks(self) -> list[dict[str, Any]]:
        """Fetch list of all tracked stocks with summary metrics."""
        return self._request("GET", "/api/demo/stocks")

    def get_stock_history(
        self, symbol: str, limit: int = 1000, order: str = "desc"
    ) -> list[dict[str, Any]]:
        """Fetch historical daily OHLCV bars for a given symbol."""
        sym_clean = symbol.strip().upper()
        return self._request(
            "GET",
            f"/api/demo/stocks/{sym_clean}",
            params={"limit": limit, "order": order},
        )

    def trigger_refresh(self, period: str = "1y") -> dict[str, Any]:
        """Trigger an on-demand market data ingestion run."""
        return self._request(
            "POST",
            "/api/demo/refresh",
            params={"period": period},
            timeout=90.0,  # Allow time for Yahoo Finance downloads
        )

    def get_ingestion_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent ingestion run audit records."""
        return self._request(
            "GET",
            "/api/demo/ingestion-runs",
            params={"limit": limit},
        )
