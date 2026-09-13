"""
DataNova Automated Python Pipeline Code Service & Jupyter Notebook Generator
=============================================================================
Provides automated Python code generation mirroring DataNova's data cleaning,
semantic profiling, statistical EDA, ML modeling, and visual analytics pipeline.
Also builds Jupyter Notebook (.ipynb) files and provides an execution sandbox
to synchronize user code edits with live platform visualizations.
"""

from __future__ import annotations

import ast
import base64
import builtins
import contextlib
import io
import logging
import signal
import sys
import time
import traceback
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

MISSING_VALUE_TOKENS = ["?", "N/A", "NA", "null", "NULL", "None", "-", "--", " ", ""]

SECTION_TITLES = {
    "ingestion": "1. Data Ingestion & Data Health Audit",
    "types": "2. Semantic Data Type Conversions & Normalization",
    "cleaning": "3. Intelligent Data Cleaning & Missing Value Imputation",
    "outliers": "4. Outlier Detection & Anomaly Analysis (IQR 1.5x Method)",
    "eda": "5. Statistical Exploratory Data Analysis (EDA) & Correlation Intelligence",
    "ml": "6. Machine Learning Suite (K-Means Clustering & Segmentation)",
    "viz": "7. Data Visualizations & Analytics Charts Showcase",
    "export": "8. Export Cleaned & Processed Dataset",
}

# Modules that must never be importable from inside user-submitted code.
DISALLOWED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "http",
    "ftplib", "smtplib", "telnetlib", "ctypes", "winreg", "importlib",
    "pty", "pickle", "marshal", "multiprocessing", "threading", "code",
    "resource", "signal", "inspect", "gc",
}

# Dangerous callable names blocked via AST inspection
DISALLOWED_CALLS = {
    "eval", "exec", "compile", "open", "input", "breakpoint",
}

# Dangerous dunder attributes used in sandbox escape exploits
DANGEROUS_DUNDERS = {
    "__subclasses__", "__globals__", "__code__", "__closure__",
    "__mro__", "__bases__", "__builtins__",
}

MAX_CODE_LENGTH = 50_000  # characters
MAX_STDOUT_LENGTH = 200_000  # characters
EXECUTION_TIMEOUT_SECONDS = 25


class _ExecutionTimeout(Exception):
    """Raised internally when user code exceeds the wall-clock time budget."""


def _safe_import(name: str, globals_dict=None, locals_dict=None, fromlist=(), level: int = 0):
    """
    Safe __import__ implementation for the sandboxed execution environment.
    Prevents access to blocked system and network modules while allowing
    data analysis, scientific computing, visualization, and utility libraries.
    """
    root_mod = name.split(".")[0]
    if root_mod in DISALLOWED_MODULES:
        raise ImportError(f"Security restriction: import of '{name}' is not permitted in the sandbox.")
    return __import__(name, globals_dict, locals_dict, fromlist, level)


@contextlib.contextmanager
def _time_limit(seconds: int):
    """
    Cross-platform execution timeout using sys.settrace combined with SIGALRM
    fallback where available. Works reliably on Windows, macOS, and Linux.
    """
    deadline = time.time() + seconds
    timed_out = [False]

    def _trace_dispatch(frame, event, arg):
        if time.time() > deadline:
            timed_out[0] = True
            raise _ExecutionTimeout(f"Execution exceeded {seconds}s time limit.")
        return _trace_dispatch

    def _sig_handler(signum, frame):
        timed_out[0] = True
        raise _ExecutionTimeout(f"Execution exceeded {seconds}s time limit.")

    has_alarm = hasattr(signal, "SIGALRM")
    old_sig_handler = None
    if has_alarm:
        try:
            old_sig_handler = signal.signal(signal.SIGALRM, _sig_handler)
            signal.alarm(seconds)
        except (ValueError, OSError):
            has_alarm = False

    old_trace = sys.gettrace()
    sys.settrace(_trace_dispatch)
    try:
        yield
    finally:
        sys.settrace(old_trace)
        if has_alarm:
            try:
                signal.alarm(0)
                if old_sig_handler is not None:
                    signal.signal(signal.SIGALRM, old_sig_handler)
            except (ValueError, OSError):
                pass


