try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
except ImportError:
    matplotlib = None
    plt = None
    sns = None
import base64
from io import BytesIO
import pandas as pd
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
    Optimized for high rendering speed and low latency.
    """
    if fig is None or plt is None:
        return None
    buf = BytesIO()
    try:
        fig.tight_layout()
    except Exception as e:
        logger.warning(f"tight_layout failed: {e}")
    fig.savefig(buf, format="png", bbox_inches='tight', transparent=True, dpi=95)
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
    Generates a missing value pattern heatmap visualization.
    """
    if plt is None or sns is None:
        return None
    if df.isna().sum().sum() == 0:
        return None

    fig, ax = plt.subplots(figsize=(8, 3))
    sns.heatmap(df.isna(), cbar=False, cmap='viridis', ax=ax, yticklabels=False)
    ax.set_title('Missing Values Pattern Matrix (Yellow = Missing)', fontsize=11, fontweight='bold')
    return fig_to_base64(fig)


def generate_correlation_heatmap(df, semantic_types):
    """
    Generates correlation heatmap visualization strictly for measure, currency, and percentage columns.
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

    corr = num_df.corr()
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, ax=ax, cbar=True)
    ax.set_title('Correlation Matrix Heatmap', fontsize=12, fontweight='bold')
    return fig_to_base64(fig)


def generate_automatic_charts(df, semantic_types, max_charts=10):
    """
    Generates high-quality automatic charts tailored by semantic types and analytical intent.
    """
    charts = []
    plot_df = visualization_sample(df)

    valid_types = ["measure", "currency", "percentage"]
    date_cols = [c for c, t in semantic_types.items() if t == "datetime" and c in plot_df.columns]
    measure_cols = [c for c, t in semantic_types.items() if t in valid_types and c in plot_df.columns]
    cat_cols = [c for c, t in semantic_types.items() if t in ["categorical", "text"] and c in plot_df.columns]

    for col in measure_cols:
        plot_df[col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[col])), errors="coerce")

    # 1. Correlation Matrix Heatmap Chart
    corr_plot = generate_correlation_heatmap(plot_df, semantic_types)
    if corr_plot:
        charts.append({
            'title': 'Correlation Matrix Heatmap',
            'description': 'Evaluates pairwise linear relationships across numerical measure columns.',
            'plot': corr_plot,
            'chart_type': 'heatmap'
        })

    # 2. Datetime + Measure (Line Chart)
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

            fig, ax = plt.subplots(figsize=(8, 4))
            resampled.plot(ax=ax, marker='o', markersize=4, linestyle='-', color=PRIMARY_COLOR, linewidth=2)
            ax.set_title(f'Time-Series Trend: {y_col} over {time_col}', fontsize=12, fontweight='bold')
            ax.set_xlabel(time_col)
            ax.set_ylabel(y_col)
            ax.grid(True, linestyle='--', alpha=0.5)

            charts.append({
                'title': f'Trend Analysis: {y_col} vs. {time_col}',
                'description': f'Shows temporal progression and seasonality for "{y_col}".',
                'plot': fig_to_base64(fig),
                'chart_type': 'line'
            })

    # 3. Categorical + Measure (Bar Chart)
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

            charts.append({
                'title': f'Category Comparison: {num_col} by {cat_col}',
                'description': f'Compares {agg_type} of "{num_col}" across top categories in "{cat_col}".',
                'plot': fig_to_base64(fig),
                'chart_type': 'bar'
            })

    # 4. Single Measure Distribution (Histogram + KDE + Boxplot)
    if measure_cols:
        num_col = measure_cols[0]
        series = pd.to_numeric(plot_df[num_col], errors="coerce").dropna()
        if not series.empty:
            fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))
            sns.histplot(series, ax=axes[0], kde=True, color=PRIMARY_COLOR)
            axes[0].set_title('Frequency & KDE Density', fontsize=10, fontweight='bold')
            sns.boxplot(x=series, ax=axes[1], color=CYAN_COLOR)
            axes[1].set_title('Outlier & Spread Boxplot', fontsize=10, fontweight='bold')

            charts.append({
                'title': f'Distribution & Outliers: {num_col}',
                'description': f'Evaluates frequency spread, skewness, and numerical outliers for "{num_col}".',
                'plot': fig_to_base64(fig),
                'chart_type': 'distribution'
            })

    # 5. Categorical Composition (Pie / Donut Chart)
    if good_cat_cols:
        cat_col = good_cat_cols[0]
        top_cats = plot_df[cat_col].value_counts().head(5)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.pie(top_cats.values, labels=top_cats.index, autopct='%1.1f%%',
               colors=[PRIMARY_COLOR, VIOLET_COLOR, CYAN_COLOR, GREEN_COLOR, '#F59E0B'], startangle=140)
        ax.set_title(f'Category Share: {cat_col}', fontsize=12, fontweight='bold')
        charts.append({
            'title': f'Composition Share: {cat_col}',
            'description': f'Percentage distribution of top categories in "{cat_col}".',
            'plot': fig_to_base64(fig),
            'chart_type': 'pie'
        })

    # 6. Measure vs Measure (Scatter Plot with Regression Trendline)
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

            charts.append({
                'title': f'Scatter & Trend: {y_col} vs {x_col}',
                'description': f'Analyzes bivariate relationship and regression fit between "{x_col}" and "{y_col}".',
                'plot': fig_to_base64(fig),
                'chart_type': 'scatter'
            })

    # 7. Violin Plot (Categorical vs Measure)
    if good_cat_cols and measure_cols:
        cat_col = good_cat_cols[0]
        num_col = measure_cols[0]
        fig, ax = plt.subplots(figsize=(8, 4))
        top_cats = plot_df[cat_col].value_counts().head(5).index
        sub_plot = plot_df[plot_df[cat_col].isin(top_cats)]
        if not sub_plot.empty:
            sns.violinplot(data=sub_plot, x=cat_col, y=num_col, ax=ax, hue=cat_col, legend=False, palette="muted", inner="quartile")
            ax.set_title(f'Violin Density: {num_col} by {cat_col}', fontsize=12, fontweight='bold')
            ax.tick_params(axis='x', rotation=30)
            charts.append({
                'title': f'Violin Density: {num_col} by {cat_col}',
                'description': f'Displays probability density spread of "{num_col}" across top categories.',
                'plot': fig_to_base64(fig),
                'chart_type': 'violin'
            })

    # 8. Missingness Heatmap (if missing values exist)
    missing_map = generate_missingness_heatmap(plot_df)
    if missing_map:
        charts.append({
            'title': 'Missing Data Pattern Heatmap',
            'description': 'Visualizes pattern and distribution of missing cells across columns.',
            'plot': missing_map,
            'chart_type': 'missing_heatmap'
        })

    return charts[:max_charts]


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
                "size": 6,
                "color": z_data,
                "colorscale": "Viridis",
                "opacity": 0.85,
                "colorbar": {"title": z_label}
            },
            "hovertemplate": f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<br>{z_label}: %{{z}}<extra></extra>"
        })
        layout["scene"] = {
            "xaxis": {"title": x_label, "gridcolor": "#334155"},
            "yaxis": {"title": y_label, "gridcolor": "#334155"},
            "zaxis": {"title": z_label, "gridcolor": "#334155"},
            "bgcolor": "rgba(0,0,0,0)"
        }

    elif chart_type == "bar":
        plotly_data.append({
            "type": "bar",
            "x": x_data,
            "y": y_data,
            "marker": {
                "color": y_data if y_data and isinstance(y_data[0], (int, float)) else "#4F46E5",
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

    # 1. 3D Scatter Plot (if 3+ measure columns exist)
    if len(measure_cols) >= 3:
        x_m, y_m, z_m = measure_cols[0], measure_cols[1], measure_cols[2]
        sub_3d = plot_df[[x_m, y_m, z_m]].dropna()
        if len(sub_3d) > 5:
            plotly_3d = build_plotly_payload(
                "scatter3d", f"3D Spatial Feature Interaction: {x_m}, {y_m}, {z_m}",
                sub_3d[x_m].tolist(), sub_3d[y_m].tolist(), sub_3d[z_m].tolist(),
                x_label=x_m, y_label=y_m, z_label=z_m
            )
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.scatter(sub_3d[x_m], sub_3d[y_m], c=sub_3d[z_m], cmap='viridis', alpha=0.8)
            ax.set_title(f'3D Scatter Projection: {x_m} vs {y_m} vs {z_m}', fontsize=12, fontweight='bold')
            ax.set_xlabel(x_m)
            ax.set_ylabel(y_m)
            ax.grid(True, linestyle='--', alpha=0.5)

            charts.append({
                'title': f'3D Spatial Projection: {x_m} vs {y_m} vs {z_m}',
                'description': f'Interactive 3D scatter plot showcasing multi-variable interactions with hover depth.',
                'plot': fig_to_base64(fig),
                'plotly_json': plotly_3d,
                'chart_type': 'scatter3d',
                'is_3d': True
            })

    # 2. Correlation Matrix Heatmap Chart
    corr_plot = generate_correlation_heatmap(plot_df, semantic_types)
    if corr_plot:
        charts.append({
            'title': 'Correlation Matrix Heatmap',
            'description': 'Evaluates pairwise linear relationships across numerical measure columns.',
            'plot': corr_plot,
            'plotly_json': None,
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
        top_cats = plot_df[cat_col].value_counts().head(5)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.pie(top_cats.values, labels=top_cats.index, autopct='%1.1f%%',
               colors=[PRIMARY_COLOR, VIOLET_COLOR, CYAN_COLOR, GREEN_COLOR, '#F59E0B'], startangle=140)
        ax.set_title(f'Category Share: {cat_col}', fontsize=12, fontweight='bold')

        plotly_pie = build_plotly_payload(
            "pie", f"Composition Share: {cat_col}",
            top_cats.index.astype(str).tolist(),
            top_cats.values.tolist()
        )

        charts.append({
            'title': f'Composition Share: {cat_col}',
            'description': f'Percentage distribution of top categories in "{cat_col}".',
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
    if x_col not in df.columns:
        raise ValueError(f"Column '{x_col}' does not exist in dataset.")

    plot_df = visualization_sample(df)
    fig, ax = plt.subplots(figsize=(8, 4.5))

    if y_col and y_col in plot_df.columns:
        plot_df[y_col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[y_col])), errors="coerce")

    if z_col and z_col in plot_df.columns:
        plot_df[z_col] = pd.to_numeric(convert_percentage(convert_currency(plot_df[z_col])), errors="coerce")

    plotly_payload = None

    if chart_type == "scatter3d":
        if not y_col or not z_col:
            # Pick a default third numeric column if available
            num_cols = [c for c in plot_df.columns if pd.api.types.is_numeric_dtype(plot_df[c]) and c not in [x_col, y_col]]
            if num_cols and not z_col:
                z_col = num_cols[0]
            elif not y_col and len(num_cols) >= 2:
                y_col, z_col = num_cols[0], num_cols[1]
            else:
                raise ValueError("3D Scatter Plot requires 3 numerical columns (X, Y, Z).")

        sub_3d = plot_df[[x_col, y_col, z_col]].dropna()
        if sub_3d.empty:
            raise ValueError("No valid data points for 3D scatter plot.")

        plotly_payload = build_plotly_payload(
            "scatter3d", f"3D Custom Scatter Plot: {x_col} vs {y_col} vs {z_col}",
            sub_3d[x_col].tolist(), sub_3d[y_col].tolist(), sub_3d[z_col].tolist(),
            x_label=x_col, y_label=y_col, z_label=z_col
        )
        ax.scatter(sub_3d[x_col], sub_3d[y_col], c=sub_3d[z_col], cmap='plasma', alpha=0.8)
        ax.set_title(f'3D Scatter Projection: {x_col} vs {y_col} vs {z_col}', fontsize=12, fontweight='bold')

    elif chart_type == "bar":
        if y_col and y_col in plot_df.columns:
            grouped = plot_df.groupby(x_col)[y_col].agg(agg_func).reset_index().head(20)
            sns.barplot(data=grouped, x=x_col, y=y_col, ax=ax, palette="Blues_d", hue=x_col, legend=False)
            ax.set_title(f'Custom Bar Chart: {agg_func.capitalize()} of {y_col} by {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("bar", f"{agg_func.capitalize()} of {y_col} by {x_col}", grouped[x_col].astype(str).tolist(), grouped[y_col].tolist(), x_label=x_col, y_label=y_col)
        else:
            top_cats = plot_df[x_col].value_counts().head(15).reset_index()
            top_cats.columns = [x_col, 'count']
            sns.barplot(data=top_cats, x=x_col, y='count', ax=ax, palette="Blues_d", hue=x_col, legend=False)
            ax.set_title(f'Custom Bar Chart: Frequency of {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("bar", f"Frequency of {x_col}", top_cats[x_col].astype(str).tolist(), top_cats['count'].tolist(), x_label=x_col, y_label="Count")
        ax.tick_params(axis='x', rotation=35)

    elif chart_type == "line":
        if y_col and y_col in plot_df.columns:
            sns.lineplot(data=plot_df, x=x_col, y=y_col, ax=ax, color=PRIMARY_COLOR, marker='o')
            ax.set_title(f'Custom Line Chart: {y_col} vs {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("line", f"{y_col} vs {x_col}", plot_df[x_col].astype(str).tolist(), plot_df[y_col].tolist(), x_label=x_col, y_label=y_col)
        else:
            val_counts = plot_df[x_col].value_counts().sort_index().reset_index()
            val_counts.columns = [x_col, 'count']
            sns.lineplot(data=val_counts, x=x_col, y='count', ax=ax, color=PRIMARY_COLOR, marker='o')
            ax.set_title(f'Custom Line Chart: Trend of {x_col}', fontsize=12, fontweight='bold')
            plotly_payload = build_plotly_payload("line", f"Trend of {x_col}", val_counts[x_col].astype(str).tolist(), val_counts['count'].tolist(), x_label=x_col, y_label="Count")

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

    elif chart_type == "pie":
        top_cats = plot_df[x_col].value_counts().head(6)
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