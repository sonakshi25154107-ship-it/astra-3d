"""Parsing, filtering and summarising NeoWs data for ASTRA 3D.

Conventions (also documented in the README and app footer)
---------------------------------------------------------
* Diameters come from NASA's ``estimated_diameter.meters`` block. The
  "mean diameter" used for sizing and KPIs is (min + max) / 2 of NASA's
  estimate. It is an estimate range, not a measurement.
* ``velocity_kms`` is velocity RELATIVE TO EARTH at close approach, not the
  asteroid's orbital speed around the Sun.
* ``miss_*`` is the distance at closest approach. It says nothing about size.
* Missing values stay missing (NaN / <NA>). Nothing is invented. Only exact
  unit conversions are applied (AU <-> km <-> lunar distance, km/s -> km/h).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd

from nasa_api import AU_KM, LUNAR_DISTANCE_KM

NOT_PROVIDED = "Not provided"

COLUMNS = [
    "row_id", "id", "name", "hazardous", "sentry", "h_mag",
    "diameter_min_m", "diameter_max_m", "diameter_mean_m",
    "approach_date", "approach_time", "velocity_kms", "velocity_kmh",
    "miss_km", "miss_lunar", "miss_au", "orbiting_body", "nasa_url",
]
NUMERIC_COLUMNS = [
    "h_mag", "diameter_min_m", "diameter_max_m", "diameter_mean_m",
    "velocity_kms", "velocity_kmh", "miss_km", "miss_lunar", "miss_au",
]

# Layout constants for the schematic 3D scene (display units, not physical).
EARTH_X = 12.0
R_MIN, R_MAX = 1.2, 5.0

# ----------------------------------------------------------------- safe values


def safe_float(value: Any) -> float:
    """Convert to a finite float, or NaN for None/empty/malformed input."""
    if value is None or isinstance(value, bool):
        return math.nan
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result if math.isfinite(result) else math.nan


def safe_bool(value: Any) -> Optional[bool]:
    """Return True/False for real booleans or 'true'/'false' strings, else None."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low == "true":
            return True
        if low == "false":
            return False
    return None


def _get(mapping: Any, *keys: str) -> Any:
    """Walk nested dicts safely; return None if any level is missing."""
    for key in keys:
        if not isinstance(mapping, dict):
            return None
        mapping = mapping.get(key)
    return mapping


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


# -------------------------------------------------------------------- parsing