def _safe_col_ref(col: str) -> str:
    """Return a syntactically safe Python literal for embedding a column
    name inside generated code (handles quotes, backslashes, unicode)."""
    return repr(col)


def _safe_col_list(cols: list[str]) -> str:
    return repr(list(cols))


# --------------------------------------------------------------------------
# Pipeline code generation
# --------------------------------------------------------------------------

def generate_pipeline_code(
    df: pd.DataFrame | None,
    semantic_types: dict[str, str] | None = None,
    dataset_name: str = "dataset.csv",
    dataset_id: int | str | None = None,
    cleaning_history: list | None = None,
) -> str:
    """
    Generates clean, well-commented, production-ready Python code that
    reproduces the complete data processing, cleaning, EDA, ML, and
    visualization pipeline.

    Args:
        df: The current DataFrame.
        semantic_types: Mapping of column name to semantic type
            (e.g. "datetime", "currency", "percentage", "measure").
        dataset_name: Original dataset filename.
        dataset_id: Dataset database ID, if any.
        cleaning_history: Optional list of recorded cleaning operations.

    Returns:
        A formatted Python source string.
    """
    if df is None:
        df = pd.DataFrame()
    if semantic_types is None:
        semantic_types = {}

    columns = list(df.columns)
    numeric_cols = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])] if not df.empty else []
    cat_cols = [c for c in columns if c not in numeric_cols] if not df.empty else []

    code_sections: list[str] = []

    # ---- Section: Header & Imports -------------------------------------
    code_sections.append(f'''# ==============================================================================
# DataNova Automated Analytics Pipeline & Reproducible Data Science Script
# Dataset: {_safe_col_ref(dataset_name)} (Dataset ID: {dataset_id if dataset_id is not None else "Active"})
# Generated by DataNova Smart Analytics Platform & Python Studio
# ==============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    px = None
    go = None
import warnings
warnings.filterwarnings("ignore")

# Set aesthetic styling
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams["figure.figsize"] = (10, 5.5)
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.titlesize"] = 14
plt.rcParams["axes.titleweight"] = "bold"
''')

    # ---- Section: Ingestion & Health Audit ------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["ingestion"]}
# ------------------------------------------------------------------------------
data_file = {_safe_col_ref(dataset_name)}

