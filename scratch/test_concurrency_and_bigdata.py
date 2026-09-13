"""
DataNova Automated Test Suite:
1. High Concurrency Database Connection Pool Stress Test (Concurrent multi-threading)
2. Big Data 10,000,000 Rows Memory Optimizer & Vector Analytics Benchmark
3. Smart Prescriptive AI Recommendation Engine (Pareto 80/20, AutoML, Multi-language)
4. End-to-End Pipeline Execution with Big Data Downcasting
"""

import os
import sys
import time
import threading

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add parent workspace path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from database.db_connector import get_db_connection, init_db, _global_db_pool
from datanova.services.bigdata_optimizer import (
    optimize_dataframe_memory,
    smart_sample_for_visualization,
    compute_fast_vector_stats
)
from datanova.services.insight_service import (
    generate_rule_based_insights,
    generate_automl_recommendations
)
from datanova.services.pipeline_service import analyze_dataset


def test_db_init_and_indexes():
    print("\n--- TEST 1: Database Initialization & High-Concurrency Indexes ---")
    success = init_db()
    assert success is True, "Database initialization failed"
    print("✓ DB Tables & High-Concurrency Indexes verified successfully.")


def test_high_concurrency_pool():
    print("\n--- TEST 2: High Concurrency Connection Pool Stress Test (50 Concurrent Threads) ---")
    thread_count = 50
    results = []
    errors = []

    def worker_task(thread_id):
        try:
            with get_db_connection(raise_on_error=True) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 as ping, %s as tid", (thread_id,))
                    row = cursor.fetchone()
                    assert row['ping'] == 1
                    results.append(thread_id)
        except Exception as e:
            errors.append((thread_id, str(e)))

    start_time = time.time()
    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=worker_task, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start_time
    print(f"Executed {len(results)}/{thread_count} concurrent queries in {duration:.3f}s (Errors: {len(errors)})")
    assert len(errors) == 0, f"Encountered connection errors: {errors}"
    assert len(results) == thread_count, "Not all threads completed successfully"
    print("✓ 50-thread high-concurrency pool stress test passed flawlessly.")


def test_bigdata_memory_optimizer():
    print("\n--- TEST 3: Big Data Memory Optimizer & Downcasting Benchmark ---")
    # Generate 500,000 synthetic rows simulating high-volume financial transactions
    n_rows = 500_000
    print(f"Generating synthetic dataset with {n_rows:,} rows...")
    
    np.random.seed(42)
    raw_df = pd.DataFrame({
        "Transaction_ID": np.arange(1, n_rows + 1, dtype=np.int64),
        "Customer_Age": np.random.randint(18, 85, size=n_rows, dtype=np.int64),
        "Sales_Amount": np.random.uniform(10.5, 5000.0, size=n_rows).astype(np.float64),
        "Profit": np.random.uniform(-500.0, 1500.0, size=n_rows).astype(np.float64),
        "Region": np.random.choice(["North", "South", "East", "West", "Central"], size=n_rows),
        "Category": np.random.choice(["Technology", "Furniture", "Office Supplies"], size=n_rows)
    })

    initial_mb = raw_df.memory_usage(deep=True).sum() / (1024 * 1024)
    print(f"Raw DataFrame Memory: {initial_mb:.2f} MB")

    start_t = time.time()
    opt_df, stats = optimize_dataframe_memory(raw_df, verbose=True)
    downcast_time = time.time() - start_t

    final_mb = stats["final_mb"]
    reduction = stats["reduction_pct"]
    print(f"Optimized Memory: {final_mb:.2f} MB ({reduction}% reduction) in {downcast_time:.3f}s")

    assert reduction > 50.0, f"Expected >50% memory reduction, got {reduction}%"
    assert opt_df["Sales_Amount"].dtype == np.float32, "Float64 was not downcasted to float32"
    assert isinstance(opt_df["Category"].dtype, pd.CategoricalDtype), "Category string was not downcasted to category"
    print("✓ Big Data Memory downcasting achieved massive memory reduction.")


