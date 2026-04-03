"""
Reusable Plotly chart components for CityBCPAgent.
"""
import plotly.graph_objects as go
import plotly.express as px

from config.settings import SECTORS, ALERTS, HEATMAP_THRESHOLDS, HEATMAP_COLORS

# ─── Color Palette ───────────────────────────────────────────────────────────
SECTOR_COLORS = {sid: info["color"] for sid, info in SECTORS.items()}

STATUS_COLORS = {
    "CRITICAL": "#dc2626",
    "WARNING": "#d97706",
    "HEALTHY": "#16a34a",
}

BUFFER_COLORS = [
    [0, "#dc2626"],     # 0 days = red
    [0.15, "#ea580c"],  # ~3 days
    [0.35, "#d97706"],  # ~7 days
    [0.5, "#eab308"],   # ~10 days
    [1, "#16a34a"],     # 20+ days = green
]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=12, color="#374151"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def apply_layout(fig, title=None, height=400):
    fig.update_layout(**CHART_LAYOUT, height=height)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14, color="#1f2937")))
    fig.update_xaxes(gridcolor="#e5e7eb", zeroline=False)
    fig.update_yaxes(gridcolor="#e5e7eb", zeroline=False)
    return fig


# ─── Chart Builders ──────────────────────────────────────────────────────────

def stacked_bar_by_sector(df, x_col, y_col, color_col="sector_id", title=None):
    """Stacked bar chart grouped by sector."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        barmode="stack", text_auto=True,
    )
    return apply_layout(fig, title)


def multi_line(df, x_col, y_col, color_col, title=None, height=400):
    """Multi-line chart with optional threshold lines."""
    fig = px.line(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        markers=True, text=y_col,
    )
    fig.update_traces(textposition="top center", textfont_size=10)
    return apply_layout(fig, title, height)


def buffer_trend_with_thresholds(df, x_col, y_col, color_col, title=None):
    """Buffer days trend with critical/warning threshold lines."""
    fig = px.line(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        markers=True,
    )
    # Add threshold lines
    fig.add_hline(
        y=ALERTS["buffer_critical_days"], line_dash="dash",
        line_color="#dc2626", annotation_text="Critical (3 days)",
        annotation_position="top right",
    )
    fig.add_hline(
        y=ALERTS["buffer_warning_days"], line_dash="dash",
        line_color="#d97706", annotation_text="Warning (7 days)",
        annotation_position="top right",
    )
    return apply_layout(fig, title)


def horizontal_bar(df, x_col, y_col, color_col=None, color_map=None, title=None):
    """Horizontal bar chart (e.g., buffer days by site)."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=color_map or SECTOR_COLORS,
        orientation="h", text_auto=True,
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_layout(fig, title, height=max(300, len(df) * 22))


def heatmap(df_pivot, title=None, colorscale="RdYlGn"):
    """Heatmap from a pivoted dataframe (index=sites, columns=dates)."""
    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.values,
        x=df_pivot.columns.tolist(),
        y=df_pivot.index.tolist(),
        colorscale=colorscale,
        colorbar=dict(title="Days"),
        hoverongaps=False,
    ))
    return apply_layout(fig, title, height=max(400, len(df_pivot) * 22))


def dual_axis_bar_line(df, x_col, bar_col, line_col, title=None):
    """Dual-axis: bars (left Y) + line (right Y)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[x_col], y=df[bar_col], name=bar_col,
        marker_color="#3b82f6", opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[line_col], name=line_col,
        yaxis="y2", mode="lines+markers",
        line=dict(color="#ef4444", width=2),
    ))
    fig.update_layout(
        yaxis=dict(title=bar_col),
        yaxis2=dict(title=line_col, overlaying="y", side="right"),
    )
    return apply_layout(fig, title)


def scatter_chart(df, x_col, y_col, color_col=None, title=None):
    """Scatter plot."""
    fig = px.scatter(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
    )
    return apply_layout(fig, title)


def pie_chart(df, values_col, names_col, title=None):
    """Simple pie/donut chart."""
    fig = px.pie(df, values=values_col, names=names_col, hole=0.4)
    return apply_layout(fig, title, height=350)


def bar_chart(df, x_col, y_col, color_col=None, color_map=None, title=None, barmode="group"):
    """Standard vertical bar chart."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=color_map or SECTOR_COLORS,
        barmode=barmode, text_auto=True,
    )
    return apply_layout(fig, title)


def treemap(df, path_cols, values_col, color_col=None, title=None):
    """Treemap chart."""
    fig = px.treemap(df, path=path_cols, values=values_col, color=color_col)
    return apply_layout(fig, title, height=500)


# ─── Site Health Heat Map ────────────────────────────────────────────────────