# Load dataset if not already loaded in memory/sandbox
try:
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        raise NameError
except (NameError, UnboundLocalError):
    try:
        if data_file.endswith((".xlsx", ".xls")):
            df = pd.read_excel(data_file)
        else:
            df = pd.read_csv(data_file, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(data_file, encoding="latin1")
    except (FileNotFoundError, Exception):
        df = pd.DataFrame()

n_rows, n_cols = df.shape
total_cells = max(1, n_rows * n_cols)
missing_cells = int(df.isnull().sum().sum()) if not df.empty else 0
duplicate_rows = int(df.duplicated().sum()) if not df.empty else 0

completeness = (1 - (missing_cells / total_cells)) * 100
uniqueness = (1 - (duplicate_rows / max(1, n_rows))) * 100
quality_score = round((completeness * 0.6) + (uniqueness * 0.4), 1)
quality_grade = (
    "A+" if quality_score >= 95 else
    "A" if quality_score >= 85 else
    "B" if quality_score >= 70 else
    "C"
)

print("=" * 65)
print(" [DATANOVA] DATA HEALTH & EXECUTIVE OVERVIEW")
print("=" * 65)
print(f" - Rows Count:       {{n_rows:,}}")
print(f" - Columns Count:    {{n_cols:,}}")
print(f" - Missing Values:   {{missing_cells:,}} ({{(missing_cells/total_cells)*100:.2f}}%)")
print(f" - Duplicate Rows:   {{duplicate_rows:,}} ({{(duplicate_rows/max(1, n_rows))*100:.2f}}%)")
print(f" - Quality Score:    {{quality_score}}% (Grade {{quality_grade}})")
print("=" * 65)
print("\\n--- First 5 Records ---")
try:
    display(df.head())
except NameError:
    print(df.head())
''')

    # ---- Section: Semantic Type Conversions -----------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["types"]}
# ------------------------------------------------------------------------------
# Normalize missing value tokens (treat "?", "N/A", "null", "nan", "-" as true NaN)
df = df.replace({MISSING_VALUE_TOKENS!r}, np.nan)
''')

    type_conversions = []
    for col, stype in semantic_types.items():
        if col not in columns:
            continue
        ref = _safe_col_ref(col)
        if stype == "datetime":
            type_conversions.append(
                f"if {ref} in df.columns:\n"
                f"    df[{ref}] = pd.to_datetime(df[{ref}], errors='coerce')"
            )
        elif stype in ("currency", "percentage", "measure"):
            type_conversions.append(
                f"if {ref} in df.columns:\n"
                f"    df[{ref}] = df[{ref}].astype(str).str.replace(r'[$€₹£,% ]', '', regex=True)\n"
                f"    df[{ref}] = pd.to_numeric(df[{ref}], errors='coerce')"
            )

    if type_conversions:
        code_sections.append("\n".join(type_conversions) + "\n")
    else:
        code_sections.append('''# Automatically parse likely date columns and numeric types
for col in df.columns:
    if "date" in col.lower() or "time" in col.lower():
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce")
        except (ValueError, TypeError):
            pass
''')

    # ---- Section: Cleaning & Imputation ---------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["cleaning"]}
# ------------------------------------------------------------------------------
# Impute numerical features using distribution-aware strategies
num_imputed = 0
for col in df.select_dtypes(include=[np.number]).columns:
    missing_count = df[col].isnull().sum()
    if missing_count == 0:
        continue
    non_null = df[col].dropna()
    if len(non_null) < 2 or non_null.nunique() <= 1:
        fill_value = non_null.median() if len(non_null) else 0
        df[col] = df[col].fillna(fill_value)
        print(f" [Imputation] '{{col}}' -> Filled with fallback value: {{fill_value}}")
        num_imputed += 1
        continue

    skewness = non_null.skew()
    if pd.notna(skewness) and abs(skewness) > 1.0:
        median_val = non_null.median()
        df[col] = df[col].fillna(median_val)
        print(f" [Imputation] '{{col}}' -> Filled with Median: {{median_val:.2f}} (Skewness: {{skewness:.2f}})")
    else:
        mean_val = non_null.mean()
        df[col] = df[col].fillna(mean_val)
        print(f" [Imputation] '{{col}}' -> Filled with Mean: {{mean_val:.2f}}")
    num_imputed += 1

# Impute categorical features with mode
cat_imputed = 0
for col in df.select_dtypes(include=["object", "category"]).columns:
    if df[col].isnull().sum() > 0:
        mode_series = df[col].mode()
        mode_val = mode_series.iloc[0] if not mode_series.empty else "Unknown"
        if isinstance(df[col].dtype, pd.CategoricalDtype) and mode_val not in df[col].cat.categories:
            df[col] = df[col].cat.add_categories([mode_val])
        df[col] = df[col].fillna(mode_val)
        print(f" [Imputation] '{{col}}' -> Filled with Mode: '{{mode_val}}'")
        cat_imputed += 1

if num_imputed == 0 and cat_imputed == 0:
    print(" [Imputation] 0 missing values detected. Dataset is fully populated.")

