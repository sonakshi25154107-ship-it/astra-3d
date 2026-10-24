"""ASTRA 3D — NASA Near-Earth Asteroid Intelligence Explorer (Streamlit entry point).

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
import streamlit as st

import data_processing as dp
import visualizations as viz
from nasa_api import (
    DEMO_KEY, MAX_RANGE_DAYS, FeedResult, NasaAPIError, build_sample_payload,
    fetch_feed, get_api_key, is_demo_key, validate_date_range,
)

st.set_page_config(page_title="ASTRA 3D — Near-Earth Object Intelligence", layout="wide",
                   initial_sidebar_state="expanded")

SAMPLE_LABEL = "DEMO/SAMPLE DATA — NOT LIVE NASA DATA"
HAZARD_OPTIONS = ["All", "Hazardous only", "Non-hazardous only"]

CSS = """
<style>
:root{--bg0:#050816;--bg1:#0a1030;--panel:rgba(14,22,50,.72);--border:rgba(120,150,220,.18);
--text:#dbe4f5;--muted:#8d9bbd;--cyan:#4cc9f0;--amber:#f4a259;--font:Inter,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}
.stApp{background:radial-gradient(1100px 560px at 12% -10%,rgba(98,84,235,.20),transparent 60%),
radial-gradient(900px 480px at 100% 0%,rgba(76,201,240,.10),transparent 55%),linear-gradient(180deg,var(--bg1),var(--bg0) 60%);
color:var(--text);font-family:var(--font);}
header[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer{visibility:hidden;}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1400px;}
[data-testid="stSidebar"]{background:rgba(7,11,32,.94);border-right:1px solid var(--border);}
.astra-top{display:flex;flex-wrap:wrap;gap:.75rem 1.5rem;align-items:center;justify-content:space-between;
padding:.9rem 1.1rem;border:1px solid var(--border);border-radius:8px;background:var(--panel);
box-shadow:0 8px 30px rgba(0,0,10,.35);}
.astra-brand{font-size:1.35rem;font-weight:650;letter-spacing:.06em;color:#fff;}
.astra-brand small{display:block;font-size:.8rem;font-weight:400;letter-spacing:0;color:var(--muted);}
.astra-meta{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;font-size:.8rem;color:var(--muted);align-items:center;}
.pill{padding:.2rem .65rem;border-radius:999px;border:1px solid;font-size:.75rem;font-weight:600;}
.pill-live{color:#6ee7b7;border-color:rgba(110,231,183,.5);background:rgba(110,231,183,.08);}
.pill-sample{color:var(--amber);border-color:rgba(244,162,89,.6);background:rgba(244,162,89,.10);}
.pill-off{color:var(--muted);border-color:var(--border);}
.hero{padding:1.6rem .2rem .6rem;}
.hero h1{font-size:2rem;font-weight:600;line-height:1.2;margin:0 0 .5rem;color:#fff;}
.hero p{max-width:70ch;color:var(--muted);margin:0;font-size:.98rem;line-height:1.55;}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.8rem;margin:1rem 0 1.4rem;}
.kpi{padding:.95rem 1.1rem;border:1px solid var(--border);border-radius:8px;background:var(--panel);
box-shadow:0 6px 24px rgba(0,0,10,.3);}
.kpi-label{font-size:.78rem;color:var(--muted);}
.kpi-value{font-size:1.75rem;font-weight:600;color:#fff;margin:.15rem 0;font-variant-numeric:tabular-nums;}
.kpi-sub{font-size:.76rem;color:var(--muted);overflow-wrap:anywhere;}
.kpi.accent{border-color:rgba(76,201,240,.45);box-shadow:0 0 22px rgba(76,201,240,.10);}
.section-title{font-size:1.15rem;font-weight:600;color:#fff;margin:1.6rem 0 .3rem;}
.section-note{font-size:.85rem;color:var(--muted);margin:0 0 .7rem;max-width:90ch;line-height:1.5;}
.banner{padding:.55rem .9rem;border:1px solid rgba(244,162,89,.55);border-radius:6px;background:rgba(244,162,89,.08);
color:var(--amber);font-size:.8rem;font-weight:600;margin-bottom:.6rem;letter-spacing:.02em;}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.6rem;margin:.6rem 0 1rem;}
.detail{padding:.7rem .9rem;border:1px solid var(--border);border-radius:8px;background:var(--panel);}
.detail .k{font-size:.74rem;color:var(--muted);}
.detail .v{font-size:1rem;color:#fff;overflow-wrap:anywhere;}
.astra-footer{margin-top:2.5rem;padding:1.1rem 1.2rem;border-top:1px solid var(--border);color:var(--muted);
font-size:.8rem;line-height:1.6;}
.astra-footer b{color:var(--text);}
.astra-footer a{color:var(--cyan);}
.stButton>button[kind="primary"]{background:linear-gradient(180deg,#2aa8d6,#1d86b0);border:1px solid rgba(76,201,240,.6);
color:#031018;font-weight:600;}
.stButton>button{border-radius:6px;}
@media (max-width:640px){.hero h1{font-size:1.5rem;}.kpi-value{font-size:1.4rem;}.block-container{padding-left:.8rem;padding-right:.8rem;}}
[data-baseweb="input"],[data-baseweb="select"]>div{border:1px solid rgba(120,150,220,.35)!important;border-radius:6px!important;}
.kpi-grid{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));}
</style>
"""


def _html(markup: str) -> str:
    """Strip indentation/blank lines so Markdown never treats the HTML as a code block."""
    return "\n".join(line.strip() for line in markup.splitlines() if line.strip())


def esc(value: Any) -> str:
    return html.escape(str(value))


# ------------------------------------------------------------------- data load


@st.cache_data(ttl=3600, show_spinner=False)
def cached_fetch(start_iso: str, end_iso: str, using_demo_key: bool, _api_key: str) -> FeedResult:
    """Cached NASA call. Exceptions are NOT cached by Streamlit, so failures are retried.

    ``_api_key`` has a leading underscore so Streamlit does not hash/store it in the cache key.
    """
    return fetch_feed(date.fromisoformat(start_iso), date.fromisoformat(end_iso), _api_key)


def load_dataset(start: date, end: date, use_sample: bool, force_refresh: bool) -> None:
    """Fetch + parse data and store the result (or an error) in session state."""
    api_key = get_api_key()
    try:
        with st.spinner("Contacting NASA NeoWs and processing the response..."):
            if use_sample:
                payload, source = build_sample_payload(start, end), "sample"
                retrieved_at, remaining = datetime.now(timezone.utc), None
            else:
                if force_refresh:
                    cached_fetch.clear()
                result = cached_fetch(start.isoformat(), end.isoformat(), is_demo_key(api_key), api_key)
                payload, source = result.payload, "live"
                retrieved_at, remaining = result.retrieved_at, result.rate_remaining
            frame = dp.parse_feed(payload, start, end)
    except NasaAPIError as exc:
        st.session_state["load_error"] = exc.message
        return
    except (ValueError, TypeError, KeyError, AttributeError):
        st.session_state["load_error"] = "The data could not be processed because the response was malformed."
        return

    st.session_state["load_error"] = None
    st.session_state["dataset"] = {
        "df": frame, "source": source, "start": start, "end": end, "retrieved_at": retrieved_at,
        "rate_remaining": remaining, "using_demo_key": is_demo_key(api_key),
        "version": st.session_state.get("dataset_version", 0) + 1,
    }
    st.session_state["dataset_version"] = st.session_state["dataset"]["version"]


# ------------------------------------------------------------------ rendering


def header_html(ds: Optional[dict[str, Any]], error: Optional[str]) -> str:
    if ds is None:
        pill, cls = "NO DATA LOADED", "pill-off"
    elif ds["source"] == "live":
        pill, cls = "LIVE NASA DATA", "pill-live"
    else:
        pill, cls = SAMPLE_LABEL, "pill-sample"

    if error:
        api = "API: last request failed"
    elif ds is None:
        api = "API: not contacted"
    elif ds["source"] == "sample":
        api = "API: not used (sample mode)"
    else:
        key_txt = "DEMO_KEY (rate-limited)" if ds["using_demo_key"] else "personal key"
        rem = f" · {ds['rate_remaining']} requests left this hour" if ds["rate_remaining"] is not None else ""
        api = f"API: connected · {key_txt}{rem}"
    stamp = ds["retrieved_at"].strftime("%Y-%m-%d %H:%M UTC") if ds else "n/a"
    return _html(f"""
    <div class="astra-top">
      <div class="astra-brand">ASTRA 3D<small>Near-Earth Object Intelligence</small></div>
      <div class="astra-meta">
        <span class="pill {cls}">{esc(pill)}</span>
        <span>{esc(api)}</span>
        <span>Retrieved: {esc(stamp)}</span>
        <span>Data: NASA NeoWs (api.nasa.gov)</span>
      </div>
    </div>""")


def parse_window(picked: Any) -> tuple[Optional[date], Optional[date], Optional[str]]:
    """Validate the date_input value. Returns (start, end, error_message)."""
    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        return None, None, "Pick both a start and an end date."
    start, end = picked
    try:
        validate_date_range(start, end)
    except ValueError as exc:
        return None, None, str(exc)
    return start, end, None


def render_hero() -> tuple[Optional[date], Optional[date], bool, bool]:
    st.markdown(_html("""
    <div class="hero"><h1>Close approaches of near-Earth objects, as reported by NASA</h1>
    <p>Choose a window of up to 7 days, load the official NeoWs feed, then filter, compare and inspect each object.
    The 3D view is a schematic layout for exploration; measured values live in the tooltips, charts and table.</p></div>"""),
        unsafe_allow_html=True)
    today = date.today()
    c1, c2, c3 = st.columns([3, 3, 2], vertical_alignment="bottom")
    with c1:
        picked = st.date_input(f"Date range (max {MAX_RANGE_DAYS} days)", value=(today - timedelta(days=6), today),
                               min_value=date(1900, 1, 1), max_value=today + timedelta(days=365), key="window")
    with c2:
        use_sample = st.checkbox(SAMPLE_LABEL, value=False, key="use_sample",
                                 help="Synthetic data for offline demos. Never mixed with live data.")
    start, end, err = parse_window(picked)
    if err:
        st.warning(err)
    with c3:
        clicked = st.button("Fetch data", type="primary", disabled=err is not None, use_container_width=True)
    return start, end, clicked, use_sample


def _reset_filters() -> None:
    st.session_state["filter_nonce"] = st.session_state.get("filter_nonce", 0) + 1


def render_filters(ds: dict[str, Any]) -> pd.DataFrame:
    """Sidebar filter panel; returns the filtered DataFrame used by every view."""
    df: pd.DataFrame = ds["df"]
    tag = f"{ds['version']}_{st.session_state.get('filter_nonce', 0)}"
    with st.sidebar:
        st.markdown('<div class="section-title" style="margin-top:.2rem">Filters</div>', unsafe_allow_html=True)
        dates = df["approach_date"].dropna()
        d_lo = dates.min().date() if not dates.empty else ds["start"]
        d_hi = dates.max().date() if not dates.empty else ds["end"]
        if d_lo < d_hi:
            window = st.slider("Approach date", min_value=d_lo, max_value=d_hi, value=(d_lo, d_hi), key=f"f_date_{tag}")
        else:
            st.caption(f"All approaches fall on {d_lo:%Y-%m-%d}.")
            window = (d_lo, d_hi)
        hazard = st.radio("Potentially hazardous", HAZARD_OPTIONS, key=f"f_haz_{tag}")

        sizes = df["diameter_mean_m"].dropna()
        diameter: Optional[tuple[float, float]] = None
        if sizes.empty:
            st.caption("No diameter estimates in this dataset.")
        else:
            lo, hi = math.floor(float(sizes.min())), math.ceil(float(sizes.max()))
            a, b = st.columns(2)
            min_d = a.number_input("Min diameter (m)", min_value=float(lo), max_value=float(hi), value=float(lo),
                                   key=f"f_dmin_{tag}")
            max_d = b.number_input("Max diameter (m)", min_value=float(lo), max_value=float(hi), value=float(hi),
                                   key=f"f_dmax_{tag}")
            if min_d > lo or max_d < hi:  # only constrain when narrowed
                diameter = (min_d, max_d)
        query = st.text_input("Search name or NASA ID", key=f"f_q_{tag}")
        st.button("Reset filters", on_click=_reset_filters, use_container_width=True)
    return dp.apply_filters(df, start=window[0], end=window[1], hazard_mode=hazard, diameter_m=diameter, query=query)


def kpi_card(label: str, value: str, sub: str, accent: bool = False) -> str:
    cls = "kpi accent" if accent else "kpi"
    return f'<div class="{cls}"><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{esc(value)}</div><div class="kpi-sub">{esc(sub)}</div></div>'


def render_kpis(df: pd.DataFrame) -> None:
    k = dp.compute_kpis(df)
    largest = dp.fmt_diameter(k.largest_diameter_m)
    largest_sub = f"{k.largest_name} · mean of NASA min/max" if k.largest_name else "No diameter data"
    if math.isnan(k.closest_km):
        closest, closest_sub = dp.NOT_PROVIDED, "No miss-distance data"
    else:
        closest = f"{k.closest_lunar:,.2f} LD"
        closest_sub = f"{k.closest_km:,.0f} km · {k.closest_name} · {k.closest_date}"
    cards = [
        kpi_card("Unique asteroids", f"{k.total_unique:,}", "In current selection", True),
        kpi_card("Potentially hazardous", f"{k.hazardous_unique:,}", "NASA's flag, not a prediction of impact"),
        kpi_card("Largest estimated diameter", largest, largest_sub),
        kpi_card("Closest approach", closest, closest_sub),
    ]
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def ensure_selection(df: pd.DataFrame) -> Optional[str]:
    """Keep st.session_state['selected_row'] valid for the filtered data (default: closest approach)."""
    if df.empty:
        st.session_state.pop("selected_row", None)
        return None
    options = df["row_id"].tolist()
    if st.session_state.get("selected_row") not in options:
        ranged = df.dropna(subset=["miss_km"])
        st.session_state["selected_row"] = ranged.loc[ranged["miss_km"].idxmin(), "row_id"] if not ranged.empty else options[0]
    return st.session_state["selected_row"]


def section(title: str, note: str = "") -> None:
    st.markdown(f'<div class="section-title">{esc(title)}</div>' + (f'<p class="section-note">{esc(note)}</p>' if note else ""),
                unsafe_allow_html=True)


def render_scene(df: pd.DataFrame, selected: Optional[str]) -> None:
    section("3D explorer", "Drag to rotate, scroll or pinch to zoom, hover a marker for NASA's measured values. "
            "Marker size reflects estimated diameter. Amber markers are flagged potentially hazardous by NASA.")
    st.markdown(f'<div class="banner">{viz.SCENE_LABEL}</div>', unsafe_allow_html=True)
    fig, plotted, unplaced = viz.build_scene(df, selected)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})
    note = ("Layout rule: direction is pseudo-random from a hash of each NASA ID (no orbital meaning); "
            "distance from Earth is a log-compressed function of the real miss distance; Sun and Earth are placed arbitrarily. "
            "This is not an orbit simulation.")
    if unplaced:
        note += f" {unplaced} object(s) without a miss distance are not shown in the scene."
    st.caption(note)


def render_analytics(df: pd.DataFrame) -> None:
    section("Analytics", "All charts use the filtered NASA values. Each bar or point is one close-approach record.")
    t1, t2, t3 = st.tabs(["Diameter distribution", "Closest approaches", "Relative velocity"])
    with t1:
        st.plotly_chart(viz.diameter_distribution(df), use_container_width=True,theme=None, config={"displaylogo": False})
        st.caption("Diameter is the mean of NASA's estimated minimum and maximum (meters). It is an estimate, and unrelated to miss distance.")
    with t2:
        st.plotly_chart(viz.closest_approaches(df), use_container_width=True,theme=None, config={"displaylogo": False})
        st.caption("Miss distance is how far the object passes from Earth, not how large it is. 1 LD is the mean Earth–Moon distance.")
    with t3:
        st.plotly_chart(viz.velocity_distribution(df), use_container_width=True,theme=None, config={"displaylogo": False})
        st.caption("Velocity relative to Earth at close approach. This is not the asteroid's orbital speed around the Sun.")


def render_table(df: pd.DataFrame, ds: dict[str, Any]) -> None:
    section("Asteroid table", "Click a column header to sort; use the search icon in the table toolbar to find text.")
    table = dp.to_display_frame(df)
    st.dataframe(
        table, use_container_width=True, hide_index=True, height=380,
        column_config={
            "Mean diameter (m)": st.column_config.NumberColumn(format="%.1f"),
            "Min diameter (m)": st.column_config.NumberColumn(format="%.1f"),
            "Max diameter (m)": st.column_config.NumberColumn(format="%.1f"),
            "Relative velocity (km/s)": st.column_config.NumberColumn(format="%.2f"),
            "Relative velocity (km/h)": st.column_config.NumberColumn(format="%.0f"),
            "Miss distance (km)": st.column_config.NumberColumn(format="%.0f"),
            "Miss distance (lunar distances)": st.column_config.NumberColumn(format="%.2f"),
            "Miss distance (AU)": st.column_config.NumberColumn(format="%.5f"),
            "NASA JPL page": st.column_config.LinkColumn(display_text="Open"),
        },
    )
    export = table.copy()
    export["Data source"] = "NASA NeoWs (live)" if ds["source"] == "live" else SAMPLE_LABEL
    suffix = "_SAMPLE" if ds["source"] == "sample" else ""
    st.download_button("Download filtered data (CSV)", data=export.to_csv(index=False).encode("utf-8"),
                       file_name=f"astra3d_neo_{ds['start']}_{ds['end']}{suffix}.csv", mime="text/csv")


def _detail(key: str, value: str) -> str:
    return f'<div class="detail"><div class="k">{esc(key)}</div><div class="v">{esc(value)}</div></div>'


def render_details(df: pd.DataFrame, ds: dict[str, Any]) -> None:
    section("Selected object", "Values below come from the NASA record for the selected close approach.")
    if df.empty:
        st.info("No object to show. Adjust the filters.")
        return
    labels = {r.row_id: f"{r.name} · {r.approach_date:%Y-%m-%d}" if pd.notna(r.approach_date) else str(r.name)
              for r in df.itertuples()}
    chosen = st.selectbox("Object", options=list(labels), format_func=labels.get, key="selected_row")
    row = df[df["row_id"] == chosen].iloc[0]
    approach = row["approach_date"].strftime("%Y-%m-%d") if pd.notna(row["approach_date"]) else dp.NOT_PROVIDED
    time_txt = row["approach_time"].strftime("%H:%M") if pd.notna(row["approach_time"]) else dp.NOT_PROVIDED
    items = [
        ("Name", str(row["name"])), ("NASA ID", str(row["id"])),
        ("Potentially hazardous (NASA flag)", dp.fmt_hazard(row["hazardous"])),
        ("Sentry object", dp.fmt_hazard(row["sentry"])),
        ("Absolute magnitude (H)", dp.fmt_number(row["h_mag"], 2)),
        ("Estimated diameter, min", dp.fmt_diameter(row["diameter_min_m"])),
        ("Estimated diameter, max", dp.fmt_diameter(row["diameter_max_m"])),
        ("Estimated diameter, mean", dp.fmt_diameter(row["diameter_mean_m"])),
        ("Relative velocity", dp.fmt_number(row["velocity_kms"], 2, " km/s")),
        ("Relative velocity (per hour)", dp.fmt_number(row["velocity_kmh"], 0, " km/h")),
        ("Miss distance", dp.fmt_number(row["miss_km"], 0, " km")),
        ("Miss distance (lunar distances)", dp.fmt_number(row["miss_lunar"], 2, " LD")),
        ("Miss distance (AU)", dp.fmt_number(row["miss_au"], 5, " AU")),
        ("Approach date / time (as reported)", f"{approach} / {time_txt}"),
        ("Orbiting body", str(row["orbiting_body"])),
    ]
    st.markdown('<div class="detail-grid">' + "".join(_detail(k, v) for k, v in items) + "</div>", unsafe_allow_html=True)
    url = row["nasa_url"]
    if isinstance(url, str) and url.startswith("http"):
        st.link_button("Open NASA JPL record", url)
    elif ds["source"] == "sample":
        st.caption("Sample objects are synthetic and have no NASA record.")
    else:
        st.caption("NASA did not provide a detail URL for this object.")


def render_footer(ds: Optional[dict[str, Any]]) -> None:
    stamp = ds["retrieved_at"].strftime("%Y-%m-%d %H:%M UTC") if ds else "n/a"
    st.markdown(_html(f"""
 /div>"""), unsafe_allow_html=True)


# ------------------------------------------------------------------------ main


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    header_slot = st.empty()  # filled after loading so it shows the newest status
    start, end, clicked, use_sample = render_hero()

    if start is not None and end is not None and (clicked or not st.session_state.get("initialized")):
        st.session_state["initialized"] = True
        load_dataset(start, end, use_sample, force_refresh=clicked)

    ds: Optional[dict[str, Any]] = st.session_state.get("dataset")
    error: Optional[str] = st.session_state.get("load_error")
    header_slot.markdown(header_html(ds, error), unsafe_allow_html=True)

    if error:
        st.error(error + (" The view below still shows the previously loaded data." if ds else ""))
    if ds is None:
        st.info("No data loaded yet. Choose a date range and select Fetch data.")
        render_footer(None)
        return
    if ds["source"] == "sample":
        st.warning(f"{SAMPLE_LABEL}. Values are synthetic and generated locally.")
    elif ds["using_demo_key"]:
        st.caption("Using DEMO_KEY (about 30 requests/hour, 50/day per IP). Add your own free key in .env for higher limits.")
    if ds["df"].empty:
        st.info(f"NASA returned no objects for {ds['start']} to {ds['end']}. Try another date range.")
        render_footer(ds)
        return

    filtered = render_filters(ds)
    render_kpis(filtered)
    selected = ensure_selection(filtered)
    if filtered.empty:
        st.info("No objects match the current filters. Use Reset filters in the sidebar.")
    else:
        render_scene(filtered, selected)
        render_analytics(filtered)
    render_table(filtered, ds)
    render_details(filtered, ds)
    render_footer(ds)


main() 
