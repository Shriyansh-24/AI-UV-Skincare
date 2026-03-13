# ============================================================
# UV Skincare Advisor — core/charts.py
# Step 4: Data Visualizations
# Team role: DESIGNER + STATISTICIAN
# ============================================================

import plotly.graph_objects as go
from core.skin_advisor import calculate_burn_time

UV_BAND_COLORS = {
    "low":       "#22c55e",
    "moderate":  "#eab308",
    "high":      "#f97316",
    "very_high": "#ef4444",
    "extreme":   "#a855f7",
}

FITZPATRICK_COLORS = [
    "#FDDBB4", "#F5C8A0", "#E8A87C",
    "#C68642", "#8D5524", "#4A2912",
]

FITZPATRICK_LABELS = [
    "Type I — Very Fair", "Type II — Fair",
    "Type III — Medium",  "Type IV — Olive",
    "Type V — Brown",     "Type VI — Dark",
]

PLOT_BG   = "#1e2130"
PAPER_BG  = "#161b2a"
GRID_COLOR = "#2d3348"
TEXT_COLOR = "#e2e8f0"
FONT_FAMILY = "Inter, system-ui, sans-serif"


def _base_layout(title, height=360):
    return dict(
        title=dict(text=title, font=dict(size=15, color=TEXT_COLOR, family=FONT_FAMILY), x=0.01),
        height=height,
        margin=dict(t=55, b=55, l=55, r=55),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR, family=FONT_FAMILY),
    )


def uv_gauge(uv_index: float, city: str) -> go.Figure:
    """Speedometer-style UV Index gauge with WHO risk bands."""

    if uv_index <= 2:   needle_color = "#22c55e"
    elif uv_index <= 5: needle_color = "#eab308"
    elif uv_index <= 7: needle_color = "#f97316"
    elif uv_index <= 10:needle_color = "#ef4444"
    else:               needle_color = "#a855f7"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=uv_index,
        number={"font": {"size": 56, "color": needle_color, "family": FONT_FAMILY}},
        gauge={
            "axis": {
                "range": [0, 12],
                "tickwidth": 1,
                "tickcolor": "#cbd5e1",
                "tickfont": {"color": "#64748b", "size": 12},
                "tickvals": [0, 2, 5, 7, 10, 12],
            },
            "bar": {"color": needle_color, "thickness": 0.22},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  2],  "color": "#dcfce7"},
                {"range": [2,  5],  "color": "#fef9c3"},
                {"range": [5,  7],  "color": "#ffedd5"},
                {"range": [7,  10], "color": "#fee2e2"},
                {"range": [10, 12], "color": "#f3e8ff"},
            ],
            "threshold": {
                "line": {"color": needle_color, "width": 3},
                "thickness": 0.85,
                "value": uv_index
            }
        },
        title={
            "text": f"UV Index · {city}<br><span style='font-size:0.75em;color:#94a3b8'>WHO Risk Scale 0–12</span>",
            "font": {"size": 15, "color": TEXT_COLOR, "family": FONT_FAMILY}
        },
    ))

    fig.update_layout(
        height=300,
        margin=dict(t=80, b=10, l=30, r=30),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
    )
    return fig


def hourly_uv_chart(hourly_labels, hourly_uv, hourly_cloud, current_hour_idx, city):
    """Dual-axis bar+line chart: UV by hour + cloud cover overlay."""

    bar_colors = []
    for uv in hourly_uv:
        if uv <= 2:    bar_colors.append(UV_BAND_COLORS["low"])
        elif uv <= 5:  bar_colors.append(UV_BAND_COLORS["moderate"])
        elif uv <= 7:  bar_colors.append(UV_BAND_COLORS["high"])
        elif uv <= 10: bar_colors.append(UV_BAND_COLORS["very_high"])
        else:          bar_colors.append(UV_BAND_COLORS["extreme"])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=hourly_labels, y=hourly_uv,
        name="UV Index",
        marker_color=bar_colors,
        opacity=0.85,
        yaxis="y1",
        hovertemplate="<b>%{x}</b><br>UV Index: %{y}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=hourly_labels, y=hourly_cloud,
        name="Cloud Cover %",
        mode="lines",
        line={"color": "#93c5fd", "width": 2, "dash": "dot"},
        yaxis="y2",
        opacity=0.9,
        hovertemplate="<b>%{x}</b><br>Cloud: %{y}%<extra></extra>",
    ))

    if 0 <= current_hour_idx < len(hourly_labels):
        fig.add_vline(
            x=current_hour_idx,
            line_width=2, line_dash="dash", line_color="#f97316",
            annotation_text="Now",
            annotation_font_color="#f97316",
            annotation_font_size=12,
        )

    layout = _base_layout(f"Hourly UV Forecast · {city}", height=360)
    layout.update(
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(color=TEXT_COLOR)),
        yaxis=dict(
            title="UV Index",
            range=[0, max(max(hourly_uv) + 1, 4)],
            gridcolor=GRID_COLOR,
            title_font=dict(color="#64748b"),
            tickfont=dict(color="#64748b"),
        ),
        yaxis2=dict(
            title="Cloud Cover (%)",
            range=[0, 100], overlaying="y", side="right",
            gridcolor=GRID_COLOR,
            title_font=dict(color="#93c5fd"),
            tickfont=dict(color="#93c5fd"),
        ),
        xaxis=dict(
            title="Hour",
            tickangle=-45,
            tickfont=dict(color="#64748b", size=11),
            tickvals=hourly_labels[::2],
            ticktext=hourly_labels[::2],
            title_font=dict(color="#64748b"),
        ),
    )
    fig.update_layout(layout)
    return fig


def burn_time_chart(uv_index: float, activity: str) -> go.Figure:
    """Horizontal bar chart comparing burn times across all 6 skin types."""

    if uv_index <= 0:
        fig = go.Figure()
        fig.add_annotation(
            text="UV Index is 0 — no burn risk currently 🌙",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        fig.update_layout(height=320, paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG)
        return fig

    burn_times, label_texts = [], []
    for fitz_id in range(1, 7):
        burn = calculate_burn_time(uv_index, fitz_id, activity)
        bt   = burn["burn_time_min"] if not burn["no_risk"] else 0
        burn_times.append(bt)
        label_texts.append(f"{bt} min")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=burn_times, y=FITZPATRICK_LABELS,
        orientation="h",
        marker_color=FITZPATRICK_COLORS,
        marker_line_color="#e2e8f0",
        marker_line_width=1,
        text=label_texts,
        textposition="outside",
        textfont=dict(color=TEXT_COLOR, size=12),
        hovertemplate=(
            "<b>%{y}</b><br>Burn time: %{x} min<br>"
            f"UV Index: {uv_index} · {activity}<extra></extra>"
        ),
    ))

    fig.add_vline(
        x=20, line_width=1.5, line_dash="dash", line_color="#ef4444",
        annotation_text="20 min",
        annotation_position="top right",
        annotation_font_color="#ef4444",
        annotation_font_size=11,
    )

    layout = _base_layout(
        f"Unprotected Burn Time by Skin Type · UV {uv_index} · {activity}",
        height=380
    )
    layout.update(
        margin=dict(t=55, b=55, l=140, r=80),
        xaxis=dict(
            title="Minutes to sunburn (without sunscreen)",
            gridcolor=GRID_COLOR,
            title_font=dict(color="#64748b"),
            tickfont=dict(color="#64748b"),
        ),
        yaxis=dict(
            tickfont=dict(color=TEXT_COLOR),
            autorange="reversed",
        ),
        showlegend=False,
    )
    fig.update_layout(layout)
    return fig