# Remove duplicate rows
initial_rows = len(df)
df = df.drop_duplicates()
print(f" [Duplicates] Removed {{initial_rows - len(df)}} duplicate records. Clean row count: {{len(df):,}}")
''')

    # ---- Section: Outlier Detection --------------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["outliers"]}
# ------------------------------------------------------------------------------
outlier_summary = {{}}
for col in df.select_dtypes(include=[np.number]).columns:
    q25 = df[col].quantile(0.25)
    q75 = df[col].quantile(0.75)
    iqr = q75 - q25
    if pd.isna(iqr) or iqr == 0:
        continue
    lower_bound = q25 - 1.5 * iqr
    upper_bound = q75 + 1.5 * iqr
    outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
    outlier_summary[col] = len(outliers)

if outlier_summary:
    print("Detected Outliers per Numeric Column:")
    for col, cnt in outlier_summary.items():
        pct = (cnt / len(df) * 100) if len(df) > 0 else 0
        flag = " [High Anomaly Rate]" if pct > 10 else ""
        print(f" - {{col:20s}}: {{cnt:5,d}} anomalies ({{pct:5.1f}}%){{flag}}")
else:
    print("No significant numerical outliers detected using IQR 1.5x method.")
''')

    # ---- Section: EDA & Correlation --------------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["eda"]}
# ------------------------------------------------------------------------------
print("\\n--- Descriptive Statistics (Numeric Features) ---")
numeric_df = df.select_dtypes(include=[np.number])
if not numeric_df.empty:
    try:
        display(numeric_df.describe().T)
    except NameError:
        print(numeric_df.describe().T)

if numeric_df.shape[1] >= 2 and len(numeric_df) >= 2:
    corr_matrix = numeric_df.corr()
    print("\\n--- Top Correlation Pairs ---")
    c_stack = corr_matrix.stack().reset_index()
    if not c_stack.empty and len(c_stack.columns) >= 3:
        c_stack.columns = ["var1", "var2", "correlation"]
        c_stack = c_stack[c_stack["var1"] != c_stack["var2"]]
        c_stack = c_stack.dropna(subset=["correlation"])
        if not c_stack.empty:
            c_stack["sorted_vars"] = c_stack.apply(
                lambda row: tuple(sorted((str(row["var1"]), str(row["var2"])))), axis=1
            )
            c_pairs = c_stack.drop_duplicates(subset="sorted_vars").drop(columns="sorted_vars")
            top_pos = c_pairs[c_pairs["correlation"] > 0].sort_values(by="correlation", ascending=False).head(3)
            top_neg = c_pairs[c_pairs["correlation"] < 0].sort_values(by="correlation", ascending=True).head(3)

            for _, r in top_pos.iterrows():
                print(f" - [Positive] {{r['var1']}} <-> {{r['var2']}}: +{{r['correlation']:.3f}}")
            for _, r in top_neg.iterrows():
                print(f" - [Negative] {{r['var1']}} <-> {{r['var2']}}: {{r['correlation']:.3f}}")
''')

    # ---- Section: Machine Learning ----------------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["ml"]}
# ------------------------------------------------------------------------------
num_cols = list(df.select_dtypes(include=[np.number]).columns)
if len(num_cols) >= 2 and len(df) >= 3:
    k_clusters = min(3, len(df))
    clustering_done = False

    # Engine A: Scikit-Learn KMeans
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        clean_features = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(clean_features)
        kmeans = KMeans(n_clusters=k_clusters, random_state=42, n_init="auto")
        df["Cluster_Segment"] = kmeans.fit_predict(scaled_data)
        clustering_done = True
        print(f"K-Means Clustering (Sklearn) completed with k={{k_clusters}}. Distribution:")
        print(df["Cluster_Segment"].value_counts())
    except (ImportError, Exception):
        # Engine B: Scipy Vector Quantization Fallback
        try:
            from scipy.cluster.vq import kmeans2, whiten
            features = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=float)
            whitened = whiten(features)
            _, labels = kmeans2(whitened, k=k_clusters, minit="points")
            df["Cluster_Segment"] = labels
            clustering_done = True
            print(f"K-Means Clustering (Scipy Engine) completed with k={{k_clusters}}. Distribution:")
            print(df["Cluster_Segment"].value_counts())
        except Exception as fallback_err:
            print(f"Clustering note: {{fallback_err}}")
else:
    print("Skipping ML Clustering: requires at least 2 numerical features and 3 records.")
''')

    # ---- Section: Visualizations --------------------------------------------
    chart_lines = [f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["viz"]}