def _neo_to_records(neo: dict[str, Any], feed_date: str) -> list[dict[str, Any]]:
    neo_id = _text(neo.get("id")) or _text(neo.get("neo_reference_id"))
    name = _text(neo.get("name"))
    if not neo_id and not name:
        return []
    neo_id = neo_id or name
    name = name or neo_id

    d_min = safe_float(_get(neo, "estimated_diameter", "meters", "estimated_diameter_min"))
    d_max = safe_float(_get(neo, "estimated_diameter", "meters", "estimated_diameter_max"))
    d_mean = (d_min + d_max) / 2 if math.isfinite(d_min) and math.isfinite(d_max) else math.nan

    base = {
        "id": neo_id,
        "name": name,
        "hazardous": safe_bool(neo.get("is_potentially_hazardous_asteroid")),
        "sentry": safe_bool(neo.get("is_sentry_object")),
        "h_mag": safe_float(neo.get("absolute_magnitude_h")),
        "diameter_min_m": d_min,
        "diameter_max_m": d_max,
        "diameter_mean_m": d_mean,
        "nasa_url": _text(neo.get("nasa_jpl_url")) or None,
    }

    approaches = neo.get("close_approach_data")
    if not isinstance(approaches, list) or not approaches:
        approaches = [{"close_approach_date": feed_date}]  # no approach details provided

    records: list[dict[str, Any]] = []
    for ca in approaches:
        if not isinstance(ca, dict):
            continue
        date_str = _text(ca.get("close_approach_date")) or feed_date
        full = _text(ca.get("close_approach_date_full"))
        body = _text(ca.get("orbiting_body")) or "Earth"

        vel_kms = safe_float(_get(ca, "relative_velocity", "kilometers_per_second"))
        vel_kmh = safe_float(_get(ca, "relative_velocity", "kilometers_per_hour"))
        if math.isnan(vel_kmh) and math.isfinite(vel_kms):
            vel_kmh = vel_kms * 3600.0

        km = safe_float(_get(ca, "miss_distance", "kilometers"))
        au = safe_float(_get(ca, "miss_distance", "astronomical"))
        ld = safe_float(_get(ca, "miss_distance", "lunar"))
        if math.isnan(km):
            if math.isfinite(au):
                km = au * AU_KM
            elif math.isfinite(ld):
                km = ld * LUNAR_DISTANCE_KM
        if math.isfinite(km):
            if math.isnan(au):
                au = km / AU_KM
            if math.isnan(ld):
                ld = km / LUNAR_DISTANCE_KM

        records.append({
            **base,
            "row_id": f"{neo_id}|{full or date_str}|{body}",
            "approach_date": pd.to_datetime(date_str, errors="coerce"),
            "approach_time": pd.to_datetime(full, format="%Y-%b-%d %H:%M", errors="coerce") if full else pd.NaT,
            "velocity_kms": vel_kms,
            "velocity_kmh": vel_kmh,
            "miss_km": km,
            "miss_lunar": ld,
            "miss_au": au,
            "orbiting_body": body,
        })
    return records


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce column order and dtypes (also valid for an empty frame)."""
    df = df.reindex(columns=COLUMNS)
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["approach_date"] = pd.to_datetime(df["approach_date"], errors="coerce")
    df["approach_time"] = pd.to_datetime(df["approach_time"], errors="coerce")
    for col in ("hazardous", "sentry"):
        df[col] = df[col].astype("boolean")
    for col in ("row_id", "id", "name", "orbiting_body", "nasa_url"):
        df[col] = df[col].astype("object")
    return df


def parse_feed(payload: dict[str, Any], start: Optional[date] = None, end: Optional[date] = None) -> pd.DataFrame:
    """Turn a NeoWs feed payload into a tidy DataFrame, one row per close approach.

    Duplicates (same object + approach) are dropped. If ``start``/``end`` are
    given, rows are kept only when the ACTUAL approach date lies in that window.
    """
    by_date = payload.get("near_earth_objects") if isinstance(payload, dict) else None
    records: list[dict[str, Any]] = []
    if isinstance(by_date, dict):
        for feed_date, objects in by_date.items():
            if not isinstance(objects, list):
                continue
            for neo in objects:
                if isinstance(neo, dict):
                    records.extend(_neo_to_records(neo, str(feed_date)))

    df = _finalize(pd.DataFrame(records))
    if df.empty:
        return df
    df = df.drop_duplicates(subset="row_id", keep="first")
    if start is not None and end is not None:
        in_window = (df["approach_date"] >= pd.Timestamp(start)) & (df["approach_date"] <= pd.Timestamp(end))
        df = df[in_window]
    return df.sort_values(["approach_date", "miss_km"]).reset_index(drop=True)


# ------------------------------------------------------------------ filtering


def flag_mask(series: pd.Series, value: bool) -> np.ndarray:
    """Boolean numpy mask where a nullable-boolean series equals ``value`` (NA -> False)."""
    return series.eq(value).fillna(False).to_numpy(dtype=bool)


def apply_filters(
    df: pd.DataFrame,
    *,
    start: date,
    end: date,
    hazard_mode: str = "All",
    diameter_m: Optional[tuple[float, float]] = None,
    query: str = "",
) -> pd.DataFrame:
    """Apply every sidebar filter. One function so all views stay consistent."""
    if df.empty:
        return df
    mask = np.array(
        (df["approach_date"] >= pd.Timestamp(start)) & (df["approach_date"] <= pd.Timestamp(end)), dtype=bool
    )  # np.array copies, so the mask is writable
    if hazard_mode == "Hazardous only":
        mask &= flag_mask(df["hazardous"], True)
    elif hazard_mode == "Non-hazardous only":
        mask &= flag_mask(df["hazardous"], False)
    if diameter_m is not None:
        lo, hi = diameter_m
        mask &= df["diameter_mean_m"].between(lo, hi).to_numpy(dtype=bool)  # NaN -> excluded
    q = query.strip().lower()
    if q:
        in_name = df["name"].astype(str).str.lower().str.contains(q, regex=False, na=False)
        in_id = df["id"].astype(str).str.lower().str.contains(q, regex=False, na=False)
        mask &= (in_name | in_id).to_numpy(dtype=bool)
    return df[mask].reset_index(drop=True)


def split_by_hazard(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Return [(label, subset)] for hazardous / not hazardous / unknown (non-empty only)."""
    groups = [
        ("Potentially hazardous", df[flag_mask(df["hazardous"], True)]),
        ("Not hazardous", df[flag_mask(df["hazardous"], False)]),
        ("Status not provided", df[df["hazardous"].isna().to_numpy(dtype=bool)]),
    ]
    return [(label, sub) for label, sub in groups if not sub.empty]


# ------------------------------------------------------------------------ KPIs


@dataclass(frozen=True)
class Kpis:
    total_unique: int
    hazardous_unique: int
    largest_diameter_m: float
    largest_name: str
    closest_km: float
    closest_lunar: float
    closest_name: str
    closest_date: str


