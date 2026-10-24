"""Plotly figures for ASTRA 3D.

The 3D scene is SCHEMATIC. Marker positions come from
``data_processing.illustrative_coordinates`` and are not real orbital
positions. All real NASA measurements appear only in hover text and charts.
"""

from __future__ import annotations

import html
import math
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import data_processing as dp

FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
TEXT = "#c9d4e8"
MUTED = "#8d9bbd"
GRID = "rgba(130,150,200,0.14)"
CYAN = "#4cc9f0"
AMBER = "#f4a259"
SUN = "#ffb347"
EARTH = "#4da3ff"
HAZARD_COLORS = {
    "Potentially hazardous": AMBER,
    "Not hazardous": CYAN,
    "Status not provided": MUTED,
}
SCENE_LABEL = "SCHEMATIC 3D EXPLORER — NOT TO SCALE; POSITIONS ARE ILLUSTRATIVE"


def _style(fig: go.Figure, height: int, title: Optional[str] = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=TEXT, size=12),
        height=height,
        margin=dict(l=10, r=10, t=48 if title else 16, b=10),
        title=dict(text=title, x=0.0, font=dict(size=14)) if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#0b1230", bordercolor="rgba(120,150,220,0.4)", font=dict(family=FONT, size=12)),
    )
    return fig


def empty_figure(message: str, height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                       font=dict(size=14, color=MUTED))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, height)


def _axes(fig: go.Figure, x_title: str, y_title: str) -> None:
    fig.update_xaxes(title=x_title, gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(title=y_title, gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)


# ------------------------------------------------------------------ 3D scene


def _marker_sizes(diameter_m: pd.Series) -> np.ndarray:
    """Marker size (px) from mean diameter on a log scale; 5 px if unknown."""
    d = diameter_m.to_numpy(dtype=float)
    scaled = (np.log10(np.clip(d, 10.0, 5000.0)) - 1.0) / (math.log10(5000.0) - 1.0)
    return np.where(np.isnan(d), 5.0, 5.0 + 12.0 * scaled)


def _hover(row: pd.Series) -> str:
    name = html.escape(str(row["name"]))
    date_txt = row["approach_date"].strftime("%Y-%m-%d") if pd.notna(row["approach_date"]) else dp.NOT_PROVIDED
    miss_km = dp.fmt_number(row["miss_km"], 0, " km")
    miss_ld = dp.fmt_number(row["miss_lunar"], 2, " LD")
    return (
        f"<b>{name}</b><br>"
        f"Est. diameter (mean of NASA min/max): {dp.fmt_diameter(row['diameter_mean_m'])}<br>"
        f"Relative velocity: {dp.fmt_number(row['velocity_kms'], 2, ' km/s')}<br>"
        f"Miss distance: {miss_km} ({miss_ld})<br>"
        f"Potentially hazardous: {dp.fmt_hazard(row['hazardous'])}<br>"
        f"Approach date: {date_txt}<br>"
        "<i>Marker position is illustrative only</i>"
    )


def build_scene(df: pd.DataFrame, selected_row_id: Optional[str] = None) -> tuple[go.Figure, int, int]:
    """Return (figure, objects_plotted, objects_not_plotted)."""
    coords = dp.illustrative_coordinates(df)
    placed = coords.dropna(subset=["x", "y", "z"])
    fig = go.Figure()

    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0], mode="markers+text", text=["Sun (schematic)"], textposition="top center",
        textfont=dict(color=SUN, size=11), name="Sun", showlegend=False,
        marker=dict(size=26, color=SUN, opacity=0.95, line=dict(color="#ffd9a0", width=2)),
        hovertemplate="<b>Sun</b><br>Schematic marker, not to scale<extra></extra>",
    ))
    fig.add_trace(go.Scatter3d(
        x=[dp.EARTH_X], y=[0], z=[0], mode="markers+text", text=["Earth (schematic)"], textposition="top center",
        textfont=dict(color=EARTH, size=11), name="Earth", showlegend=False,
        marker=dict(size=13, color=EARTH, opacity=0.95, line=dict(color="#a9d2ff", width=2)),
        hovertemplate="<b>Earth</b><br>Schematic marker, not to scale<extra></extra>",
    ))

    for label, color in HAZARD_COLORS.items():
        if label == "Potentially hazardous":
            sub = placed[dp.flag_mask(placed["hazardous"], True)]
        elif label == "Not hazardous":
            sub = placed[dp.flag_mask(placed["hazardous"], False)]
        else:
            sub = placed[placed["hazardous"].isna().to_numpy(dtype=bool)]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter3d(
            x=sub["x"], y=sub["y"], z=sub["z"], mode="markers", name=label,
            marker=dict(size=_marker_sizes(sub["diameter_mean_m"]), color=color, opacity=0.88,
                        line=dict(color="rgba(255,255,255,0.35)", width=0.5)),
            hoverinfo="text",
            text=[_hover(r) for _, r in sub.iterrows()],
        ))

    if selected_row_id is not None:
        sel = placed[placed["row_id"] == selected_row_id]
        if not sel.empty:
            fig.add_trace(go.Scatter3d(
                x=sel["x"], y=sel["y"], z=sel["z"], mode="markers", name="Selected", hoverinfo="skip",
                marker=dict(size=_marker_sizes(sel["diameter_mean_m"]) + 9, color="rgba(0,0,0,0)",
                            symbol="circle-open", line=dict(color="#ffffff", width=3)),
            ))

    hidden_axis = dict(visible=False, showbackground=False, showgrid=False, zeroline=False)
    fig.update_layout(
        scene=dict(
            xaxis=hidden_axis, yaxis=hidden_axis, zaxis=hidden_axis, aspectmode="data", bgcolor="rgba(0,0,0,0)",
            camera=dict(eye=dict(x=0.9, y=-1.5, z=0.8)), dragmode="orbit",
        ),
        uirevision="astra-scene",  # keep the user's camera when data/filters change
        annotations=[dict(text=SCENE_LABEL, x=0.01, y=0.99, xref="paper", yref="paper", showarrow=False,
                          xanchor="left", yanchor="top", font=dict(size=11, color=AMBER))],
    )
    _style(fig, height=600)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(
        orientation="h", yanchor="bottom", y=0.0, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0)"))
    return fig, len(placed), len(df) - len(placed)