# ------------------------------------------------------------------------------
num_chart_cols = list(df.select_dtypes(include=[np.number]).columns)
cat_chart_cols = [c for c in df.columns if c not in num_chart_cols]
''']

    if numeric_cols:
        p_col = numeric_cols[0]
        ref = _safe_col_ref(p_col)
        chart_lines.append(f'''# A. Distribution Profile & KDE
if {ref} in df.columns and pd.api.types.is_numeric_dtype(df[{ref}]):
    plt.figure(figsize=(9, 4.8))
    sns.histplot(df[{ref}].dropna(), kde=True, color="#2563eb", bins=min(25, max(5, len(df))))
    plt.title(f"Distribution Profile: {p_col}", fontsize=14, fontweight="bold")
    plt.xlabel({ref})
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.show()
''')

    if len(numeric_cols) >= 2:
        x_ref, y_ref = _safe_col_ref(numeric_cols[0]), _safe_col_ref(numeric_cols[1])
        chart_lines.append(f'''# B. Bivariate Correlation & Cluster Scatter
if {x_ref} in df.columns and {y_ref} in df.columns:
    plt.figure(figsize=(9, 4.8))
    has_cluster = "Cluster_Segment" in df.columns
    sns.scatterplot(
        data=df, x={x_ref}, y={y_ref},
        hue="Cluster_Segment" if has_cluster else None,
        palette="tab10" if has_cluster else None,
        alpha=0.85,
    )
    plt.title(f"Correlation Analysis: {numeric_cols[0]} vs {numeric_cols[1]}", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.show()

# C. Correlation Matrix Heatmap
num_df_corr = df.select_dtypes(include=[np.number])
if num_df_corr.shape[1] >= 2:
    plt.figure(figsize=(9.5, 6))
    sns.heatmap(num_df_corr.corr(), annot=True, cmap="Blues", fmt=".2f", linewidths=0.5, cbar=True)
    plt.title("Correlation Matrix Heatmap", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.show()
''')

    if cat_cols and numeric_cols:
        cat_ref, num_ref = _safe_col_ref(cat_cols[0]), _safe_col_ref(numeric_cols[0])
        chart_lines.append(f'''# D. Top Categories Breakdown
if {cat_ref} in df.columns and {num_ref} in df.columns:
    top_cats = df.groupby({cat_ref})[{num_ref}].mean().dropna().sort_values(ascending=False).head(8)
    if not top_cats.empty:
        plt.figure(figsize=(9.5, 4.8))
        top_cats.plot(kind="bar", color="#3b82f6", edgecolor="#1e40af")
        plt.title(f"Average {numeric_cols[0]} by Top {cat_cols[0]}", fontsize=14, fontweight="bold")
        plt.xlabel({cat_ref})
        plt.ylabel(f"Mean {numeric_cols[0]}")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.show()
''')

    if numeric_cols:
        box_cols_ref = _safe_col_list(numeric_cols[: min(4, len(numeric_cols))])
        chart_lines.append(f'''# E. Outlier & IQR Distribution Boxplot
valid_box_cols = [c for c in {box_cols_ref} if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
if valid_box_cols:
    plt.figure(figsize=(9.5, 4.8))
    sns.boxplot(data=df[valid_box_cols], color="#60a5fa")
    plt.title("Outlier & Dispersion Analysis (IQR Boxplot)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.show()
''')

    code_sections.append("\n".join(chart_lines))

    # ---- Section: Export -----------------------------------------------------
    code_sections.append(f'''# ------------------------------------------------------------------------------
# {SECTION_TITLES["export"]}
# ------------------------------------------------------------------------------
output_filename = "cleaned_data_export.csv"
try:
    df.to_csv(output_filename, index=False)
    print(f"Cleaned dataset successfully exported to '{{output_filename}}' (Final records: {{len(df):,}})")
except Exception as e_exp:
    print(f"Export note: {{e_exp}}")
''')

    return "\n".join(code_sections)


# --------------------------------------------------------------------------
# Jupyter notebook generation
# --------------------------------------------------------------------------

def generate_jupyter_notebook(
    df: pd.DataFrame | None,
    semantic_types: dict[str, str] | None = None,
    dataset_name: str = "dataset.csv",
    dataset_id: int | str | None = None,
    custom_code: str | None = None,
) -> dict[str, Any]:
    """
    Generates a valid Jupyter Notebook (.ipynb) dictionary compliant with the
    nbformat v4 JSON schema.
    """
    raw_code = custom_code if custom_code else generate_pipeline_code(
        df, semantic_types, dataset_name, dataset_id
    )

    cells: list[dict[str, Any]] = [{
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# 🚀 DataNova Automated Analytics Pipeline\n",
            f"**Dataset**: `{dataset_name}` (ID: `{dataset_id if dataset_id is not None else 'Active'}`)\n",
            "\n",
            "**Generated By**: DataNova Smart Analytics Platform\n",
            "\n",
            "This notebook contains a complete, self-contained, reproducible Python "
            "analytics workflow including data ingestion, data quality hygiene, "
            "exploratory data analysis (EDA), machine learning modeling, and "
            "visualizations.",
        ],
    }]

    section_prefixes = tuple(f"# {title}" for title in SECTION_TITLES.values())
    lines = raw_code.split("\n")
    current_chunk: list[str] = []

    def _flush_code_chunk():
        # Strip trailing and leading blank lines
        while current_chunk and not current_chunk[-1].strip():
            current_chunk.pop()
        while current_chunk and not current_chunk[0].strip():
            current_chunk.pop(0)

        if current_chunk:
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [l + "\n" for l in current_chunk],
            })
            current_chunk.clear()

    for line in lines:
        if line.startswith(
            "# ------------------------------------------------------------------------------"
        ) or line.startswith(
            "# =============================================================================="
        ):
            _flush_code_chunk()
            continue

        if line.startswith(section_prefixes):
            _flush_code_chunk()
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [f"### {line.replace('# ', '').strip()}\n"],
            })
            continue

        current_chunk.append(line)

    _flush_code_chunk()

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# --------------------------------------------------------------------------
# Syntax validation
# --------------------------------------------------------------------------

def validate_python_syntax(code_str: str) -> tuple[bool, str | None]:
    """Validates Python syntax before execution. Returns (is_valid, error_message)."""
    try:
        ast.parse(code_str)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax Error at line {e.lineno}: {e.msg}"


# --------------------------------------------------------------------------
# Sandboxed execution
# --------------------------------------------------------------------------

def _find_security_violation(code_str: str) -> str | None:
    """
    Static AST scan for unsafe modules, calls, and internal dunder escape paths.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return None  # Handled separately by validate_python_syntax

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in DISALLOWED_MODULES:
                    return f"Security restriction: import of '{alias.name}' is not permitted."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in DISALLOWED_MODULES:
                    return f"Security restriction: import from '{node.module}' is not permitted."
        elif isinstance(node, ast.Name) and node.id in DISALLOWED_CALLS:
            return f"Security restriction: use of '{node.id}' is not permitted."
        elif isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_DUNDERS:
                return f"Security restriction: access to '{node.attr}' is not permitted in the sandbox."

    return None


def execute_custom_python_code(
    code_str: str,
    df_original: pd.DataFrame | None,
    dataset_id: int | str | None = None,
    user_id: int | str | None = None,
) -> dict[str, Any]:
    """
    Executes user Python code against a DataFrame copy in a controlled sandbox.
    Captures stdout, generated matplotlib/seaborn plots (base64 PNG), the modified
    DataFrame, and execution status.

    Args:
        code_str: Python source to execute.
        df_original: Input DataFrame.
        dataset_id: Dataset ID (for logging/telemetry).
        user_id: User ID (for logging/telemetry).

    Returns:
        A dict with keys: success, error, stdout, plots, df_updated,
        resulting_df, preview_html, row_count, column_count.
    """
    base_result = {
        "success": False,
        "error": None,
        "stdout": "",
        "plots": [],
        "df_updated": False,
        "resulting_df": None,
        "preview_html": None,
        "row_count": len(df_original) if df_original is not None else 0,
        "column_count": len(df_original.columns) if df_original is not None else 0,
    }

    if not isinstance(code_str, str) or not code_str.strip():
        base_result["error"] = "No code provided."
        return base_result

    if len(code_str) > MAX_CODE_LENGTH:
        base_result["error"] = f"Code exceeds the maximum allowed length of {MAX_CODE_LENGTH} characters."
        return base_result

    # 1. Syntax check
    is_valid, syntax_err = validate_python_syntax(code_str)
    if not is_valid:
        base_result["error"] = syntax_err
        return base_result

    # 2. Static security scan
    violation = _find_security_violation(code_str)
    if violation:
        base_result["error"] = violation
        return base_result

    df_work = df_original.copy() if df_original is not None else pd.DataFrame()

    stdout_buffer = io.StringIO()
    plots_base64: list[str] = []

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.close("all")
    except ImportError:
        plt = None
        sns = None

    def _capped_print(*args, **kwargs):
        if stdout_buffer.tell() >= MAX_STDOUT_LENGTH:
            return
        print(*args, file=stdout_buffer, **kwargs)

    def custom_plt_show(*_args, **_kwargs):
        if plt is not None and plt.get_fignums():
            for fig_num in plt.get_fignums():
                fig = plt.figure(fig_num)
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
                buf.seek(0)
                img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                plots_base64.append(f"data:image/png;base64,{img_b64}")
                plt.close(fig)

    if plt:
        plt.show = custom_plt_show

    # Build complete builtins dictionary supporting full Python, OOP, and data science
    safe_builtins = builtins.__dict__.copy()
    safe_builtins["__import__"] = _safe_import

    def _blocked_open(*args, **kwargs):
        raise PermissionError("Direct open() is restricted in the sandbox. Use pandas read/write functions instead.")

    def _blocked_exit(*args, **kwargs):
        raise SystemExit("exit() is not permitted in the sandbox.")

    safe_builtins["open"] = _blocked_open
    safe_builtins["exit"] = _blocked_exit
    safe_builtins["quit"] = _blocked_exit

    sandbox_globals: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "pd": pd,
        "np": np,
        "df": df_work,
        "plt": plt,
        "sns": sns,
        "print": _capped_print,
        "display": lambda x: _capped_print(x),
    }

    exec_success = True
    error_msg: str | None = None

    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stdout_buffer):
        try:
            with _time_limit(EXECUTION_TIMEOUT_SECONDS):
                exec(compile(code_str, "<user_code>", "exec"), sandbox_globals)
                if plt and plt.get_fignums():
                    custom_plt_show()
        except _ExecutionTimeout as timeout_err:
            exec_success = False
            error_msg = str(timeout_err)
        except Exception as e:
            exec_success = False
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    captured_stdout = stdout_buffer.getvalue()
    if len(captured_stdout) > MAX_STDOUT_LENGTH:
        captured_stdout = captured_stdout[:MAX_STDOUT_LENGTH] + "\n... [output truncated]"

    resulting_df = sandbox_globals.get("df")
    df_updated = False
    preview_html = None
    row_count = 0
    col_count = 0

    if isinstance(resulting_df, pd.DataFrame):
        row_count = len(resulting_df)
        col_count = len(resulting_df.columns)
        if df_original is None or not resulting_df.equals(df_original):
            df_updated = True
        preview_html = resulting_df.head(10).to_html(
            classes=["dn-table", "dn-table-preview", "table-sm"],
            index=False,
            border=0,
            justify="left",
        )

    return {
        "success": exec_success,
        "error": error_msg,
        "stdout": captured_stdout,
        "plots": plots_base64,
        "df_updated": df_updated,
        "resulting_df": resulting_df if df_updated else None,
        "preview_html": preview_html,
        "row_count": row_count,
        "column_count": col_count,
    }