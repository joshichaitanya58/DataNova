try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    from mpl_toolkits.mplot3d import Axes3D
except ImportError:
    matplotlib = None
    plt = None
    sns = None
    Axes3D = None
import base64
from io import BytesIO
import pandas as pd
import numpy as np
import logging

from .cleaning_service import convert_currency, convert_percentage

logger = logging.getLogger(__name__)

# Primary Design System Colors
PRIMARY_COLOR = '#4F46E5'  # Indigo
VIOLET_COLOR = '#7C3AED'   # Violet
CYAN_COLOR = '#06B6D4'     # Cyan
GREEN_COLOR = '#10B981'    # Emerald


def fig_to_base64(fig):
    """
    Converts a Matplotlib figure into a base64 encoded PNG string.
    Optimized for high rendering speed, crisp resolution, and low latency.
    """
    if fig is None or plt is None:
        return None
    buf = BytesIO()
    try:
        fig.tight_layout()
    except Exception as e:
        logger.warning(f"tight_layout failed: {e}")
    fig.savefig(buf, format="png", bbox_inches='tight', transparent=True, dpi=120)
    try:
        plt.close(fig)
    except Exception:
        pass
    return base64.b64encode(buf.getbuffer()).decode("ascii")


def visualization_sample(df, max_rows=3000):
    """
    Returns a deterministic sample of up to max_rows specifically for fast rendering.
    """
    if len(df) <= max_rows:
        return df
    return df.sample(n=max_rows, random_state=42)


def recommend_chart(x_type, y_type=None, purpose=None):
    """
    Recommends chart types based on semantic column types and analytical intent.
    """
    if y_type is None:
        if x_type == "measure":
            return ["histogram", "boxplot"]
        if x_type == "categorical":
            return ["bar"]
        if x_type == "datetime":
            return ["line"]

    if x_type == "datetime" and y_type == "measure":
        return ["line"]
    if x_type == "categorical" and y_type == "measure":
        return ["bar"]
    if x_type == "measure" and y_type == "measure":
        return ["scatter"]
    if x_type == "categorical" and y_type == "categorical":
        return ["stacked_bar", "heatmap"]

    return ["table"]


def generate_missingness_heatmap(df):
    """
    Generates a missing value pattern heatmap visualization with adaptive width and clean label formatting.
    """
    if plt is None or sns is None:
        return None
    if df.isna().sum().sum() == 0:
        return None

    n_cols = len(df.columns)
    fig_w = max(8.0, min(16.0, n_cols * 0.45 + 2.0))
    fig, ax = plt.subplots(figsize=(fig_w, 3.8))
    
    label_size = max(7, min(9, int(110 / max(1, n_cols))))
    sns.heatmap(df.isna(), cbar=False, cmap='viridis', ax=ax, yticklabels=False)
    ax.tick_params(axis='x', rotation=45, labelsize=label_size)
    plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")
    ax.set_title('Missing Values Pattern Matrix (Yellow = Missing)', fontsize=11, fontweight='bold', pad=10)
    return fig_to_base64(fig)


def generate_correlation_heatmap(df, semantic_types, max_features=10):
    """
    Generates a clean, highly interpretable correlation heatmap.
    When a dataset has many numerical columns, it intelligently isolates the top 8-10
    most influential / strongly correlated metrics and uses a clean lower-triangular mask
    so business users can easily understand the chart without visual clutter.
    """
    if plt is None or sns is None:
        return None
    valid_types = ["measure", "currency", "percentage"]
    measure_cols = [c for c, t in semantic_types.items() if t in valid_types and c in df.columns]

    if len(measure_cols) < 2:
        return None

    num_df = df[measure_cols].copy()
    for col in measure_cols:
        num_df[col] = pd.to_numeric(convert_percentage(convert_currency(num_df[col])), errors="coerce")

    num_df.dropna(inplace=True)
    if num_df.empty or len(num_df.columns) < 2:
        return None

    # Calculate full correlation matrix
    full_corr = num_df.corr()

    # If more than max_features, pick top most correlated/meaningful features
    if len(full_corr.columns) > max_features:
        # Score each column by its maximum absolute correlation with other columns (excluding self 1.0)
        corr_scores = (full_corr.abs() - np.eye(len(full_corr))).max(axis=0)
        top_cols = corr_scores.sort_values(ascending=False).head(max_features).index.tolist()
        corr = full_corr.loc[top_cols, top_cols]
        is_focused = True
    else:
        corr = full_corr
        is_focused = False

    n_cols = len(corr.columns)

    # Clean lower-triangle mask to cut 50% duplicate clutter
    mask = np.triu(np.ones_like(corr, dtype=bool))

    # Standard clean figure dimensions
    fig, ax = plt.subplots(figsize=(8.5, 6.5))

    # Clean formatted column labels
    display_corr = corr.copy()
    display_corr.columns = [str(c)[:18] + '..' if len(str(c)) > 20 else str(c) for c in display_corr.columns]
    display_corr.index = [str(c)[:18] + '..' if len(str(c)) > 20 else str(c) for c in display_corr.index]

    # Large, bold, crystal clear annotations
    annot_kws = {"size": 9.5, "weight": "bold"}

    sns.heatmap(
        display_corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
        center=0,
        square=True,
        linewidths=1.2,
        linecolor='white',
        ax=ax,
        cbar=True,
        annot_kws=annot_kws,
        cbar_kws={"shrink": 0.75, "aspect": 18, "label": "Correlation"}
    )

    ax.tick_params(axis='x', rotation=40, labelsize=9)
    ax.tick_params(axis='y', rotation=0, labelsize=9)
    plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

    if is_focused:
        ax.set_title(f'Key Correlations Heatmap (Top {n_cols} High-Impact Metrics)', fontsize=13, fontweight='bold', pad=14)
    else:
        ax.set_title('Correlation Matrix Heatmap', fontsize=13, fontweight='bold', pad=14)

    return fig_to_base64(fig)


