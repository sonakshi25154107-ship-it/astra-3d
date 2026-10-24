"""NASA NeoWs client for ASTRA 3D.

Responsibilities
----------------
* Read the API key from the environment (never hard-coded).
* Validate the requested date range against the NeoWs feed limit (7 days).
* Call the official Feed endpoint with timeouts and translate every failure
  into a friendly ``NasaAPIError``.
* Provide an optional, clearly synthetic sample payload (same JSON shape as
  NeoWs) for offline demos. It is never presented as live NASA data.

Security note: the API key is sent as a query parameter, so ``requests``
exception messages can contain it. This module therefore NEVER forwards the
text of a ``requests`` exception; it raises its own messages ``from None``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import requests
from dotenv import load_dotenv

FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"
DEMO_KEY = "DEMO_KEY"
MAX_RANGE_DAYS = 7  # NeoWs feed limit: at most 7 days per request
REQUEST_TIMEOUT = (5, 20)  # (connect, read) seconds

AU_KM = 149_597_870.7  # kilometres per astronomical unit
LUNAR_DISTANCE_KM = 384_400.0  # mean Earth-Moon distance


class NasaAPIError(Exception):
    """Raised for any failure to obtain a usable NeoWs response."""

    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind  # timeout | network | rate_limit | invalid_key | bad_request | server | malformed


@dataclass(frozen=True)
class FeedResult:
    """A successful feed response plus request metadata."""

    payload: dict[str, Any]
    retrieved_at: datetime
    rate_remaining: Optional[int]
    element_count: Optional[int]


def get_api_key() -> str:
    """Return NASA_API_KEY from the environment/.env, or DEMO_KEY if unset."""
    load_dotenv()
    key = (os.getenv("NASA_API_KEY") or "").strip()
    return key or DEMO_KEY


def is_demo_key(key: str) -> bool:
    return key == DEMO_KEY


def validate_date_range(start: date, end: date) -> None:
    """Raise ValueError if the range is reversed or longer than 7 days (inclusive)."""
    if end < start:
        raise ValueError("The end date must be on or after the start date.")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(f"NASA's feed allows at most {MAX_RANGE_DAYS} days per request.")


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_feed(start: date, end: date, api_key: str) -> FeedResult:
    """Fetch the NeoWs feed for ``start``..``end`` (inclusive, max 7 days)."""
    try:
        validate_date_range(start, end)
    except ValueError as exc:
        raise NasaAPIError(str(exc), kind="bad_request") from None

    params = {"start_date": start.isoformat(), "end_date": end.isoformat(), "api_key": api_key}
    try:
        resp = requests.get(FEED_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise NasaAPIError(
            "NASA did not respond in time. Check your connection and try again.", kind="timeout"
        ) from None
    except requests.exceptions.ConnectionError:
        raise NasaAPIError(
            "Could not reach api.nasa.gov. Check your internet connection or firewall.", kind="network"
        ) from None
    except requests.exceptions.RequestException:
        raise NasaAPIError("An unexpected network error occurred while contacting NASA.", kind="network") from None

    status = resp.status_code
    if status == 429:
        raise NasaAPIError(
            "NASA rate limit reached (HTTP 429). DEMO_KEY allows only about 30 requests/hour and "
            "50/day per IP. Wait a while, or add your own free key to the .env file.",
            kind="rate_limit",
        )
    if status in (401, 403):
        raise NasaAPIError(
            f"NASA rejected the API key (HTTP {status}). Check NASA_API_KEY in your .env file, "
            "or use DEMO_KEY.",
            kind="invalid_key",
        )
    if status == 400:
        raise NasaAPIError(
            "NASA rejected the request (HTTP 400). Check that the dates are valid and within 7 days.",
            kind="bad_request",
        )
    if status >= 500:
        raise NasaAPIError(f"NASA's service returned an error (HTTP {status}). Try again shortly.", kind="server")
    if status != 200:
        raise NasaAPIError(f"Unexpected response from NASA (HTTP {status}).", kind="server")

    try:
        payload = resp.json()
    except ValueError:
        raise NasaAPIError("NASA returned a response that is not valid JSON.", kind="malformed") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("near_earth_objects"), dict):
        raise NasaAPIError("NASA's response is missing the 'near_earth_objects' field.", kind="malformed")

    return FeedResult(
        payload=payload,
        retrieved_at=datetime.now(timezone.utc),
        rate_remaining=_int_or_none(resp.headers.get("X-RateLimit-Remaining")),
        element_count=_int_or_none(payload.get("element_count")),
    )


def build_sample_payload(start: date, end: date) -> dict[str, Any]:
    """Build a SYNTHETIC payload shaped like NeoWs. NOT real NASA data.

    Deterministic (fixed seed). Objects are named SAMPLE-nnn, carry no NASA URL,
    and a few deliberately omit fields so the app's missing-value handling is
    exercised.
    """
    validate_date_range(start, end)
    rng = np.random.default_rng(20240101)
    by_date: dict[str, list[dict[str, Any]]] = {}
    counter = 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        items: list[dict[str, Any]] = []
        for _ in range(int(rng.integers(3, 8))):
            counter += 1
            d_mean = 10 ** rng.uniform(1.0, 3.2)
            velocity = float(rng.uniform(4.0, 36.0))
            miss_lunar = 10 ** rng.uniform(-0.7, 1.7)
            miss_km = miss_lunar * LUNAR_DISTANCE_KM
            miss_au = miss_km / AU_KM
            d_min, d_max = d_mean * 0.7, d_mean * 1.3
            hh, mm = int(rng.integers(0, 24)), int(rng.integers(0, 60))
            approach: dict[str, Any] = {
                "close_approach_date": day.isoformat(),
                "close_approach_date_full": f"{day:%Y-%b-%d} {hh:02d}:{mm:02d}",
                "relative_velocity": {
                    "kilometers_per_second": f"{velocity:.6f}",
                    "kilometers_per_hour": f"{velocity * 3600:.3f}",
                },
                "miss_distance": {
                    "astronomical": f"{miss_au:.8f}",
                    "lunar": f"{miss_lunar:.4f}",
                    "kilometers": f"{miss_km:.1f}",
                },
                "orbiting_body": "Earth",
            }
            item: dict[str, Any] = {
                "id": f"SAMPLE-{counter:03d}",
                "name": f"SAMPLE-{counter:03d}",
                "nasa_jpl_url": None,
                "absolute_magnitude_h": None,
                "estimated_diameter": {
                    "meters": {"estimated_diameter_min": d_min, "estimated_diameter_max": d_max}
                },
                "is_potentially_hazardous_asteroid": bool(d_max >= 150 and miss_au <= 0.05),
                "is_sentry_object": False,
                "close_approach_data": [approach],
            }
            if counter % 7 == 0:
                del item["estimated_diameter"]  # simulate a missing diameter
            if counter % 11 == 0:
                approach["relative_velocity"] = {}  # simulate a missing velocity
            items.append(item)
        by_date[day.isoformat()] = items
    return {"element_count": counter, "near_earth_objects": by_date}