def _get_heatmap_color(value, metric_key):
    """Return color string for a single value based on HEATMAP_THRESHOLDS."""
    if value is None or (isinstance(value, float) and (value != value)):  # NaN check
        return HEATMAP_COLORS["gray"]
    cfg = HEATMAP_THRESHOLDS[metric_key]
    if cfg.get("reverse"):
        # Buffer days: higher = better
        if value >= cfg["green_min"]:
            return HEATMAP_COLORS["green"]
        if value >= cfg["yellow_min"]:
            return HEATMAP_COLORS["yellow"]
        if value >= cfg["amber_min"]:
            return HEATMAP_COLORS["amber"]
        return HEATMAP_COLORS["red"]
    else:
        # Diesel price, blackout hr, expense %: lower = better
        if value < cfg["green_max"]:
            return HEATMAP_COLORS["green"]
        if value < cfg["yellow_max"]:
            return HEATMAP_COLORS["yellow"]
        if value <= cfg["amber_max"]:
            return HEATMAP_COLORS["amber"]
        return HEATMAP_COLORS["red"]


def _get_heatmap_icon(value, metric_key):
    """Return status icon based on threshold color."""
    color = _get_heatmap_color(value, metric_key)
    if color == HEATMAP_COLORS["green"]:
        return "🟢"
    if color == HEATMAP_COLORS["yellow"]:
        return "🟡"
    if color == HEATMAP_COLORS["amber"]:
        return "🟠"
    if color == HEATMAP_COLORS["red"]:
        return "🔴"
    return "⚪"


def _get_heatmap_label(value, metric_key):
    """Return display text for a cell (icon + value)."""
    if value is None or (isinstance(value, float) and (value != value)):
        return "⚪ N/A"
    icon = _get_heatmap_icon(value, metric_key)
    if metric_key == "diesel_price":
        return f"{icon} {value:,.0f}"
    if metric_key == "blackout_hr":
        return f"{icon} {value:.1f}"
    if metric_key == "expense_pct":
        return f"{icon} {value:.2f}%"
    if metric_key == "buffer_days":
        return f"{icon} {value:.1f}"
    return f"{icon} {round(value, 1)}"


def site_health_heatmap(df, title="Site Health Heat Map"):
    """
    Build a 4-metric heatmap from a DataFrame with columns:
        site_id, sector_id, diesel_price, blackout_hr, expense_pct, buffer_days

    Returns a Plotly Figure with colored cells (Green/Yellow/Amber/Red).
    """
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False, font=dict(size=16))
        return apply_layout(fig, title, height=200)

    metrics = ["diesel_price", "blackout_hr", "expense_pct", "buffer_days"]
    metric_labels = [HEATMAP_THRESHOLDS[m]["label"] for m in metrics]
    sites = df["site_id"].tolist()

    # Build color matrix and text matrix
    colors = []
    texts = []
    hover_texts = []
    for m in metrics:
        row_colors = []
        row_texts = []
        row_hovers = []
        for _, r in df.iterrows():
            val = r.get(m)
            row_colors.append(_get_heatmap_color(val, m))
            row_texts.append(_get_heatmap_label(val, m))
            row_hovers.append(f"{r['site_id']} ({r.get('sector_id', '')})<br>"
                              f"{HEATMAP_THRESHOLDS[m]['label']}: {_get_heatmap_label(val, m)}")
        colors.append(row_colors)
        texts.append(row_texts)
        hover_texts.append(row_hovers)

    # Use a dummy z-matrix (0-3) mapped to the 4 colors via a discrete colorscale
    color_to_z = {
        HEATMAP_COLORS["green"]: 0,
        HEATMAP_COLORS["yellow"]: 1,
        HEATMAP_COLORS["amber"]: 2,
        HEATMAP_COLORS["red"]: 3,
        HEATMAP_COLORS["gray"]: 1.5,
    }
    z = [[color_to_z.get(c, 1.5) for c in row] for row in colors]

    colorscale = [
        [0.0, HEATMAP_COLORS["green"]],
        [0.33, HEATMAP_COLORS["yellow"]],
        [0.66, HEATMAP_COLORS["amber"]],
        [1.0, HEATMAP_COLORS["red"]],
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=sites,
        y=metric_labels,
        text=texts,
        texttemplate="%{text}",
        textfont=dict(size=12, color="white"),
        hovertext=hover_texts,
        hoverinfo="text",
        colorscale=colorscale,
        zmin=0, zmax=3,
        showscale=False,
        xgap=2, ygap=2,
    ))

    height = max(280, 70 * len(metrics))
    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        xaxis=dict(side="bottom", tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(autorange="reversed"),
    )
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14, color="#1f2937")))

    return fig


def render_heatmap_legend():
    """Return HTML string for the heatmap color legend."""
    return """
    <div style="display:flex;gap:20px;justify-content:center;padding:8px 0;font-size:12px;color:#475569">
        <span><span style="display:inline-block;width:14px;height:14px;background:#22c55e;border-radius:3px;vertical-align:middle"></span> Green — Healthy</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:#eab308;border-radius:3px;vertical-align:middle"></span> Yellow — Watch</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:#f97316;border-radius:3px;vertical-align:middle"></span> Amber — Warning</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:#ef4444;border-radius:3px;vertical-align:middle"></span> Red — Critical</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:#9ca3af;border-radius:3px;vertical-align:middle"></span> Gray — No Data</span>
    </div>
    """
