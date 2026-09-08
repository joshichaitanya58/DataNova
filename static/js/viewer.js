/* ==========================================================================
   DataNova — Viewer Dashboard Interactive Controller
   Handles shared dashboard viewing, report downloading, insights inspection,
   Plotly analytics rendering, and topbar search filtering.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Viewer Controller Initialized.");

    // --- Quick Action Handlers ---
    const quickActions = document.querySelectorAll('.dn-quick-action, .dn-page-header .btn');
    quickActions.forEach(btn => {
        btn.addEventListener('click', function (e) {
            const text = (btn.textContent || '').trim().toLowerCase();
            if (text.includes('view dashboard')) {
                e.preventDefault();
                scrollToSection('Shared Dashboards');
            } else if (text.includes('view insights') || text.includes('insights')) {
                e.preventDefault();
                scrollToSection('Key Insights');
            } else if (text.includes('view report') || text.includes('reports')) {
                e.preventDefault();
                scrollToSection('Reports');
            } else if (text.includes('download report') || text.includes('download')) {
                e.preventDefault();
                scrollToSection('Reports');
                showToast("Click the Download icon on any report in the table below.", "info");
            }
        });
    });

    // --- Topbar Search Filter ---
    const searchInput = document.querySelector('.dn-topbar-search input');
    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            const query = (e.target.value || '').trim().toLowerCase();
            filterSharedCards(query);
            filterReportsTable(query);
        });
    }

    function filterSharedCards(query) {
        const cards = document.querySelectorAll('#viewerSharedCardsContainer .col-md-6');
        cards.forEach(card => {
            const text = (card.textContent || '').toLowerCase();
            card.style.display = (!query || text.includes(query)) ? '' : 'none';
        });
    }

    function filterReportsTable(query) {
        const rows = document.querySelectorAll('#viewerReportsTable tbody tr');
        rows.forEach(row => {
            const text = (row.textContent || '').toLowerCase();
            row.style.display = (!query || text.includes(query)) ? '' : 'none';
        });
    }

    // --- Dynamic Viewer Analytics Auto-Fetch ---
    fetch('/api/viewer/dashboard_data')
        .then(res => res.json())
        .then(resData => {
            if (resData.success && resData.data) {
                renderViewerAnalytics(resData.data);
            }
        })
        .catch(err => {
            console.log("Viewer Analytics fetch warning, using fallback layout: ", err);
            renderDefaultPlotlyCharts();
        });

    function renderViewerAnalytics(data) {
        if (data.kpi) {
            if (data.kpi.shared_dashboards_count !== undefined && document.getElementById('kpiSharedCount')) {
                document.getElementById('kpiSharedCount').textContent = data.kpi.shared_dashboards_count;
            }
            if (data.kpi.reports_available !== undefined && document.getElementById('kpiReportsCount')) {
                document.getElementById('kpiReportsCount').textContent = data.kpi.reports_available;
            }
            if (data.kpi.recent_insights !== undefined && document.getElementById('kpiInsightsCount')) {
                document.getElementById('kpiInsightsCount').textContent = data.kpi.recent_insights;
            }
            if (data.kpi.last_updated && document.getElementById('kpiLastUpdated')) {
                document.getElementById('kpiLastUpdated').textContent = data.kpi.last_updated;
            }
        }

        // Render Plotly Charts
        if (data.sales_trend) renderSalesTrendChart(data.sales_trend);
        else renderDefaultSalesTrendChart();

        if (data.revenue_dist) renderRevenueDistChart(data.revenue_dist);
        else renderDefaultRevenueDistChart();

        if (data.category_perf) renderCategoryChart(data.category_perf);
        else renderDefaultCategoryChart();

        // Regional Performance
        if (data.regional_perf && Array.isArray(data.regional_perf)) {
            renderRegionalPerformance(data.regional_perf);
        }

        // Key Insights
        if (data.insights && Array.isArray(data.insights)) {
            const listEl = document.getElementById('viewerInsightsList');
            if (listEl) {
                listEl.innerHTML = data.insights.map(ins => `<li><span class="dn-insight-dot" style="background:var(--dn-primary)"></span>${ins}</li>`).join('');
            }
        }
    }

    // --- Plotly Chart Renderers ---
    function renderSalesTrendChart(salesData) {
        const container = document.getElementById('viewerSalesChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: salesData.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
            y: salesData.values || [105, 120, 115, 145, 135, 175, 190],
            type: 'scatter',
            mode: 'lines+markers',
            fill: 'tozeroy',
            fillcolor: 'rgba(79, 70, 229, 0.15)',
            line: { color: '#4F46E5', width: 3, shape: 'spline' },
            marker: { size: 6, color: '#06B6D4' },
            hovertemplate: '<b>%{x}</b><br>Sales Index: %{y}<extra></extra>'
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

    function renderRevenueDistChart(revData) {
        const container = document.getElementById('viewerRevenueChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: revData.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            y: revData.values || [45000, 60000, 50000, 80000, 65000, 92000],
            type: 'bar',
            marker: { color: '#06B6D4', cornerradius: 4 },
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
        const container = document.getElementById('viewerCategoryChart');
        if (!container || typeof Plotly === 'undefined') return;

        const trace = {
            x: catData.values || [90, 55, 70, 40, 20],
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

    function renderRegionalPerformance(regions) {
        const container = document.getElementById('viewerRegionalContainer');
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
        renderDefaultSalesTrendChart();
        renderDefaultRevenueDistChart();
        renderDefaultCategoryChart();
    }
    function renderDefaultSalesTrendChart() {
        renderSalesTrendChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'], values: [105, 120, 115, 145, 135, 175, 190] });
    }
    function renderDefaultRevenueDistChart() {
        renderRevenueDistChart({ labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], values: [45000, 60000, 50000, 80000, 65000, 92000] });
    }
    function renderDefaultCategoryChart() {
        renderCategoryChart({ labels: ['Electronics', 'Apparel', 'Home', 'Grocery', 'Services'], values: [90, 55, 70, 40, 20] });
    }

    // --- Report View & Download Buttons ---
    document.addEventListener('click', function (e) {
        const viewBtn = e.target.closest('.dn-table-action[title="View"]');
        const downloadBtn = e.target.closest('.dn-table-action[title="Download"], a.btn[href*="download"]');

        if (viewBtn) {
            e.preventDefault();
            const row = viewBtn.closest('tr');
            const reportName = row && row.cells[0] ? row.cells[0].innerText.trim() : 'EDA Report';
            const href = viewBtn.getAttribute('href') || '/api/export_eda_report/1';
            showToast(`Opening Executive Report Preview: "${reportName}"...`, "info");
            window.open(href, '_blank');
        }

        if (downloadBtn) {
            const row = downloadBtn.closest('tr');
            const reportName = row && row.cells[0] ? row.cells[0].innerText.trim() : 'EDA Report';
            showToast(`Downloading Report: "${reportName}"...`, "success");
        }
    });

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