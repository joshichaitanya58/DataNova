/* ==========================================================================
   DataNova — Manager Dashboard Interactive Controller
   Handles Business KPIs, Dynamic Plotly Analytics, Dataset Comparison,
   Predictions Preview, Share Dashboard, and Quick Action buttons.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Manager Controller Initialized.");

    // --- Quick Action Handlers ---
    const quickActions = document.querySelectorAll('.dn-quick-action, .dn-page-header .btn');
    quickActions.forEach(btn => {
        btn.addEventListener('click', function (e) {
            const text = (btn.textContent || '').trim().toLowerCase();
            if (text.includes('share dashboard')) {
                e.preventDefault();
                showShareDashboardModal();
            } else if (text.includes('generate report') || text.includes('view report')) {
                e.preventDefault();
                showToast("Generating Executive Business Summary Report...", "info");
                window.location.href = "/dashboard/analyst";
            } else if (text.includes('compare datasets') || text.includes('compare data')) {
                e.preventDefault();
                showCompareDatasetsModal();
            } else if (text.includes('view predictions') || text.includes('predictions')) {
                e.preventDefault();
                scrollToSection('Prediction Preview');
            } else if (text.includes('ai insights') || text.includes('insights')) {
                e.preventDefault();
                scrollToSection('AI Key Insights');
            } else if (text.includes('business dashboard') || text.includes('overview')) {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    });

    // --- Dynamic Business KPI & Plotly Analytics Auto-Fetch ---
    fetch('/api/manager/dashboard_data')
        .then(res => res.json())
        .then(resData => {
            if (resData.success && (resData.data || resData.metrics)) {
                const data = resData.data || resData.metrics;
                renderDashboardAnalytics(data);
            }
        })
        .catch(err => {
            console.log("Manager Analytics fetch warning, using fallback layout: ", err);
            renderDefaultPlotlyCharts();
        });

    function renderDashboardAnalytics(data) {
        if (data.total_revenue) updateKPI('Total Revenue', data.total_revenue);
        if (data.total_sales) updateKPI('Total Sales', data.total_sales);
        if (data.growth_rate) updateKPI('Growth Rate', data.growth_rate);
        if (data.top_category) updateKPI('Top Category', data.top_category);
        if (data.active_datasets !== undefined) updateKPI('Active Datasets', data.active_datasets);
        if (data.reports_generated !== undefined) updateKPI('Reports Generated', data.reports_generated);

        // Predictions
        if (data.predictions) {
            const p = data.predictions;
            if (p.predicted_sales && document.getElementById('predSales')) document.getElementById('predSales').textContent = p.predicted_sales;
            if (p.predicted_revenue && document.getElementById('predRevenue')) document.getElementById('predRevenue').textContent = p.predicted_revenue;
            if (p.expected_demand && document.getElementById('predDemand')) document.getElementById('predDemand').textContent = p.expected_demand;
            if (p.growth_forecast && document.getElementById('predGrowth')) document.getElementById('predGrowth').textContent = p.growth_forecast;
        }

        // Render Plotly Charts
        if (data.revenue_trend) renderRevenueChart(data.revenue_trend);
        else renderDefaultRevenueChart();

        if (data.category_perf) renderCategoryChart(data.category_perf);
        else renderDefaultCategoryChart();

        if (data.sales_perf) renderSalesChart(data.sales_perf);
        else renderDefaultSalesChart();

        // Regional Performance
        if (data.regional_perf && Array.isArray(data.regional_perf)) {
            renderRegionalPerformance(data.regional_perf);
        }

        // AI Insights
        if (data.ai_insights && Array.isArray(data.ai_insights)) {
            const listEl = document.getElementById('managerAiInsightsList');
            if (listEl) {
                listEl.innerHTML = data.ai_insights.map(ins => `<li><span class="dn-insight-dot" style="background:var(--dn-primary)"></span>${ins}</li>`).join('');
            }
        }

        // Trends
        if (data.trends && Array.isArray(data.trends)) {
            const listEl = document.getElementById('managerTrendsList');
            if (listEl) {
                listEl.innerHTML = data.trends.map(tr => `<li><span class="dn-insight-dot" style="background:var(--dn-green)"></span>${tr}</li>`).join('');
            }
        }

        // Recommendations
        if (data.recommendations && Array.isArray(data.recommendations)) {
            const container = document.getElementById('managerRecsContainer');
            if (container) {
                container.innerHTML = data.recommendations.map(rec => `<div class="dn-rec-item"><i class="bi bi-box-seam dn-rec-icon"></i><span class="dn-rec-text">${rec}</span></div>`).join('');
            }
        }

        // Team Activity
        if (data.team_activity && Array.isArray(data.team_activity)) {
            const listEl = document.getElementById('managerTeamActivityList');
            if (listEl) {
                listEl.innerHTML = data.team_activity.map(act => `<li><span class="dn-insight-dot" style="background:var(--dn-primary)"></span><strong>${act.user_name}</strong> ${act.action} <span class="text-secondary ms-auto small">${act.time_ago}</span></li>`).join('');
            }
        }
    }

    function updateKPI(label, value) {
        const cards = document.querySelectorAll('.dn-kpi-card');
        if (!cards || cards.length === 0) return;
        cards.forEach(card => {
            const l = card.querySelector('.dn-kpi-label');
            const v = card.querySelector('.dn-kpi-value');
            if (l && v && l.textContent.trim().toLowerCase() === label.toLowerCase()) {
                v.textContent = value;
            }
        });
    }

    // --- Plotly Chart Renderers ---
    function renderRevenueChart(trendData) {
        const container = document.getElementById('managerRevenueChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: trendData.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
            y: trendData.values || [120000, 145000, 160000, 195000, 210000, 250000, 290000],
            type: 'scatter',
            mode: 'lines+markers',
            fill: 'tozeroy',
            fillcolor: 'rgba(79, 70, 229, 0.15)',
            line: { color: '#4F46E5', width: 3, shape: 'spline' },
            marker: { size: 6, color: '#06B6D4' },
            hovertemplate: '<b>%{x}</b><br>Revenue: ₹%{y:,.0f}<extra></extra>'
        };

        const layout = {
            margin: { t: 10, r: 10, l: 40, b: 30 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8' },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8', tickprefix: '₹' },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderCategoryChart(catData) {
        const container = document.getElementById('managerCategoryChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: catData.values || [45, 25, 15, 10, 5],
            y: catData.labels || ['Electronics', 'Apparel', 'Home', 'Grocery', 'Services'],
            type: 'bar',
            orientation: 'h',
            marker: {
                color: ['#4F46E5', '#7C3AED', '#06B6D4', '#10B981', '#F59E0B']
            },
            hovertemplate: '<b>%{y}</b>: %{x}<extra></extra>'
        };

        const layout = {
            margin: { t: 10, r: 10, l: 80, b: 30 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8' },
            yaxis: { showgrid: false, color: '#94A3B8', autorange: 'reversed' },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderSalesChart(salesData) {
        const container = document.getElementById('managerSalesChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: salesData.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            y: salesData.values || [320, 410, 390, 520, 610, 700],
            type: 'bar',
            marker: { color: '#06B6D4', cornerradius: 4 },
            hovertemplate: '<b>%{x}</b><br>Sales: %{y:,}<extra></extra>'
        };

        const layout = {
            margin: { t: 10, r: 10, l: 40, b: 30 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8' },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8' },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderRegionalPerformance(regions) {
        const container = document.getElementById('managerRegionalContainer');
        if (!container) return;

        container.innerHTML = regions.map(reg => `
            <div class="dn-quality-row"><span class="dn-quality-label">${reg.region}</span>
                <div class="dn-quality-track">
                    <div class="dn-quality-fill" style="width:${reg.percentage}%;background:${reg.color || 'var(--dn-primary)'}"></div>
                </div><span class="dn-quality-value">${reg.percentage}%</span>
            </div>
        `).join('');
    }

    function renderDefaultPlotlyCharts() {
        renderRevenueChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'], values: [120000, 145000, 160000, 195000, 210000, 250000, 290000] });
        renderCategoryChart({ labels: ['Electronics', 'Apparel', 'Home', 'Grocery', 'Services'], values: [45, 25, 15, 10, 5] });
        renderSalesChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], values: [320, 410, 390, 520, 610, 700] });
    }

    function renderDefaultRevenueChart() {
        renderRevenueChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'], values: [120000, 145000, 160000, 195000, 210000, 250000, 290000] });
    }
    function renderDefaultCategoryChart() {
        renderCategoryChart({ labels: ['Electronics', 'Apparel', 'Home', 'Grocery', 'Services'], values: [45, 25, 15, 10, 5] });
    }
    function renderDefaultSalesChart() {
        renderSalesChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], values: [320, 410, 390, 520, 610, 700] });
    }

    // --- Share Dashboard Modal ---
    function showShareDashboardModal() {
        let modalEl = document.getElementById('dnShareModal');
        if (!modalEl) {
            const modalHtml = `
            <div class="modal fade" id="dnShareModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content dn-panel p-3">
                        <div class="modal-header border-0">
                            <h5 class="modal-title fw-bold"><i class="bi bi-share text-primary me-2"></i>Share Dashboard</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="dnShareForm">
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Dashboard Title</label>
                                    <input type="text" id="shareTitle" class="form-control" value="Q2 Executive Performance Overview" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Share With Role Group</label>
                                    <select id="shareRole" class="form-select">
                                        <option value="all">All Platform Users</option>
                                        <option value="viewer">Viewers Group</option>
                                        <option value="analyst">Analyst Team</option>
                                        <option value="manager">Management Group</option>
                                    </select>
                                </div>
                                <div class="text-end">
                                    <button type="button" class="btn btn-sm btn-secondary me-2" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-sm btn-primary dn-btn-primary"><i class="bi bi-send me-1"></i>Share Now</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>`;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            modalEl = document.getElementById('dnShareModal');
        }

        modalEl = document.getElementById('dnShareModal');
        if (!modalEl) {
            showToast("Failed to create share modal.", "danger");
            return;
        }

        const modalInstance = new bootstrap.Modal(modalEl);
        modalInstance.show();

        const form = document.getElementById('dnShareForm');
        if (form) {
            form.onsubmit = function (e) {
                e.preventDefault();
                const titleInput = document.getElementById('shareTitle');
                const roleSelect = document.getElementById('shareRole');
                if (!titleInput || !roleSelect) {
                    showToast("Form fields missing.", "danger");
                    return;
                }

                const payload = {
                    title: titleInput.value.trim(),
                    shared_with_role: roleSelect.value
                };

                if (!payload.title) {
                    showToast("Please enter a dashboard title.", "warning");
                    return;
                }

                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Sharing...';
                }

                fetch('/api/share_dashboard', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(res => res.json())
                .then(data => {
                    modalInstance.hide();
                    if (data.success) {
                        showToast(data.message, "success");
                    } else {
                        showToast(data.message || "Failed to share dashboard.", "danger");
                    }
                })
                .catch(err => {
                    modalInstance.hide();
                    showToast("Network error sharing dashboard.", "danger");
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-1"></i>Share Now';
                    }
                });
            };
        }
    }

    // --- Dataset Comparison Modal ---
    function showCompareDatasetsModal() {
        let modalEl = document.getElementById('dnCompareModal');
        if (!modalEl) {
            const modalHtml = `
            <div class="modal fade" id="dnCompareModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content dn-panel p-3">
                        <div class="modal-header border-0">
                            <h5 class="modal-title fw-bold"><i class="bi bi-columns-gap text-primary me-2"></i>Dataset Comparison Engine</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="dnCompareForm" class="row g-3 mb-3">
                                <div class="col-6">
                                    <label class="form-label small fw-semibold">Dataset 1 (Primary)</label>
                                    <input type="number" id="compareDatasetId1" class="form-control" placeholder="Enter Dataset ID (e.g. 1)" required>
                                </div>
                                <div class="col-6">
                                    <label class="form-label small fw-semibold">Dataset 2 (Benchmark)</label>
                                    <input type="number" id="compareDatasetId2" class="form-control" placeholder="Enter Dataset ID (e.g. 2)" required>
                                </div>
                                <div class="col-12 text-end">
                                    <button type="submit" class="btn btn-sm btn-primary dn-btn-primary"><i class="bi bi-arrow-left-right me-1"></i>Run Comparison</button>
                                </div>
                            </form>
                            <div id="dnCompareResults" style="display:none;"></div>
                        </div>
                    </div>
                </div>
            </div>`;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            modalEl = document.getElementById('dnCompareModal');
        }

        const modalInstance = new bootstrap.Modal(modalEl);
        modalInstance.show();

        const form = document.getElementById('dnCompareForm');
        const resultsContainer = document.getElementById('dnCompareResults');

        if (form) {
            form.onsubmit = function (e) {
                e.preventDefault();
                const id1 = document.getElementById('compareDatasetId1').value;
                const id2 = document.getElementById('compareDatasetId2').value;

                if (!id1 || !id2) {
                    showToast("Please enter two dataset IDs.", "warning");
                    return;
                }

                resultsContainer.style.display = 'block';
                resultsContainer.innerHTML = '<div class="text-center p-3"><div class="spinner-border text-primary" role="status"></div><p class="small text-muted mt-2">Comparing dataset metrics...</p></div>';

                fetch('/api/compare_datasets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id_1: parseInt(id1), dataset_id_2: parseInt(id2) })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.comparison) {
                        const c = data.comparison;
                        resultsContainer.innerHTML = `
                            <div class="row g-3">
                                <div class="col-6">
                                    <div class="p-3 border rounded bg-body-tertiary">
                                        <h6 class="fw-bold text-primary">Dataset #${c.dataset1.id}</h6>
                                        <div class="small">Rows: <strong>${c.dataset1.rows.toLocaleString()}</strong></div>
                                        <div class="small">Columns: <strong>${c.dataset1.columns}</strong></div>
                                        <div class="small">Quality Score: <strong>${c.dataset1.quality_score}% (${c.dataset1.grade})</strong></div>
                                        <div class="small">Missing Cells: <strong>${c.dataset1.missing_cells}</strong></div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="p-3 border rounded bg-body-tertiary">
                                        <h6 class="fw-bold text-primary">Dataset #${c.dataset2.id}</h6>
                                        <div class="small">Rows: <strong>${c.dataset2.rows.toLocaleString()}</strong></div>
                                        <div class="small">Columns: <strong>${c.dataset2.columns}</strong></div>
                                        <div class="small">Quality Score: <strong>${c.dataset2.quality_score}% (${c.dataset2.grade})</strong></div>
                                        <div class="small">Missing Cells: <strong>${c.dataset2.missing_cells}</strong></div>
                                    </div>
                                </div>
                                <div class="col-12">
                                    <div class="p-3 bg-primary-subtle text-primary rounded small">
                                        <i class="bi bi-info-circle-fill me-1"></i> Shared Columns (${c.common_columns_count}): <strong>${c.common_columns.join(', ') || 'None'}</strong>
                                    </div>
                                </div>
                            </div>
                        `;
                    } else {
                        resultsContainer.innerHTML = `<div class="alert alert-danger mb-0">${data.message || 'Comparison failed.'}</div>`;
                    }
                })
                .catch(err => {
                    resultsContainer.innerHTML = `<div class="alert alert-danger mb-0">Error contacting comparison service.</div>`;
                });
            };
        }
    }

    // --- Helper Functions ---
    function scrollToSection(titleText) {
        const panels = document.querySelectorAll('.dn-panel-title');
        for (let p of panels) {
            if (p.textContent && p.textContent.includes(titleText)) {
                p.scrollIntoView({ behavior: 'smooth', block: 'center' });
                const parent = p.parentElement ? p.parentElement.parentElement : null;
                if (parent) {
                    parent.classList.add('dn-pulse');
                    setTimeout(() => parent.classList.remove('dn-pulse'), 1500);
                }
                break;
            }
        }
    }

    function showToast(message, type = 'info') {
        let container = document.getElementById('dnToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'dnToastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1090';
            document.body.appendChild(container);
        }

        const bgClass = type === 'success' ? 'bg-success text-white' :
                        type === 'danger' ? 'bg-danger text-white' :
                        type === 'warning' ? 'bg-warning text-dark' : 'bg-dark text-white';

        const closeBtnClass = type === 'warning' ? 'btn-close' : 'btn-close btn-close-white';

        const toastHtml = `
        <div class="toast align-items-center ${bgClass} border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="${closeBtnClass} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = toastHtml.trim();
        const toastEl = tempDiv.firstChild;
        if (toastEl) {
            container.appendChild(toastEl);
            setTimeout(() => {
                if (toastEl && toastEl.parentNode) {
                    toastEl.remove();
                }
            }, 4000);
        }
    }
});