def compute_kpis(df: pd.DataFrame) -> Kpis:
    """Compute headline numbers from the (filtered) dataset only."""
    nan = math.nan
    if df.empty:
        return Kpis(0, 0, nan, "", nan, nan, "", "")
    hazardous_unique = int(df.loc[flag_mask(df["hazardous"], True), "id"].nunique())

    sized = df.dropna(subset=["diameter_mean_m"])
    if sized.empty:
        largest, largest_name = nan, ""
    else:
        row = sized.loc[sized["diameter_mean_m"].idxmax()]
        largest, largest_name = float(row["diameter_mean_m"]), str(row["name"])

    ranged = df.dropna(subset=["miss_km"])
    if ranged.empty:
        c_km = c_ld = nan
        c_name = c_date = ""
    else:
        row = ranged.loc[ranged["miss_km"].idxmin()]
        c_km, c_ld = float(row["miss_km"]), float(row["miss_lunar"])
        c_name = str(row["name"])
        c_date = row["approach_date"].strftime("%Y-%m-%d") if pd.notna(row["approach_date"]) else ""
    return Kpis(int(df["id"].nunique()), hazardous_unique, largest, largest_name, c_km, c_ld, c_name, c_date)


# ------------------------------------------------- illustrative 3D coordinates


def _unit_pair(key: str) -> tuple[float, float]:
    """Deterministic pair of numbers in [0, 1) derived from a string (SHA-256)."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 2**32, int.from_bytes(digest[4:8], "big") / 2**32


def illustrative_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Add x, y, z columns for the SCHEMATIC scene. These are NOT real positions.

    * Direction (angles): pseudo-random but deterministic, from a hash of the
      object's row_id. It carries no orbital information.
    * Distance from Earth: a monotonic, log-compressed function of the real
      miss distance (0.1 LD -> R_MIN, 100 LD -> R_MAX). Only this ordering is
      meaningful, and only loosely.
    * Sun at the origin, Earth at (EARTH_X, 0, 0): arbitrary, not to scale.
    Objects with no miss distance receive NaN and are not plotted.
    """
    out = df.copy()
    if out.empty:
        out[["x", "y", "z"]] = np.nan
        return out
    pairs = [_unit_pair(rid) for rid in out["row_id"]]
    u = np.array([p[0] for p in pairs])
    v = np.array([p[1] for p in pairs])
    theta = 2 * np.pi * u
    cos_phi = 1 - 2 * v  # uniform direction on a sphere
    sin_phi = np.sqrt(np.clip(1 - cos_phi**2, 0, 1))
    ld = out["miss_lunar"].to_numpy(dtype=float)
    s = (np.log10(np.clip(ld, 0.1, 100.0)) + 1.0) / 3.0
    r = R_MIN + (R_MAX - R_MIN) * s
    out["x"] = EARTH_X + r * sin_phi * np.cos(theta)
    out["y"] = r * sin_phi * np.sin(theta)
    out["z"] = r * cos_phi
    return out


# ----------------------------------------------------------------- formatting


def fmt_number(value: Any, decimals: int = 1, suffix: str = "") -> str:
    v = safe_float(value)
    return NOT_PROVIDED if math.isnan(v) else f"{v:,.{decimals}f}{suffix}"


def fmt_diameter(meters: Any) -> str:
    v = safe_float(meters)
    if math.isnan(v):
        return NOT_PROVIDED
    return f"{v / 1000:,.2f} km" if v >= 1000 else f"{v:,.0f} m"


def fmt_hazard(value: Any) -> str:
    flag = safe_bool(value) if not pd.isna(value) else None
    return "Yes" if flag is True else "No" if flag is False else "Unknown"


# --------------------------------------------------------------- table / CSV


def to_display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Human-readable table with units in the column names (also used for CSV)."""
    hazard = np.where(
        flag_mask(df["hazardous"], True), "Yes",
        np.where(flag_mask(df["hazardous"], False), "No", "Unknown"),
    )
    return pd.DataFrame({
        "Name": df["name"],
        "NASA ID": df["id"],
        "Potentially hazardous": hazard,
        "Approach date": df["approach_date"].dt.strftime("%Y-%m-%d"),
        "Approach time": df["approach_time"].dt.strftime("%H:%M"),
        "Mean diameter (m)": df["diameter_mean_m"],
        "Min diameter (m)": df["diameter_min_m"],
        "Max diameter (m)": df["diameter_max_m"],
        "Relative velocity (km/s)": df["velocity_kms"],
        "Relative velocity (km/h)": df["velocity_kmh"],
        "Miss distance (km)": df["miss_km"],
        "Miss distance (lunar distances)": df["miss_lunar"],
        "Miss distance (AU)": df["miss_au"],
        "NASA JPL page": df["nasa_url"],
    }).reset_index(drop=True)