def build_plotly_payload(chart_type, title, x_data, y_data=None, z_data=None, categories=None, x_label="", y_label="", z_label=""):
    """
    Constructs high-end Plotly.js data and layout payloads for 2D and 3D charts with hover tooltips.
    """
    plotly_data = []
    layout = {
        "title": {"text": title, "font": {"family": "Space Grotesk, sans-serif", "size": 16, "color": "#F8FAFC"}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
        "hoverlabel": {"bgcolor": "#1E293B", "font": {"family": "Inter, sans-serif", "color": "#F8FAFC"}},
        "font": {"color": "#94A3B8"}
    }

    if chart_type == "scatter3d" and x_data and y_data and z_data:
        plotly_data.append({
            "type": "scatter3d",
            "mode": "markers",
            "x": x_data,
            "y": y_data,
            "z": z_data,
            "marker": {
                "size": 5,
                "color": z_data,
                "colorscale": "Viridis",
                "opacity": 0.88,
                "showscale": True,
                "colorbar": {"title": {"text": z_label or "Z", "side": "right"}, "len": 0.75, "thickness": 14}
            },
            "hovertemplate": f"<b>{x_label}</b>: %{{x}}<br><b>{y_label}</b>: %{{y}}<br><b>{z_label}</b>: %{{z}}<extra></extra>"
        })
        layout["scene"] = {
            "xaxis": {"title": {"text": x_label}, "gridcolor": "rgba(148, 163, 184, 0.2)", "showbackground": True, "backgroundcolor": "rgba(30, 41, 59, 0.2)"},
            "yaxis": {"title": {"text": y_label}, "gridcolor": "rgba(148, 163, 184, 0.2)", "showbackground": True, "backgroundcolor": "rgba(30, 41, 59, 0.2)"},
            "zaxis": {"title": {"text": z_label}, "gridcolor": "rgba(148, 163, 184, 0.2)", "showbackground": True, "backgroundcolor": "rgba(30, 41, 59, 0.2)"},
            "camera": {
                "eye": {"x": 1.55, "y": 1.55, "z": 1.2}
            },
            "aspectratio": {"x": 1.1, "y": 1.1, "z": 0.85}
        }
        layout["margin"] = {"l": 10, "r": 10, "t": 40, "b": 10}

    elif chart_type == "heatmap" and x_data and y_data and z_data is not None:
        plotly_data.append({
            "type": "heatmap",
            "z": z_data,
            "x": x_data,
            "y": y_data,
            "colorscale": "RdBu",
            "zmin": -1,
            "zmax": 1,
            "reversescale": True,
            "hoverongaps": False,
            "hovertemplate": "<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.2f}<extra></extra>"
        })
        layout["xaxis"] = {"tickangle": -45, "automargin": True, "gridcolor": "rgba(148, 163, 184, 0.15)"}
        layout["yaxis"] = {"automargin": True, "gridcolor": "rgba(148, 163, 184, 0.15)"}
        layout["margin"] = {"l": 90, "r": 30, "t": 60, "b": 100}

    elif chart_type == "bar":
        is_num = bool(y_data and len(y_data) > 0 and isinstance(y_data[0], (int, float)) and not (isinstance(y_data[0], float) and (np.isnan(y_data[0]) or np.isinf(y_data[0]))))
        plotly_data.append({
            "type": "bar",
            "x": x_data,
            "y": y_data,
            "marker": {
                "color": y_data if is_num else "#4F46E5",
                "colorscale": "Plasma",
                "line": {"color": "#6366F1", "width": 1}
            },
            "hovertemplate": f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": y_label, "gridcolor": "#334155"}

    elif chart_type == "line":
        plotly_data.append({
            "type": "scatter",
            "mode": "lines+markers",
            "x": x_data,
            "y": y_data,
            "line": {"color": "#06B6D4", "width": 3, "shape": "spline"},
            "marker": {"size": 7, "color": "#38BDF8"},
            "hovertemplate": f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": y_label, "gridcolor": "#334155"}

    elif chart_type == "scatter":
        plotly_data.append({
            "type": "scatter",
            "mode": "markers",
            "x": x_data,
            "y": y_data,
            "marker": {
                "size": 8,
                "color": "#7C3AED",
                "opacity": 0.7,
                "line": {"color": "#A855F7", "width": 1}
            },
            "hovertemplate": f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": y_label, "gridcolor": "#334155"}

    elif chart_type == "pie":
        plotly_data.append({
            "type": "pie",
            "labels": x_data,
            "values": y_data,
            "hole": 0.4,
            "textinfo": "label+percent",
            "hoverinfo": "label+value+percent",
            "marker": {"colors": ["#4F46E5", "#7C3AED", "#06B6D4", "#10B981", "#F59E0B", "#EC4899"]}
        })

    elif chart_type == "histogram":
        plotly_data.append({
            "type": "histogram",
            "x": x_data,
            "marker": {"color": "#10B981", "line": {"color": "#34D399", "width": 1}},
            "hovertemplate": f"{x_label}: %{{x}}<br>Count: %{{y}}<extra></extra>"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": "Frequency", "gridcolor": "#334155"}

    elif chart_type == "boxplot":
        plotly_data.append({
            "type": "box",
            "x": categories if categories else None,
            "y": y_data if y_data else x_data,
            "marker": {"color": "#F59E0B"},
            "boxpoints": "outliers"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": y_label, "gridcolor": "#334155"}

    elif chart_type == "violin":
        plotly_data.append({
            "type": "violin",
            "x": categories if categories else None,
            "y": y_data if y_data else x_data,
            "marker": {"color": "#06B6D4"},
            "box": {"visible": True},
            "meanline": {"visible": True},
            "points": "outliers"
        })
        layout["xaxis"] = {"title": x_label, "gridcolor": "#334155"}
        layout["yaxis"] = {"title": y_label, "gridcolor": "#334155"}

    return {"data": plotly_data, "layout": layout}


def generate_automatic_charts(df, semantic_types, max_charts=10):
    """
    Generates high-quality automatic charts tailored by semantic types and analytical intent,
    including Plotly JSON payloads for interactive 2D and 3D rendering.
    """
    charts = []
    plot_df = visualization_sample(df)

    valid_types = ["measure", "currency", "percentage"]
    date_cols = [c for c, t in semantic_types.items() if t == "datetime" and c in plot_df.columns]
    measure_cols = [c for c, t in semantic_types.items() if t in valid_types and c in plot_df.columns]
    cat_cols = [c for c, t in semantic_types.items() if t in ["categorical", "text"] and c in plot_df.columns]

    for col in measure_cols:
        plot_df[col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[col])), errors="coerce")

    # 1. Multi-Variable Interaction (2D Color-Mapped Scatter / 3D Spatial Plotly)
    if len(measure_cols) >= 3:
        x_m, y_m, z_m = measure_cols[0], measure_cols[1], measure_cols[2]
        sub_3d = plot_df[[x_m, y_m, z_m]].dropna()
        if len(sub_3d) > 5:
            plotly_3d = build_plotly_payload(
                "scatter3d", f"3D Spatial Interaction: {x_m} vs {y_m} vs {z_m}",
                sub_3d[x_m].tolist(), sub_3d[y_m].tolist(), sub_3d[z_m].tolist(),
                x_label=x_m, y_label=y_m, z_label=z_m
            )
            
            # Clean 2D Representation: Bivariate scatter with color-coded 3rd variable
            fig_2d, ax_2d = plt.subplots(figsize=(8, 4.5))
            scatter_2d = ax_2d.scatter(
                sub_3d[x_m], sub_3d[y_m], c=sub_3d[z_m],
                cmap='viridis', s=45, alpha=0.75, edgecolors='none'
            )
            ax_2d.set_title(f'Multi-Variable Interaction: {y_m} vs {x_m} (Color: {z_m})', fontsize=11, fontweight='bold')
            ax_2d.set_xlabel(x_m, fontsize=9)
            ax_2d.set_ylabel(y_m, fontsize=9)
            ax_2d.grid(True, linestyle='--', alpha=0.4)
            cbar_2d = fig_2d.colorbar(scatter_2d, ax=ax_2d)
            cbar_2d.set_label(z_m, fontsize=8)
            plot_2d_base64 = fig_to_base64(fig_2d)

            # 3D Matplotlib Fallback
            fig_3d = plt.figure(figsize=(8, 4.8))
            try:
                ax_3d = fig_3d.add_subplot(111, projection='3d')
                p3 = ax_3d.scatter(sub_3d[x_m], sub_3d[y_m], sub_3d[z_m], c=sub_3d[z_m], cmap='viridis', s=25, alpha=0.8)
                ax_3d.set_title(f'3D Multi-Variable Space: {x_m} vs {y_m} vs {z_m}', fontsize=11, fontweight='bold')
                ax_3d.set_xlabel(x_m, fontsize=8, labelpad=6)
                ax_3d.set_ylabel(y_m, fontsize=8, labelpad=6)
                ax_3d.set_zlabel(z_m, fontsize=8, labelpad=6)
                fig_3d.colorbar(p3, ax=ax_3d, shrink=0.55, pad=0.1, label=z_m)
            except Exception:
                pass
            plot_3d_base64 = fig_to_base64(fig_3d)

            charts.append({
                'title': f'Multi-Variable Interaction: {y_m} vs {x_m}',
                'title_2d': f'Multi-Variable Scatter: {y_m} vs {x_m} (Color: {z_m})',
                'title_3d': f'3D Spatial Projection: {x_m} vs {y_m} vs {z_m}',
                'description': f'Evaluates interaction between "{x_m}" and "{y_m}" with gradient coloring by "{z_m}".',
                'description_2d': f'2D bivariate scatter plot mapping "{z_m}" color gradient across "{x_m}" and "{y_m}".',
                'description_3d': f'Interactive 3D scatter plot showcasing multi-variable interactions with 360° rotation and hover depth.',
                'plot': plot_2d_base64,
                'plot_2d': plot_2d_base64,
                'plot_3d': plot_3d_base64,
                'plotly_json': plotly_3d,
                'chart_type': 'scatter3d',
                'is_3d': True
            })

    # 2. Correlation Matrix Heatmap Chart
    corr_plot = generate_correlation_heatmap(plot_df, semantic_types)
    if corr_plot:
        valid_types = ["measure", "currency", "percentage"]
        m_cols = [c for c, t in semantic_types.items() if t in valid_types and c in plot_df.columns]
        num_df = plot_df[m_cols].copy().dropna()
        if not num_df.empty and len(num_df.columns) >= 2:
            full_corr = num_df.corr()
            if len(full_corr.columns) > 10:
                corr_scores = (full_corr.abs() - np.eye(len(full_corr))).max(axis=0)
                top_cols = corr_scores.sort_values(ascending=False).head(10).index.tolist()
                corr_matrix = full_corr.loc[top_cols, top_cols]
                title = f'Key Correlations Heatmap (Top {len(top_cols)} Metrics)'
                desc = f'Focuses on top {len(top_cols)} high-impact metrics with strongest relationships (filtered from {len(m_cols)} metrics for maximum clarity).'
            else:
                corr_matrix = full_corr
                title = 'Correlation Matrix Heatmap'
                desc = 'Evaluates pairwise linear relationships across numerical measure columns.'

            plotly_corr = build_plotly_payload(
                "heatmap", title,
                x_data=corr_matrix.columns.tolist(),
                y_data=corr_matrix.index.tolist(),
                z_data=corr_matrix.values.round(2).tolist()
            )
            charts.append({
                'title': title,
                'description': desc,
                'plot': corr_plot,
                'plotly_json': plotly_corr,
                'chart_type': 'heatmap',
                'is_3d': False
            })

    # 3. Datetime + Measure (Line Chart)
    if date_cols and measure_cols:
        time_col = date_cols[0]
        y_col = next((c for c in measure_cols if c.lower() in ['sales', 'revenue', 'profit', 'quantity', 'amount']), measure_cols[0])

        temp = plot_df[[time_col, y_col]].copy()
        temp[time_col] = pd.to_datetime(temp[time_col], errors="coerce", format="mixed")
        temp[y_col] = pd.to_numeric(convert_currency(temp[y_col]), errors="coerce")
        temp.dropna(inplace=True)

        if not temp.empty:
            temp.set_index(time_col, inplace=True)
            resampled = temp[y_col].resample('ME').sum() if len(temp) > 30 else temp[y_col].resample('D').sum()
            resampled_df = resampled.reset_index()

            fig, ax = plt.subplots(figsize=(8, 4))
            resampled.plot(ax=ax, marker='o', markersize=4, linestyle='-', color=PRIMARY_COLOR, linewidth=2)
            ax.set_title(f'Time-Series Trend: {y_col} over {time_col}', fontsize=12, fontweight='bold')
            ax.set_xlabel(time_col)
            ax.set_ylabel(y_col)
            ax.grid(True, linestyle='--', alpha=0.5)

            plotly_line = build_plotly_payload(
                "line", f"Trend Analysis: {y_col} vs {time_col}",
                resampled_df[time_col].dt.strftime('%Y-%m-%d').tolist(),
                resampled_df[y_col].tolist(),
                x_label=time_col, y_label=y_col
            )

            charts.append({
                'title': f'Trend Analysis: {y_col} vs. {time_col}',
                'description': f'Shows temporal progression and seasonality for "{y_col}".',
                'plot': fig_to_base64(fig),
                'plotly_json': plotly_line,
                'chart_type': 'line',
                'is_3d': False
            })

    # 4. Categorical + Measure (Bar Chart)
    good_cat_cols = [c for c in cat_cols if 1 < plot_df[c].nunique() <= 30]
    if good_cat_cols and measure_cols:
        cat_col = good_cat_cols[0]
        num_col = next((c for c in measure_cols if c.lower() in ['sales', 'profit', 'revenue', 'quantity']), measure_cols[0])

        is_financial = any(k in num_col.lower() for k in ['sales', 'profit', 'revenue', 'amount', 'qty', 'quantity'])
        agg_type = "sum" if is_financial else "mean"

        temp_df = plot_df[[cat_col, num_col]].copy()
        temp_df[num_col] = pd.to_numeric(convert_currency(temp_df[num_col]), errors="coerce")
        temp_df.dropna(subset=[num_col], inplace=True)

        if not temp_df.empty:
            grouped = temp_df.groupby(cat_col)[num_col].agg(agg_type).sort_values(ascending=False).head(10)

            fig, ax = plt.subplots(figsize=(8, 4))
            grouped.plot(kind='bar', ax=ax, color=VIOLET_COLOR, edgecolor='none', width=0.7)
            ax.set_title(f'{agg_type.capitalize()} of {num_col} by {cat_col}', fontsize=12, fontweight='bold')
            ax.set_xlabel(cat_col)
            ax.set_ylabel(f'{agg_type.capitalize()} {num_col}')
            ax.tick_params(axis='x', rotation=45)
            ax.grid(axis='y', linestyle='--', alpha=0.5)

            plotly_bar = build_plotly_payload(
                "bar", f"Category Comparison: {num_col} by {cat_col}",
                grouped.index.astype(str).tolist(),
                grouped.values.tolist(),
                x_label=cat_col, y_label=f"{agg_type.capitalize()} {num_col}"
            )

            charts.append({
                'title': f'Category Comparison: {num_col} by {cat_col}',
                'description': f'Compares {agg_type} of "{num_col}" across top categories in "{cat_col}".',
                'plot': fig_to_base64(fig),
                'plotly_json': plotly_bar,
                'chart_type': 'bar',
                'is_3d': False
            })

    # 5. Single Measure Distribution (Histogram + KDE + Boxplot)
    if measure_cols:
        num_col = measure_cols[0]
        series = pd.to_numeric(plot_df[num_col], errors="coerce").dropna()
        if not series.empty:
            fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))
            sns.histplot(series, ax=axes[0], kde=True, color=PRIMARY_COLOR)
            axes[0].set_title('Frequency & KDE Density', fontsize=10, fontweight='bold')
            sns.boxplot(x=series, ax=axes[1], color=CYAN_COLOR)
            axes[1].set_title('Outlier & Spread Boxplot', fontsize=10, fontweight='bold')

            plotly_hist = build_plotly_payload(
                "histogram", f"Distribution & Outliers: {num_col}",
                series.tolist(),
                x_label=num_col
            )

            charts.append({
                'title': f'Distribution & Outliers: {num_col}',
                'description': f'Evaluates frequency spread, skewness, and numerical outliers for "{num_col}".',
                'plot': fig_to_base64(fig),
                'plotly_json': plotly_hist,
                'chart_type': 'distribution',
                'is_3d': False
            })

    # 6. Categorical Composition (Pie / Donut Chart)
    if good_cat_cols:
        cat_col = good_cat_cols[0]
        cat_counts = plot_df[cat_col].value_counts()
        if len(cat_counts) > 5:
            top_cats = cat_counts.head(5).copy()
            top_cats['Other'] = cat_counts.iloc[5:].sum()
        else:
            top_cats = cat_counts

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.pie(top_cats.values, labels=top_cats.index, autopct='%1.1f%%',
               colors=[PRIMARY_COLOR, VIOLET_COLOR, CYAN_COLOR, GREEN_COLOR, '#F59E0B', '#94A3B8'], startangle=140)
        ax.set_title(f'Composition Share: {cat_col}', fontsize=12, fontweight='bold')

        plotly_pie = build_plotly_payload(
            "pie", f"Composition Share: {cat_col}",
            top_cats.index.astype(str).tolist(),
            top_cats.values.tolist()
        )

        charts.append({
            'title': f'Composition Share: {cat_col}',
            'description': f'Percentage distribution of categories in "{cat_col}".',
            'plot': fig_to_base64(fig),
            'plotly_json': plotly_pie,
            'chart_type': 'pie',
            'is_3d': False
        })

    # 7. Measure vs Measure (Scatter Plot)
    if len(measure_cols) >= 2:
        x_col = measure_cols[0]
        y_col = measure_cols[1]
        scatter_df = plot_df[[x_col, y_col]].dropna()
        if not scatter_df.empty and len(scatter_df) > 5:
            fig, ax = plt.subplots(figsize=(8, 4))
            sns.regplot(data=scatter_df, x=x_col, y=y_col, ax=ax,
                        scatter_kws={'alpha': 0.5, 'color': PRIMARY_COLOR},
                        line_kws={'color': 'red', 'linewidth': 2})
            ax.set_title(f'Scatter & Regression: {y_col} vs. {x_col}', fontsize=12, fontweight='bold')
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.grid(True, linestyle='--', alpha=0.5)

            plotly_scatter = build_plotly_payload(
                "scatter", f"Scatter & Trend: {y_col} vs {x_col}",
                scatter_df[x_col].tolist(),
                scatter_df[y_col].tolist(),
                x_label=x_col, y_label=y_col
            )

            charts.append({
                'title': f'Scatter & Trend: {y_col} vs {x_col}',
                'description': f'Analyzes bivariate relationship and regression fit between "{x_col}" and "{y_col}".',
                'plot': fig_to_base64(fig),
                'plotly_json': plotly_scatter,
                'chart_type': 'scatter',
                'is_3d': False
            })

    return charts[:max_charts]


def get_chart_options_with_recommendations(x_type, y_type=None):
    """
    Returns chart options formatted with '(Recommended)' prefixes/suffixes for interactive UI chart builder.
    """
    base_options = [
        {"value": "bar", "label": "Bar Chart"},
        {"value": "line", "label": "Line Chart"},
        {"value": "scatter", "label": "Scatter Plot"},
        {"value": "scatter3d", "label": "3D Scatter Plot"},
        {"value": "histogram", "label": "Histogram"},
        {"value": "boxplot", "label": "Box Plot"},
        {"value": "pie", "label": "Pie Chart"},
        {"value": "violin", "label": "Violin Plot"}
    ]

    recs = recommend_chart(x_type, y_type)

    formatted_options = []
    for opt in base_options:
        is_rec = opt["value"] in recs
        label = f"(Recommended) {opt['label']}" if is_rec else opt['label']
        formatted_options.append({
            "value": opt["value"],
            "label": label,
            "recommended": is_rec
        })

    formatted_options.sort(key=lambda x: x["recommended"], reverse=True)
    return formatted_options


def generate_custom_chart(df, x_col, y_col=None, chart_type="bar", agg_func="sum", z_col=None):
    """
    Generates a user-requested custom chart using cleaned dataframe, returning base64 plot and Plotly JSON structure.
    """
    if df is None or df.empty:
        raise ValueError("Dataset is empty or invalid.")

    if x_col not in df.columns:
        raise ValueError(f"Column '{x_col}' does not exist in dataset.")

    # Normalize optional columns if empty or invalid
    if y_col and (y_col not in df.columns or (isinstance(y_col, str) and y_col.lower() in ('none', 'null', 'select', 'optional', ''))):
        y_col = None
    if z_col and (z_col not in df.columns or (isinstance(z_col, str) and z_col.lower() in ('none', 'null', 'select', 'optional', ''))):
        z_col = None

    valid_aggs = ['sum', 'mean', 'count', 'min', 'max', 'median', 'std']
    if not agg_func or str(agg_func).lower() not in valid_aggs:
        agg_func = "sum"
    else:
        agg_func = str(agg_func).lower()

    plot_df = visualization_sample(df)

    if y_col and y_col in plot_df.columns:
        plot_df[y_col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[y_col])), errors="coerce")

    if z_col and z_col in plot_df.columns:
        plot_df[z_col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[z_col])), errors="coerce")

    plotly_payload = None

    if chart_type == "scatter3d":
        fig = plt.figure(figsize=(9, 5.5))
        ax = fig.add_subplot(111, projection='3d')

        if not y_col or not z_col:
            num_cols = [c for c in plot_df.columns if pd.api.types.is_numeric_dtype(plot_df[c]) and c not in [x_col, y_col]]
            if num_cols and not z_col:
                z_col = num_cols[0]
            elif not y_col and len(num_cols) >= 2:
                y_col, z_col = num_cols[0], num_cols[1]
            elif len(num_cols) >= 1 and not y_col:
                y_col = num_cols[0]
                if len(num_cols) >= 2:
                    z_col = num_cols[1]
                else:
                    z_col = x_col
            else:
                z_col = y_col or x_col

        sub_3d = plot_df[[x_col, y_col, z_col]].dropna()
        if sub_3d.empty:
            raise ValueError("No valid data points for 3D scatter plot.")

        p = ax.scatter(sub_3d[x_col], sub_3d[y_col], sub_3d[z_col], c=sub_3d[z_col], cmap='plasma', alpha=0.85, s=35)
        ax.set_xlabel(str(x_col), labelpad=8)
        ax.set_ylabel(str(y_col), labelpad=8)
        ax.set_zlabel(str(z_col), labelpad=8)
        ax.set_title(f'3D Scatter Projection: {x_col} vs {y_col} vs {z_col}', fontsize=12, fontweight='bold', pad=12)

        plotly_payload = build_plotly_payload(
            "scatter3d", f"3D Custom Scatter Plot: {x_col} vs {y_col} vs {z_col}",
            sub_3d[x_col].tolist(), sub_3d[y_col].tolist(), sub_3d[z_col].tolist(),
            x_label=x_col, y_label=y_col, z_label=z_col
        )
    else:
        fig, ax = plt.subplots(figsize=(8, 4.5))

        if chart_type == "bar":
            if y_col and y_col in plot_df.columns:
                sub = plot_df[[x_col, y_col]].dropna(subset=[x_col, y_col])
                if not sub.empty:
                    grouped = sub.groupby(x_col)[y_col].agg(agg_func).reset_index().sort_values(by=y_col, ascending=False).head(20)
                    sns.barplot(data=grouped, x=x_col, y=y_col, ax=ax, palette="Blues_d", hue=x_col, legend=False)
                    ax.set_title(f'Custom Bar Chart: {agg_func.capitalize()} of {y_col} by {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("bar", f"{agg_func.capitalize()} of {y_col} by {x_col}", grouped[x_col].astype(str).tolist(), grouped[y_col].tolist(), x_label=x_col, y_label=y_col)
                else:
                    top_cats = plot_df[x_col].dropna().value_counts().head(15).reset_index()
                    top_cats.columns = [x_col, 'count']
                    if top_cats.empty:
                        raise ValueError(f"No valid data available to render bar chart for column '{x_col}'.")
                    sns.barplot(data=top_cats, x=x_col, y='count', ax=ax, palette="Blues_d", hue=x_col, legend=False)
                    ax.set_title(f'Custom Bar Chart: Frequency of {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("bar", f"Frequency of {x_col}", top_cats[x_col].astype(str).tolist(), top_cats['count'].tolist(), x_label=x_col, y_label="Count")
            else:
                top_cats = plot_df[x_col].dropna().value_counts().head(15).reset_index()
                top_cats.columns = [x_col, 'count']
                if top_cats.empty:
                    raise ValueError(f"No valid data available to render bar chart for column '{x_col}'.")
                sns.barplot(data=top_cats, x=x_col, y='count', ax=ax, palette="Blues_d", hue=x_col, legend=False)
                ax.set_title(f'Custom Bar Chart: Frequency of {x_col}', fontsize=12, fontweight='bold')
                plotly_payload = build_plotly_payload("bar", f"Frequency of {x_col}", top_cats[x_col].astype(str).tolist(), top_cats['count'].tolist(), x_label=x_col, y_label="Count")
            ax.tick_params(axis='x', rotation=35)
            plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

        elif chart_type == "line":
            if y_col and y_col in plot_df.columns:
                sub = plot_df[[x_col, y_col]].dropna(subset=[x_col, y_col])
                if not sub.empty:
                    grouped = sub.groupby(x_col)[y_col].agg(agg_func).reset_index().sort_values(by=x_col).head(50)
                    sns.lineplot(data=grouped, x=x_col, y=y_col, ax=ax, color=PRIMARY_COLOR, marker='o')
                    ax.set_title(f'Custom Line Chart: {y_col} vs {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("line", f"{y_col} vs {x_col}", grouped[x_col].astype(str).tolist(), grouped[y_col].tolist(), x_label=x_col, y_label=y_col)
                else:
                    val_counts = plot_df[x_col].dropna().value_counts().sort_index().reset_index()
                    val_counts.columns = [x_col, 'count']
                    if val_counts.empty:
                        raise ValueError(f"No valid data available to render line chart for column '{x_col}'.")
                    sns.lineplot(data=val_counts, x=x_col, y='count', ax=ax, color=PRIMARY_COLOR, marker='o')
                    ax.set_title(f'Custom Line Chart: Trend of {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("line", f"Trend of {x_col}", val_counts[x_col].astype(str).tolist(), val_counts['count'].tolist(), x_label=x_col, y_label="Count")
            else:
                val_counts = plot_df[x_col].dropna().value_counts().sort_index().reset_index()
                val_counts.columns = [x_col, 'count']
                if val_counts.empty:
                    raise ValueError(f"No valid data available to render line chart for column '{x_col}'.")
                sns.lineplot(data=val_counts, x=x_col, y='count', ax=ax, color=PRIMARY_COLOR, marker='o')
                ax.set_title(f'Custom Line Chart: Trend of {x_col}', fontsize=12, fontweight='bold')
                plotly_payload = build_plotly_payload("line", f"Trend of {x_col}", val_counts[x_col].astype(str).tolist(), val_counts['count'].tolist(), x_label=x_col, y_label="Count")
            ax.tick_params(axis='x', rotation=35)
            plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

        elif chart_type == "scatter":
            if not y_col or y_col not in plot_df.columns:
                raise ValueError("Scatter plot requires both X-Axis and Y-Axis columns.")
            scatter_data = plot_df[[x_col, y_col]].dropna()
            if scatter_data.empty:
                raise ValueError("No valid data points after removing missing values.")
            sns.scatterplot(data=scatter_data, x=x_col, y=y_col, ax=ax, color=VIOLET_COLOR, alpha=0.7)
            ax.set_title(f'Custom Scatter Plot: {y_col} vs {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("scatter", f"{y_col} vs {x_col}", scatter_data[x_col].tolist(), scatter_data[y_col].tolist(), x_label=x_col, y_label=y_col)

        elif chart_type == "histogram":
            num_x = pd.to_numeric(convert_percentage(convert_currency(plot_df[x_col])), errors="coerce").dropna()
            if num_x.empty:
                raise ValueError(f"Column '{x_col}' contains no numeric data for histogram.")
            sns.histplot(num_x, kde=True, ax=ax, color=CYAN_COLOR)
            ax.set_title(f'Custom Distribution Histogram: {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("histogram", f"Distribution of {x_col}", num_x.tolist(), x_label=x_col)

        elif chart_type == "boxplot":
            if y_col and y_col in plot_df.columns:
                if pd.api.types.is_numeric_dtype(plot_df[y_col]):
                    top_cats = plot_df[x_col].value_counts().head(10).index
                    sub_box = plot_df[plot_df[x_col].isin(top_cats)].dropna(subset=[x_col, y_col])
                    if sub_box.empty:
                        raise ValueError("No valid data for box plot.")
                    sns.boxplot(data=sub_box, x=x_col, y=y_col, ax=ax, palette="Blues_d", hue=x_col, legend=False)
                    ax.set_title(f'Custom Box Plot: {y_col} by {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("boxplot", f"Box Plot: {y_col} by {x_col}", sub_box[y_col].tolist(), categories=sub_box[x_col].astype(str).tolist(), x_label=x_col, y_label=y_col)
                elif pd.api.types.is_numeric_dtype(plot_df[x_col]):
                    top_cats = plot_df[y_col].value_counts().head(10).index
                    sub_box = plot_df[plot_df[y_col].isin(top_cats)].dropna(subset=[x_col, y_col])
                    if sub_box.empty:
                        raise ValueError("No valid data for box plot.")
                    sns.boxplot(data=sub_box, x=y_col, y=x_col, ax=ax, palette="Blues_d", hue=y_col, legend=False)
                    ax.set_title(f'Custom Box Plot: {x_col} by {y_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("boxplot", f"Box Plot: {x_col} by {y_col}", sub_box[x_col].tolist(), categories=sub_box[y_col].astype(str).tolist(), x_label=y_col, y_label=x_col)
                else:
                    raise ValueError("At least one column must be numeric for a 2-variable Box Plot.")
            else:
                num_x = pd.to_numeric(convert_percentage(convert_currency(plot_df[x_col])), errors="coerce").dropna()
                if num_x.empty:
                    raise ValueError(f"Column '{x_col}' contains no numeric data for Box Plot.")
                sns.boxplot(y=num_x, ax=ax, color=PRIMARY_COLOR)
                ax.set_title(f'Custom Box Plot: {x_col}', fontsize=12, fontweight='bold')
                plotly_payload = build_plotly_payload("boxplot", f"Box Plot: {x_col}", num_x.tolist(), x_label=x_col, y_label=x_col)
            ax.tick_params(axis='x', rotation=35)
            plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

        elif chart_type == "violin":
            if y_col and y_col in plot_df.columns:
                if pd.api.types.is_numeric_dtype(plot_df[y_col]):
                    top_cats = plot_df[x_col].value_counts().head(10).index
                    sub_v = plot_df[plot_df[x_col].isin(top_cats)].dropna(subset=[x_col, y_col])
                    if sub_v.empty:
                        raise ValueError("No valid data for violin plot.")
                    sns.violinplot(data=sub_v, x=x_col, y=y_col, ax=ax, palette="Blues_d", hue=x_col, legend=False, inner="quartile")
                    ax.set_title(f'Custom Violin Plot: {y_col} by {x_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("violin", f"Violin Plot: {y_col} by {x_col}", sub_v[y_col].tolist(), categories=sub_v[x_col].astype(str).tolist(), x_label=x_col, y_label=y_col)
                elif pd.api.types.is_numeric_dtype(plot_df[x_col]):
                    top_cats = plot_df[y_col].value_counts().head(10).index
                    sub_v = plot_df[plot_df[y_col].isin(top_cats)].dropna(subset=[x_col, y_col])
                    if sub_v.empty:
                        raise ValueError("No valid data for violin plot.")
                    sns.violinplot(data=sub_v, x=y_col, y=x_col, ax=ax, palette="Blues_d", hue=y_col, legend=False, inner="quartile")
                    ax.set_title(f'Custom Violin Plot: {x_col} by {y_col}', fontsize=12, fontweight='bold')
                    plotly_payload = build_plotly_payload("violin", f"Violin Plot: {x_col} by {y_col}", sub_v[x_col].tolist(), categories=sub_v[y_col].astype(str).tolist(), x_label=y_col, y_label=x_col)
                else:
                    raise ValueError("At least one column must be numeric for a 2-variable Violin Plot.")
            else:
                num_x = pd.to_numeric(convert_percentage(convert_currency(plot_df[x_col])), errors="coerce").dropna()
                if num_x.empty:
                    raise ValueError(f"Column '{x_col}' contains no numeric data for Violin Plot.")
                sns.violinplot(y=num_x, ax=ax, color=CYAN_COLOR, inner="quartile")
                ax.set_title(f'Custom Violin Plot: {x_col}', fontsize=12, fontweight='bold')
                plotly_payload = build_plotly_payload("violin", f"Violin Plot: {x_col}", num_x.tolist(), x_label=x_col, y_label=x_col)
            ax.tick_params(axis='x', rotation=35)
            plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")

        elif chart_type == "pie":
            top_cats = plot_df[x_col].dropna().value_counts().head(6)
            if top_cats.empty:
                raise ValueError(f"Column '{x_col}' has no categories for pie chart.")
            ax.pie(top_cats.values, labels=top_cats.index, autopct='%1.1f%%', colors=sns.color_palette("pastel"))
            ax.set_title(f'Custom Pie Chart: Share of {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("pie", f"Share of {x_col}", top_cats.index.astype(str).tolist(), top_cats.values.tolist())

        else:
            raise ValueError(f"Unsupported chart type '{chart_type}'.")

        ax.grid(True, linestyle='--', alpha=0.5)

    return {
        "plot": fig_to_base64(fig),
        "plotly_json": plotly_payload,
        "chart_type": chart_type,
        "is_3d": chart_type == "scatter3d"
    }