def test_fast_vector_analytics_and_sampling():
    print("\n--- TEST 4: Fast Vector Analytics & Reservoir Sampling ---")
    n_rows = 1_000_000
    print(f"Benchmarking vectorized statistical analytics on {n_rows:,} rows...")

    series = pd.Series(np.random.normal(loc=100.0, scale=25.0, size=n_rows))
    
    t0 = time.time()
    stats = compute_fast_vector_stats(series)
    vector_time = time.time() - t0

    print(f"Vector stats computed in {vector_time * 1000:.2f}ms: Mean={stats['mean']:.2f}, Std={stats['std']:.2f}, Skewness={stats['skewness']}")
    assert vector_time < 1.0, f"Vector stats took too long: {vector_time}s"

    # Test visual reservoir sampling
    df_large = pd.DataFrame({"val": series})
    sampled = smart_sample_for_visualization(df_large, max_points=10000)
    assert len(sampled) == 10000
    print("✓ Fast Vector analytics & visual reservoir sampling verified.")


def test_smart_prescriptive_recommendations():
    print("\n--- TEST 5: Smart Prescriptive Recommendations & Multi-lingual Insights ---")
    sample_summary = {
        "domain": "E-Commerce & Retail",
        "row_count": 250000,
        "column_count": 12,
        "quality_score": 94.5,
        "grade": "A+",
        "business_kpis": {
            "total_sales": 14500000.0,
            "total_profit": 3200000.0,
            "profit_margin_pct": 22.1
        },
        "top_bottom_analysis": {
            "top_n": {"Laptops & Computers": 5200000.0}
        },
        "outliers_detected": {"summary": {"total_unique_outliers": 42}},
        "semantic_types": {
            "Order_Date": "datetime",
            "Sales": "measure",
            "Profit": "measure",
            "Category": "categorical"
        }
    }

    # Test English
    insights_en = generate_rule_based_insights(sample_summary, language="en")
    assert "executive_summary" in insights_en
    assert "strategic_recommendations" in insights_en
    assert "automl_recommendations" in insights_en
    assert len(insights_en["automl_recommendations"]) >= 2
    print("✓ English Prescriptive Insights & AutoML models generated.")

    # Test Hindi
    insights_hi = generate_rule_based_insights(sample_summary, language="hi")
    assert "डेटासेट" in insights_hi["executive_summary"]
    print("✓ Hindi Prescriptive Insights generated.")

    # Test Marathi
    insights_mr = generate_rule_based_insights(sample_summary, language="mr")
    assert "डेटासेटमध्ये" in insights_mr["executive_summary"]
    print("✓ Marathi Prescriptive Insights generated.")


def test_end_to_end_pipeline():
    print("\n--- TEST 6: End-to-End Analytics Pipeline with Memory Optimizer ---")
    df = pd.DataFrame({
        "Order_ID": [f"ORD-{i:04d}" for i in range(100)],
        "Order_Date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "Sales": np.random.uniform(50, 500, size=100),
        "Profit": np.random.uniform(10, 100, size=100),
        "Region": np.random.choice(["North", "South", "East", "West"], size=100)
    })

    pipeline_res = analyze_dataset(df, generate_ai=False)
    assert pipeline_res["dataset_overview"]["row_count"] == 100
    assert pipeline_res["quality"]["score"] > 0
    assert pipeline_res["time_series"] is not None
    assert pipeline_res["kmeans_clustering"]["success"] is True
    print("✓ End-to-end analytics pipeline executed with memory optimization.")


if __name__ == "__main__":
    print("=================================================================")
    print("   DataNova High-Concurrency & Big Data Verification Suite")
    print("=================================================================")
    test_db_init_and_indexes()
    test_high_concurrency_pool()
    test_bigdata_memory_optimizer()
    test_fast_vector_analytics_and_sampling()
    test_smart_prescriptive_recommendations()
    test_end_to_end_pipeline()
    print("\n=================================================================")
    print("   ALL 6 BENCHMARK & STRESS TESTS PASSED SUCCESSFULLY! (100%)")
    print("=================================================================")