# ------------------------------------------------------------------- analytics


def diameter_distribution(df: pd.DataFrame) -> go.Figure:
    valid = df[df["diameter_mean_m"] > 0].dropna(subset=["diameter_mean_m"])
    if valid.empty:
        return empty_figure("No diameter values available for the current selection.")
    logs = np.log10(valid["diameter_mean_m"].to_numpy(dtype=float))
    lo, hi = float(logs.min()), float(logs.max())
    if hi - lo < 1e-9:
        lo, hi = lo - 0.25, hi + 0.25
    edges = np.linspace(lo, hi, 21)
    centers, width = (edges[:-1] + edges[1:]) / 2, edges[1] - edges[0]
    lo_m, hi_m = 10 ** edges[:-1], 10 ** edges[1:]

    fig = go.Figure()
    for label, sub in dp.split_by_hazard(valid):
        counts, _ = np.histogram(np.log10(sub["diameter_mean_m"].to_numpy(dtype=float)), bins=edges)
        fig.add_trace(go.Bar(
            x=centers, y=counts, width=width * 0.94, name=label, marker_color=HAZARD_COLORS[label],
            customdata=np.column_stack([lo_m, hi_m]),
            hovertemplate="%{customdata[0]:,.0f} to %{customdata[1]:,.0f} m<br>Close approaches: %{y}<extra>" + label + "</extra>",
        ))
    ticks = [t for t in (1, 3, 10, 30, 100, 300, 1000, 3000, 10000) if lo - 0.3 <= math.log10(t) <= hi + 0.3]
    fig.update_layout(barmode="stack", bargap=0.05)
    _axes(fig, "Mean estimated diameter (m, log scale)", "Close-approach records")
    if ticks:
        fig.update_xaxes(tickvals=[math.log10(t) for t in ticks], ticktext=[f"{t:,}" for t in ticks])
    return _style(fig, 340)


def closest_approaches(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    valid = df.dropna(subset=["miss_lunar"])
    if valid.empty:
        return empty_figure("No miss-distance values available for the current selection.")
    top = valid.nsmallest(top_n, "miss_lunar").iloc[::-1]  # closest at the top of a horizontal bar chart
    labels = [f"{n} · {d:%b %d}" if pd.notna(d) else str(n) for n, d in zip(top["name"], top["approach_date"])]
    colors = [HAZARD_COLORS["Potentially hazardous"] if h else HAZARD_COLORS["Not hazardous"]
              for h in dp.flag_mask(top["hazardous"], True)]
    fig = go.Figure(go.Bar(
        x=top["miss_lunar"], y=labels, orientation="h", marker_color=colors,
        customdata=np.column_stack([top["miss_km"], top["miss_au"]]),
        hovertemplate="%{y}<br>%{x:,.2f} lunar distances<br>%{customdata[0]:,.0f} km<br>%{customdata[1]:.5f} AU<extra></extra>",
    ))
    fig.add_vline(x=1, line=dict(color=MUTED, width=1, dash="dot"), annotation_text="Moon's mean distance (1 LD)",
                  annotation_font=dict(size=10, color=MUTED), annotation_position="top right")
    _axes(fig, "Miss distance (lunar distances; 1 LD ≈ 384,400 km)", "")
    fig.update_yaxes(automargin=True)
    fig.update_layout(showlegend=False)
    return _style(fig, max(320, 30 * len(top) + 90))


def velocity_distribution(df: pd.DataFrame) -> go.Figure:
    valid = df.dropna(subset=["velocity_kms"])
    if valid.empty:
        return empty_figure("No velocity values available for the current selection.")
    fig = go.Figure()
    for label, sub in dp.split_by_hazard(valid):
        fig.add_trace(go.Histogram(
            x=sub["velocity_kms"], name=label, marker_color=HAZARD_COLORS[label], nbinsx=20,
            hovertemplate="%{x} km/s<br>Close approaches: %{y}<extra>" + label + "</extra>",
        ))
    fig.update_layout(barmode="stack", bargap=0.05)
    _axes(fig, "Relative velocity to Earth at close approach (km/s)", "Close-approach records")
    return _style(fig, 340)