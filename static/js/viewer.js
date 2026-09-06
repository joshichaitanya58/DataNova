/* ==========================================================================
   DataNova — Viewer Dashboard Interactive Controller
   Handles Plotly analytics, live search & format filtering for reports,
   modal preview triggers, and read-only dashboard navigation.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Viewer Controller Initialized.");

    let reportModalInstance = null;
    const reportModalEl = document.getElementById('dnReportDetailsModal');
    if (reportModalEl) {
        reportModalInstance = new bootstrap.Modal(reportModalEl);
    }

    // --- Action Triggers (Event Delegation) ---
    document.body.addEventListener('click', function (e) {
        const trigger = e.target.closest('[data-action]');
        if (!trigger) return;

        const action = trigger.getAttribute('data-action');

        switch (action) {
            case 'nav-tasks':
                scrollToSection('Assigned Work');
                break;

            case 'nav-shared':
                scrollToSection('Shared Dashboards');
                break;

            case 'nav-analytics':
                scrollToSection('Read-Only Data Visualizations');
                break;

            case 'nav-insights':
                scrollToSection('Key Insights');
                break;

            case 'nav-reports':
                scrollToSection('Accessible Platform Reports');
                break;

            case 'update-task-status':
                e.preventDefault();
                const taskId = trigger.getAttribute('data-task-id');
                const newStatus = trigger.getAttribute('data-status');
                if (taskId && newStatus) {
                    trigger.disabled = true;
                    fetch('/api/manager/update_task_status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task_id: taskId, status: newStatus })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message || `Task updated to ${newStatus}.`, "success");
                            refreshViewerTasks();
                            if (window.DataNovaStateBus) {
                                if (typeof window.DataNovaStateBus.notify === 'function') {
                                    window.DataNovaStateBus.notify('MUTATION_TASK_UPDATE', { task_id: taskId, status: newStatus });
                                } else if (typeof window.DataNovaStateBus.emit === 'function') {
                                    window.DataNovaStateBus.emit('MUTATION_TASK_UPDATE', { task_id: taskId, status: newStatus });
                                }
                            }
                        } else {
                            showToast(data.message || 'Failed to update task.', "danger");
                        }
                    })
                    .catch(err => {
                        console.error('Task update error:', err);
                        showToast('Error updating task status.', 'danger');
                    })
                    .finally(() => {
                        trigger.disabled = false;
                    });
                }
                break;

            case 'preview-report':
                e.preventDefault();
                const reportName = trigger.getAttribute('data-report-name') || 'EDA Report';
                const datasetId = trigger.getAttribute('data-dataset-id') || '1';
                showReportPreviewModal(reportName, datasetId);
                break;

            case 'download-report':
                showToast("Preparing report download...", "success");
                break;

            case 'help':
                e.preventDefault();
                showToast("Viewer Portal: Read-only access to shared dashboards, reports, and AI insights.", "info");
                break;
        }
    });

    // --- Report Modal Preview ---
    function showReportPreviewModal(title, datasetId) {
        if (!reportModalInstance && reportModalEl) {
            reportModalInstance = new bootstrap.Modal(reportModalEl);
        }

        const titleEl = document.getElementById('modalReportTitle');
        const datasetEl = document.getElementById('modalReportDataset');
        const linkEl = document.getElementById('modalReportDownloadLink');

        if (titleEl) titleEl.textContent = title;
        if (datasetEl) datasetEl.textContent = `Associated Dataset #${datasetId}`;
        if (linkEl) linkEl.href = `/api/export_eda_report/${datasetId}`;

        if (reportModalInstance) reportModalInstance.show();
    }

    // --- Dynamic Search & Filter for Reports ---
    const searchInput = document.getElementById('viewerReportSearchInput') || document.getElementById('viewerGlobalSearch');
    const formatFilter = document.getElementById('viewerReportFormatFilter');
    const resetBtn = document.getElementById('resetReportFilterBtn');

    if (searchInput) {
        searchInput.addEventListener('input', filterReportsTable);
    }
    if (formatFilter) {
        formatFilter.addEventListener('change', filterReportsTable);
    }
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (formatFilter) formatFilter.value = 'all';
            filterReportsTable();
            showToast("Report filters reset.", "info");
        });
    }

    function filterReportsTable() {
        const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
        const fmt = formatFilter ? formatFilter.value.toLowerCase() : 'all';

        const rows = document.querySelectorAll('#viewerReportsTableBody tr');
        let visibleCount = 0;

        rows.forEach(row => {
            if (row.cells.length < 4) return;
            const text = row.textContent.toLowerCase();
            const formatText = row.cells[3].textContent.toLowerCase();

            const matchesQuery = !query || text.includes(query);
            const matchesFormat = (fmt === 'all') || formatText.includes(fmt);

            if (matchesQuery && matchesFormat) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        const tbody = document.getElementById('viewerReportsTableBody');
        let emptyRow = document.getElementById('viewerReportEmptyRow');

        if (visibleCount === 0 && tbody) {
            if (!emptyRow) {
                emptyRow = document.createElement('tr');
                emptyRow.id = 'viewerReportEmptyRow';
                emptyRow.innerHTML = `
                    <td colspan="5" class="text-center text-muted py-4">
                        <i class="bi bi-search fs-3 d-block mb-1"></i> No matching reports found for your filter.
                    </td>`;
                tbody.appendChild(emptyRow);
            } else {
                emptyRow.style.display = '';
            }
        } else if (emptyRow) {
            emptyRow.style.display = 'none';
        }
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
            console.log("Viewer Analytics fetch warning: ", err);
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
        if (data.sales_trend && data.sales_trend.values) renderSalesTrendChart(data.sales_trend);
        if (data.revenue_dist && data.revenue_dist.values) renderRevenueDistChart(data.revenue_dist);
        if (data.category_perf && data.category_perf.values) renderCategoryChart(data.category_perf);

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
        if (!container || typeof Plotly === 'undefined' || !salesData || !salesData.values) return;

        const trace = {
            x: salesData.labels || [],
            y: salesData.values || [],
            type: 'scatter',
            mode: 'lines+markers',
            fill: 'tozeroy',
            fillcolor: 'rgba(79, 70, 229, 0.15)',
            line: { color: '#4F46E5', width: 3, shape: 'spline' },
            marker: { size: 6, color: '#06B6D4' }
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
        if (!container || typeof Plotly === 'undefined' || !revData || !revData.values) return;

        const trace = {
            x: revData.labels || [],
            y: revData.values || [],
            type: 'bar',
            marker: { color: '#06B6D4' }
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
        if (!container || typeof Plotly === 'undefined' || !catData || !catData.values) return;

        const trace = {
            x: catData.values || [],
            y: catData.labels || [],
            type: 'bar',
            orientation: 'h',
            marker: { color: ['#4F46E5', '#7C3AED', '#06B6D4', '#10B981', '#F59E0B'] }
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

    window.addEventListener('resize', function () {
        ['viewerSalesChart', 'viewerRevenueChart', 'viewerCategoryChart'].forEach(id => {
            const el = document.getElementById(id);
            if (el && typeof Plotly !== 'undefined') {
                try { Plotly.Plots.resize(el); } catch (e) { }
            }
        });
    });

    // Helper functions
    function scrollToSection(titleText) {
        const panels = document.querySelectorAll('.dn-panel-title');
        for (let p of panels) {
            if (p.textContent && p.textContent.includes(titleText)) {
                p.scrollIntoView({ behavior: 'smooth', block: 'center' });
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

        const toastHtml = `
        <div class="toast align-items-center ${bgClass} border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = toastHtml.trim();
        const toastEl = tempDiv.firstChild;
        if (toastEl) {
            container.appendChild(toastEl);
            setTimeout(() => { if (toastEl && toastEl.parentNode) toastEl.remove(); }, 4000);
        }
    }

    // --- Assigned Tasks Rendering and Refresh for Viewer ---
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderViewerTasks(tasks) {
        const tbody = document.getElementById('viewerAssignedTasksTableBody');
        const badge = document.getElementById('viewerAssignedTasksBadge');
        if (badge) {
            badge.textContent = tasks ? tasks.length : 0;
        }
        if (!tbody) return;

        if (!tasks || tasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-secondary py-4">
                        <i class="bi bi-check2-circle fs-3 d-block mb-1 text-muted"></i> No tasks currently assigned to you.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = tasks.map(task => {
            let priorityBadge = '<span class="badge bg-info-subtle text-info border border-info-subtle">Low</span>';
            if (task.priority === 'High') {
                priorityBadge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-exclamation-triangle me-1"></i>High</span>';
            } else if (task.priority === 'Medium') {
                priorityBadge = '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Medium</span>';
            }

            let statusBadge = '<span class="badge bg-amber text-dark" style="background:#f59e0b"><i class="bi bi-clock me-1"></i>Pending</span>';
            let actionButtons = `
                <button class="btn btn-outline-primary" data-action="update-task-status" data-task-id="${task.id}" data-status="In Progress"><i class="bi bi-play-fill me-1"></i> Start</button>
                <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Done</button>
            `;

            if (task.status === 'Completed') {
                statusBadge = '<span class="badge bg-success text-white"><i class="bi bi-check-circle me-1"></i>Completed</span>';
                actionButtons = `<span class="badge bg-success-subtle text-success border border-success-subtle py-2 px-2"><i class="bi bi-check2-all me-1"></i>Completed</span>`;
            } else if (task.status === 'In Progress') {
                statusBadge = '<span class="badge bg-primary text-white"><i class="bi bi-hourglass-split me-1"></i>In Progress</span>';
                actionButtons = `
                    <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Complete</button>
                    <button class="btn btn-outline-secondary" data-action="update-task-status" data-task-id="${task.id}" data-status="Pending"><i class="bi bi-pause-fill me-1"></i> Pause</button>
                `;
            } else if (task.status === 'Reopened') {
                statusBadge = '<span class="badge bg-warning text-dark border border-warning-subtle"><i class="bi bi-arrow-counterclockwise me-1"></i>Reopened</span>';
                actionButtons = `
                    <button class="btn btn-outline-primary" data-action="update-task-status" data-task-id="${task.id}" data-status="In Progress"><i class="bi bi-play-fill me-1"></i> Start</button>
                    <button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${task.id}" data-status="Completed"><i class="bi bi-check-lg me-1"></i> Done</button>
                `;
            }

            const descHtml = task.description ? `<div class="small text-secondary text-truncate" style="max-width:300px;">${escapeHtml(task.description)}</div>` : '';
            const datasetBadge = task.dataset_file_name ? `<div class="small mt-1 text-primary d-inline-flex align-items-center bg-primary-subtle px-2 py-0 rounded border border-primary-subtle" style="font-size:0.75rem;"><i class="bi bi-file-earmark-spreadsheet me-1"></i>${escapeHtml(task.dataset_file_name)}</div>` : '';
            const remarkHtml = task.remark ? `<div class="small mt-1 p-1 px-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle" style="max-width:320px;"><i class="bi bi-chat-left-dots-fill me-1"></i><strong>Manager Remark:</strong> ${escapeHtml(task.remark)}</div>` : '';

            return `
                <tr data-task-id="${task.id}">
                    <td>
                        <div class="fw-semibold">${escapeHtml(task.task_title || '')}</div>
                        ${descHtml}
                        ${datasetBadge}
                        ${remarkHtml}
                    </td>
                    <td>
                        <div class="small fw-semibold">${escapeHtml(task.manager_name || 'Management')}</div>
                        <div class="small text-secondary">${escapeHtml(task.manager_email || '')}</div>
                    </td>
                    <td>${priorityBadge}</td>
                    <td class="small">${escapeHtml(task.due_date || 'Flexible')}</td>
                    <td>${statusBadge}</td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            ${actionButtons}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function refreshViewerTasks() {
        const btn = document.getElementById('refreshViewerTasksBtn');
        if (btn) btn.classList.add('disabled');
        fetch('/api/user/assigned_tasks')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.tasks) {
                    renderViewerTasks(data.tasks);
                }
            })
            .catch(err => console.warn('Could not refresh viewer assigned tasks:', err))
            .finally(() => {
                if (btn) btn.classList.remove('disabled');
            });
    }

    const refreshViewerBtn = document.getElementById('refreshViewerTasksBtn');
    if (refreshViewerBtn) {
        refreshViewerBtn.addEventListener('click', function (e) {
            e.preventDefault();
            refreshViewerTasks();
        });
    }

    // --- Shared Dashboards & Modal Preview for Viewer ---
    const sharedDetailModalEl = document.getElementById('sharedDashboardDetailModal');
    let sharedDetailModalInstance = null;
    if (sharedDetailModalEl) {
        sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
    }

    function fetchViewerSharedDashboards() {
        const container = document.getElementById('viewerSharedCardsContainer');
        fetch('/api/shared_dashboards/list')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.dashboards) {
                    renderViewerSharedDashboards(data.dashboards);
                }
            })
            .catch(err => console.warn('Could not fetch viewer shared dashboards:', err));
    }

    function renderViewerSharedDashboards(dashboards) {
        const container = document.getElementById('viewerSharedCardsContainer');
        if (!container) return;

        if (!dashboards || dashboards.length === 0) {
            container.innerHTML = `
                <div class="col-12">
                    <div class="p-4 text-center text-secondary border rounded-3 bg-light-subtle">
                        <i class="bi bi-share fs-2 mb-2 d-block text-muted"></i>
                        <div class="fw-medium">No shared dashboards available</div>
                        <small>Dashboards shared by team managers and analysts will appear here.</small>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = dashboards.map(sd => {
            let statusBadge = '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">Shared</span>';
            if (sd.status === 'Approved') {
                statusBadge = '<span class="badge bg-success text-white"><i class="bi bi-check-circle me-1"></i>Approved</span>';
            } else if (sd.status === 'Reopened') {
                statusBadge = '<span class="badge bg-warning text-dark"><i class="bi bi-arrow-counterclockwise me-1"></i>Revision Requested</span>';
            }

            const remarkHtml = sd.remark ? `
                <div class="small mt-2 p-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle">
                    <i class="bi bi-chat-left-quote-fill me-1"></i><strong>Manager Feedback:</strong> ${escapeHtml(sd.remark)}
                </div>
            ` : '';

            return `
                <div class="col-md-6 col-lg-4">
                    <div class="dn-predict-card h-100 d-flex flex-column justify-content-between">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <div class="fw-semibold text-truncate" style="max-width:200px;" title="${escapeHtml(sd.title)}">${escapeHtml(sd.title)}</div>
                                ${statusBadge}
                            </div>
                            <div class="small text-secondary mb-1">Owner: <strong>${escapeHtml(sd.owner_name)}</strong> (${escapeHtml(sd.owner_role)})</div>
                            <div class="small text-secondary mb-2">${escapeHtml(sd.dataset_name)} &bull; ${Number(sd.row_count || 0).toLocaleString()} rows</div>
                            ${sd.description ? `<p class="small text-muted mb-2 text-truncate" style="max-height:40px;">${escapeHtml(sd.description)}</p>` : ''}
                            ${remarkHtml}
                        </div>
                        <div class="pt-2 mt-2 border-top">
                            <button class="btn dn-btn-outline-dn btn-sm w-100 btn-viewer-view-shared" data-shared-id="${sd.id}">
                                <i class="bi bi-eye me-1"></i> View Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach view click handlers
        container.querySelectorAll('.btn-viewer-view-shared').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const sharedId = this.getAttribute('data-shared-id');
                if (sharedId) {
                    openViewerSharedDetail(sharedId);
                }
            });
        });
    }

    function openViewerSharedDetail(sharedId) {
        if (!sharedDetailModalInstance && sharedDetailModalEl) {
            sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
        }

        fetch(`/api/shared_dashboard/view/${sharedId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.dashboard) {
                    const sd = data.dashboard;

                    const titleEl = document.getElementById('sharedDetailTitle');
                    const metaEl = document.getElementById('sharedDetailMeta');
                    const statusBadge = document.getElementById('sharedDetailStatusBadge');
                    const descContainer = document.getElementById('sharedDetailDescContainer');
                    const descText = document.getElementById('sharedDetailDescText');
                    const remarkBanner = document.getElementById('sharedDetailRemarkBanner');
                    const remarkText = document.getElementById('sharedDetailRemarkText');
                    const fileText = document.getElementById('sharedDetailDatasetFile');

                    if (titleEl) titleEl.textContent = sd.title;
                    if (metaEl) metaEl.textContent = `Shared by ${sd.owner_name} (${sd.owner_role}) • ${sd.created_at_str}`;
                    if (fileText) fileText.textContent = `Dataset: ${sd.dataset_name}`;

                    if (statusBadge) {
                        statusBadge.textContent = sd.status;
                        statusBadge.className = 'badge ' + (sd.status === 'Approved' ? 'bg-success' : sd.status === 'Reopened' ? 'bg-warning text-dark' : 'bg-primary');
                    }

                    if (descContainer && descText) {
                        if (sd.description) {
                            descContainer.style.display = 'flex';
                            descText.textContent = sd.description;
                        } else {
                            descContainer.style.display = 'none';
                        }
                    }

                    if (remarkBanner && remarkText) {
                        if (sd.remark) {
                            remarkBanner.style.display = 'flex';
                            remarkText.textContent = sd.remark;
                        } else {
                            remarkBanner.style.display = 'none';
                        }
                    }

                    // KPIs
                    const rEl = document.getElementById('sdKpiRows');
                    const cEl = document.getElementById('sdKpiCols');
                    const mEl = document.getElementById('sdKpiMemory');
                    const qEl = document.getElementById('sdKpiQuality');
                    const miEl = document.getElementById('sdKpiMissing');
                    const dEl = document.getElementById('sdKpiDuplicates');

                    if (rEl) rEl.textContent = Number(sd.row_count || 0).toLocaleString();
                    if (cEl) cEl.textContent = Number(sd.column_count || 0).toLocaleString();
                    if (mEl) mEl.textContent = sd.memory_usage || '0 KB';
                    if (qEl) qEl.textContent = `${sd.quality_score || 100}%`;
                    if (miEl) miEl.textContent = Number(sd.missing_count || 0).toLocaleString();
                    if (dEl) dEl.textContent = Number(sd.duplicate_count || 0).toLocaleString();

                    // Preview Table
                    const prevContainer = document.getElementById('sharedDetailPreviewContainer');
                    if (prevContainer) {
                        prevContainer.innerHTML = sd.preview_html || '<div class="p-3 text-muted">No preview table available.</div>';
                    }

                    // AI Insights
                    const insightsContainer = document.getElementById('sharedDetailInsightsContainer');
                    if (insightsContainer) {
                        if (sd.insights && sd.insights.length > 0) {
                            insightsContainer.innerHTML = `<ul class="mb-0 ps-3">${sd.insights.map(i => `<li>${i}</li>`).join('')}</ul>`;
                        } else {
                            insightsContainer.innerHTML = '<span class="text-muted small">No AI findings generated yet.</span>';
                        }
                    }

                    if (sharedDetailModalInstance) {
                        sharedDetailModalInstance.show();
                    }
                } else {
                    showToast(data.message || 'Could not load shared dashboard.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error fetching dashboard details:', err);
                showToast('Error loading shared dashboard details.', 'danger');
            });
    }

    // Auto-fetch viewer shared dashboards on load
    fetchViewerSharedDashboards();

    // Global State Bus Listener for Viewer Dashboard
    if (window.DataNovaStateBus) {
        window.DataNovaStateBus.on('*', function (eventType) {
            console.log("Viewer Dashboard syncing with Global State Bus:", eventType);
            if (eventType === 'MUTATION_TASK_ASSIGNED' || eventType === 'MUTATION_TASK_UPDATE') {
                refreshViewerTasks();
            }
            if (eventType === 'MUTATION_DASHBOARD_SHARED' || eventType === 'MUTATION_DASHBOARD_REVIEWED') {
                fetchViewerSharedDashboards();
            }
            fetch('/api/viewer/dashboard_data')
                .then(res => res.json())
                .then(resData => {
                    if (resData.success && resData.data) {
                        renderViewerAnalytics(resData.data);
                    }
                })
                .catch(err => console.warn('State bus viewer sync error:', err));
        });
    }
});