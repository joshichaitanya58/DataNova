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
            case 'nav-dashboard':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('dashboardOverview'), trigger);
                break;

            case 'nav-tasks':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('assignedTasksPanel'), trigger);
                break;

            case 'nav-shared':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('shared'), trigger);
                break;

            case 'nav-analytics':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('analytics'), trigger);
                break;

            case 'nav-insights':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('insights'), trigger);
                break;

            case 'nav-reports':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('reports'), trigger);
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
    function smoothScrollToElement(targetEl, linkEl) {
        if (!targetEl) return;

        if (linkEl) {
            document.querySelectorAll('.dn-sidebar-scroll .dn-nav-link').forEach(nl => nl.classList.remove('active'));
            linkEl.classList.add('active');
        }

        const topbar = document.querySelector('.dn-topbar');
        const topbarHeight = topbar ? topbar.offsetHeight : 68;
        const targetRect = targetEl.getBoundingClientRect();
        const offsetTop = targetRect.top + window.pageYOffset - (topbarHeight + 16);

        window.scrollTo({
            top: Math.max(0, offsetTop),
            behavior: 'smooth'
        });

        targetEl.classList.remove('dn-section-highlight');
        void targetEl.offsetWidth; // force reflow
        targetEl.classList.add('dn-section-highlight');
        setTimeout(() => targetEl.classList.remove('dn-section-highlight'), 1600);

        const appShell = document.querySelector('.dn-app');
        const overlay = document.querySelector('.dn-sidebar-overlay');
        if (window.innerWidth <= 991.98 && appShell && appShell.classList.contains('dn-sidebar-open')) {
            appShell.classList.remove('dn-sidebar-open');
            if (overlay) overlay.classList.remove('is-visible');
        }
    }

    function scrollToSection(titleText) {
        const panels = document.querySelectorAll('.dn-panel-title');
        for (let p of panels) {
            if (p.textContent && p.textContent.includes(titleText)) {
                const section = p.closest('.dn-panel') || p.closest('.row') || p;
                smoothScrollToElement(section);
                break;
            }
        }
    }

    // Direct Anchor Click binding for all Viewer Sidebar Nav links
    document.querySelectorAll('.dn-sidebar-scroll .dn-nav-link').forEach(link => {
        link.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#') && href.length > 1) {
                const targetId = href.substring(1);
                const targetEl = document.getElementById(targetId);
                if (targetEl) {
                    e.preventDefault();
                    smoothScrollToElement(targetEl, this);
                }
            }
        });
    });

    // ScrollSpy observer for viewer dashboard
    const viewerSectionIds = [
        'dashboardOverview',
        'assignedTasksPanel',
        'shared',
        'analytics',
        'insights',
        'reports'
    ];

    let viewerScrollTimeout = null;
    window.addEventListener('scroll', function () {
        if (viewerScrollTimeout) return;
        viewerScrollTimeout = setTimeout(function () {
            viewerScrollTimeout = null;
            const scrollPos = window.pageYOffset + 140;

            let currentSectionId = null;
            for (let i = 0; i < viewerSectionIds.length; i++) {
                const el = document.getElementById(viewerSectionIds[i]);
                if (el) {
                    const top = el.offsetTop;
                    const height = el.offsetHeight;
                    if (scrollPos >= top && scrollPos < top + height) {
                        currentSectionId = viewerSectionIds[i];
                    }
                }
            }

            if (currentSectionId) {
                document.querySelectorAll('.dn-sidebar-scroll .dn-nav-link').forEach(link => {
                    const href = link.getAttribute('href') || '';
                    if (href === '#' + currentSectionId) {
                        link.classList.add('active');
                    } else if (href.startsWith('#')) {
                        link.classList.remove('active');
                    }
                });
            }
        }, 80);
    }, { passive: true });

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

            // Render recipient user badges
            let recipientsHtml = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle extra-small">All Team Members</span>';
            if (sd.shared_with_users && sd.shared_with_users.length > 0) {
                recipientsHtml = sd.shared_with_users.map(u => {
                    return `<span class="badge bg-primary-subtle text-primary border border-primary-subtle extra-small" title="${escapeHtml(u.email || '')}">${escapeHtml(u.name)} (${escapeHtml(u.role || 'User')})</span>`;
                }).join(' ');
            }

            return `
                <div class="col-md-6 col-lg-4">
                    <div class="dn-predict-card h-100 d-flex flex-column justify-content-between p-3 border rounded shadow-sm">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <div class="fw-semibold text-truncate" style="max-width:200px;" title="${escapeHtml(sd.title)}">${escapeHtml(sd.title)}</div>
                                ${statusBadge}
                            </div>
                            <div class="small text-secondary mb-1">Owner: <strong>${escapeHtml(sd.owner_name)}</strong> (${escapeHtml(sd.owner_role)})</div>
                            <div class="small text-secondary mb-2">${escapeHtml(sd.dataset_name)} &bull; ${Number(sd.row_count || 0).toLocaleString()} rows</div>
                            
                            <!-- Recipient Users List -->
                            <div class="small mb-2 p-2 rounded bg-body-tertiary border">
                                <span class="text-secondary d-block fw-semibold mb-1" style="font-size:0.75rem;"><i class="bi bi-people-fill text-primary me-1"></i>Shared With:</span>
                                <div class="d-flex flex-wrap gap-1">${recipientsHtml}</div>
                            </div>

                            ${sd.description ? `<p class="small text-muted mb-2 text-truncate" style="max-height:40px;">${escapeHtml(sd.description)}</p>` : ''}
                            ${remarkHtml}
                        </div>
                        <div class="pt-2 mt-2 border-top">
                            <button class="btn dn-btn-outline-dn btn-sm w-100 btn-viewer-view-shared" data-shared-id="${sd.id}">
                                <i class="bi bi-eye me-1"></i> View Full Dashboard
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
                    const domainBadge = document.getElementById('sharedDetailDomainBadge');
                    const descContainer = document.getElementById('sharedDetailDescContainer');
                    const descText = document.getElementById('sharedDetailDescText');
                    const remarkBanner = document.getElementById('sharedDetailRemarkBanner');
                    const remarkText = document.getElementById('sharedDetailRemarkText');
                    const fileText = document.getElementById('sharedDetailDatasetFile');

                    if (titleEl) titleEl.textContent = sd.title;
                    if (metaEl) metaEl.textContent = `Shared by ${sd.owner_name} (${sd.owner_role}) • ${sd.created_at_str}`;
                    if (fileText) fileText.textContent = `Dataset: ${sd.dataset_name}`;
                    if (domainBadge) domainBadge.textContent = sd.business_domain || 'General Analytics';

                    if (statusBadge) {
                        statusBadge.textContent = sd.status;
                        statusBadge.className = 'badge ' + (sd.status === 'Approved' ? 'bg-success' : sd.status === 'Reopened' ? 'bg-warning text-dark' : 'bg-primary');
                    }

                    // Populate Recipients list in modal
                    const recListEl = document.getElementById('sharedDetailRecipientsList');
                    if (recListEl) {
                        if (sd.shared_with_users && sd.shared_with_users.length > 0) {
                            recListEl.innerHTML = sd.shared_with_users.map(u => `
                                <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1">
                                    <i class="bi bi-person-fill me-1"></i>${escapeHtml(u.name)} <small class="opacity-75">(${escapeHtml(u.role || 'User')})</small>
                                </span>
                            `).join('');
                        } else {
                            recListEl.innerHTML = '<span class="badge bg-secondary-subtle text-secondary">All Team Members</span>';
                        }
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

                    // 1. KPIs & Overview
                    const rEl = document.getElementById('sdKpiRows');
                    const cEl = document.getElementById('sdKpiCols');
                    const mEl = document.getElementById('sdKpiMemory');
                    const qEl = document.getElementById('sdKpiQuality');
                    const miEl = document.getElementById('sdKpiMissing');
                    const dEl = document.getElementById('sdKpiDuplicates');

                    if (rEl) rEl.textContent = Number(sd.row_count || 0).toLocaleString();
                    if (cEl) cEl.textContent = Number(sd.column_count || 0).toLocaleString();
                    if (mEl) mEl.textContent = sd.memory_usage || '0 KB';
                    if (qEl) qEl.textContent = `${sd.quality_score || 100}% (${sd.quality_grade || 'A+'})`;
                    if (miEl) miEl.textContent = Number(sd.missing_count || 0).toLocaleString();
                    if (dEl) dEl.textContent = Number(sd.duplicate_count || 0).toLocaleString();

                    const execSumEl = document.getElementById('sdExecSummaryText');
                    if (execSumEl) {
                        execSumEl.textContent = sd.ai_explanation?.executive_summary || 'Comprehensive end-to-end analytics pipeline executed across all dataset attributes.';
                    }

                    const hlListEl = document.getElementById('sdQuickHighlightsList');
                    if (hlListEl) {
                        const hl = [];
                        hl.push(`<strong>Data Scale:</strong> Verified <strong>${Number(sd.row_count || 0).toLocaleString()} rows</strong> across <strong>${sd.column_count || 0} features</strong> in domain <em>${escapeHtml(sd.business_domain || 'General')}</em>.`);
                        hl.push(`<strong>Data Hygiene:</strong> Quality grade <strong>${sd.quality_grade || 'A+'}</strong> (${sd.quality_score || 100}/100) with <strong>${sd.duplicates_removed || 0} duplicates removed</strong>.`);
                        if (sd.imputation_details && sd.imputation_details.length > 0) {
                            hl.push(`<strong>Imputation:</strong> Successfully resolved null values across <strong>${sd.imputation_details.length} columns</strong>.`);
                        }
                        if (sd.dropped_columns && sd.dropped_columns.length > 0) {
                            hl.push(`<strong>Feature Optimization:</strong> Isolated <strong>${sd.dropped_columns.length} low-variance / redundant columns</strong>.`);
                        }
                        hlListEl.innerHTML = hl.map(x => `<li class="mb-1">${x}</li>`).join('');
                    }

                    // 2. Charts Showcase & Correlations
                    const topCorrsSection = document.getElementById('sdTopCorrsSection');
                    const posList = document.getElementById('sdTopPositiveList');
                    const negList = document.getElementById('sdTopNegativeList');
                    if (topCorrsSection && posList && negList) {
                        const hasPos = sd.top_positive_corrs && sd.top_positive_corrs.length > 0;
                        const hasNeg = sd.top_negative_corrs && sd.top_negative_corrs.length > 0;
                        if (hasPos || hasNeg) {
                            posList.innerHTML = (sd.top_positive_corrs || []).map(p => `
                                <li class="list-group-item d-flex justify-content-between align-items-center py-1 px-2 bg-transparent">
                                    <span>${escapeHtml(p.var1)} &harr; ${escapeHtml(p.var2)}</span>
                                    <span class="badge bg-success-subtle text-success border border-success-subtle">+${Number(p.correlation).toFixed(2)}</span>
                                </li>
                            `).join('') || '<li class="list-group-item text-muted py-1 px-2 bg-transparent">No strong positive pairs</li>';

                            negList.innerHTML = (sd.top_negative_corrs || []).map(p => `
                                <li class="list-group-item d-flex justify-content-between align-items-center py-1 px-2 bg-transparent">
                                    <span>${escapeHtml(p.var1)} &harr; ${escapeHtml(p.var2)}</span>
                                    <span class="badge bg-danger-subtle text-danger border border-danger-subtle">${Number(p.correlation).toFixed(2)}</span>
                                </li>
                            `).join('') || '<li class="list-group-item text-muted py-1 px-2 bg-transparent">No strong negative pairs</li>';
                            topCorrsSection.style.display = 'block';
                        } else {
                            topCorrsSection.style.display = 'none';
                        }
                    }

                    const chartsGrid = document.getElementById('sdChartsGridContainer');
                    if (chartsGrid) {
                        if (sd.charts_showcase && sd.charts_showcase.length > 0) {
                            chartsGrid.innerHTML = sd.charts_showcase.map(c => `
                                <div class="col-md-6">
                                    <div class="border rounded p-3 bg-body-tertiary h-100 d-flex flex-column justify-content-between">
                                        <div>
                                            <h6 class="fw-bold mb-1 text-primary">${escapeHtml(c.title || 'Analytical Visualization')}</h6>
                                            <p class="small text-muted mb-2">${escapeHtml(c.description || '')}</p>
                                        </div>
                                        <div class="text-center my-auto">
                                            <img src="data:image/png;base64,${c.plot}" alt="${escapeHtml(c.title || 'Chart')}" class="img-fluid rounded border bg-white shadow-sm" style="max-height: 280px; width: 100%; object-fit: contain;">
                                        </div>
                                    </div>
                                </div>
                            `).join('');
                        } else {
                            chartsGrid.innerHTML = '<div class="col-12"><div class="alert alert-info small mb-0">Visualizations are being rendered for this dataset.</div></div>';
                        }
                    }

                    // 3. Cleaning Audit Trail
                    const droppedTbody = document.getElementById('sdDroppedColsTbody');
                    if (droppedTbody) {
                        if (sd.dropped_columns && sd.dropped_columns.length > 0) {
                            droppedTbody.innerHTML = sd.dropped_columns.map(dc => `
                                <tr>
                                    <td class="fw-semibold text-danger">${escapeHtml(dc.column)}</td>
                                    <td><span class="badge bg-secondary-subtle text-secondary">${escapeHtml(dc.type)}</span></td>
                                    <td class="small text-muted">${escapeHtml(dc.reason)}</td>
                                    <td><span class="badge bg-danger-subtle text-danger border border-danger-subtle">${escapeHtml(dc.status)}</span></td>
                                </tr>
                            `).join('');
                        } else {
                            droppedTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted small py-3"><i class="bi bi-check-circle-fill text-success me-1"></i> No columns were dropped. All features were retained.</td></tr>';
                        }
                    }

                    const impTbody = document.getElementById('sdImputationTbody');
                    if (impTbody) {
                        if (sd.imputation_details && sd.imputation_details.length > 0) {
                            impTbody.innerHTML = sd.imputation_details.map(imp => `
                                <tr>
                                    <td class="fw-semibold text-primary">${escapeHtml(imp.column)}</td>
                                    <td class="text-danger fw-bold">${Number(imp.missing_count || 0).toLocaleString()}</td>
                                    <td><span class="badge bg-warning-subtle text-warning-emphasis">${imp.missing_percentage}%</span></td>
                                    <td class="small">${escapeHtml(imp.strategy)}</td>
                                    <td class="small fw-semibold text-dark">${escapeHtml(imp.replacement_value)}</td>
                                    <td><span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check2 me-1"></i>${escapeHtml(imp.status)}</span></td>
                                </tr>
                            `).join('');
                        } else {
                            impTbody.innerHTML = '<tr><td colspan="6" class="text-center text-success small py-3"><i class="bi bi-check-circle-fill me-1"></i> 0 missing values detected in dataset. No imputation needed.</td></tr>';
                        }
                    }

                    // 4. AI Insights & Strategic Recommendations
                    const findingsEl = document.getElementById('sdAiFindingsList');
                    if (findingsEl) {
                        const findings = sd.ai_explanation?.key_findings || sd.ai_explanation?.patterns || [];
                        if (findings.length > 0) {
                            findingsEl.innerHTML = `<ul class="mb-0 ps-3">${findings.map(f => `<li class="mb-1">${escapeHtml(f)}</li>`).join('')}</ul>`;
                        } else {
                            findingsEl.innerHTML = '<span class="text-muted">Dataset features demonstrate high integrity with consistent distributions across categories.</span>';
                        }
                    }

                    const recEl = document.getElementById('sdAiRecommendationsList');
                    if (recEl) {
                        const recs = sd.ai_explanation?.recommendations || [];
                        if (recs.length > 0) {
                            recEl.innerHTML = `<ul class="mb-0 ps-3">${recs.map(r => `<li class="mb-1">${escapeHtml(r)}</li>`).join('')}</ul>`;
                        } else {
                            recEl.innerHTML = '<span class="text-muted">Maintain current operational tracking and monitor high-volume categorical segments.</span>';
                        }
                    }

                    // 5. Dataset Q&A / FAQs (5+)
                    const qaAccordion = document.getElementById('sdQaAccordion');
                    if (qaAccordion) {
                        if (sd.dataset_qa && sd.dataset_qa.length > 0) {
                            qaAccordion.innerHTML = sd.dataset_qa.map((qa, idx) => `
                                <div class="accordion-item mb-2 border rounded overflow-hidden shadow-sm">
                                    <h2 class="accordion-header" id="vwSdQaHead${idx}">
                                        <button class="accordion-button ${idx === 0 ? '' : 'collapsed'} py-2 px-3 fw-semibold small bg-body-tertiary" type="button" data-bs-toggle="collapse" data-bs-target="#vwSdQaCollapse${idx}" aria-expanded="${idx === 0 ? 'true' : 'false'}" aria-controls="vwSdQaCollapse${idx}">
                                            <i class="bi ${qa.icon || 'bi-patch-question-fill'} text-primary me-2"></i>
                                            <span class="badge bg-secondary-subtle text-secondary me-2 extra-small">${escapeHtml(qa.category || 'Analysis')}</span>
                                            <span>${escapeHtml(qa.question)}</span>
                                        </button>
                                    </h2>
                                    <div id="vwSdQaCollapse${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" aria-labelledby="vwSdQaHead${idx}" data-bs-parent="#sdQaAccordion">
                                        <div class="accordion-body small bg-white text-secondary py-3 px-3 border-top" style="line-height: 1.6;">
                                            ${qa.answer}
                                        </div>
                                    </div>
                                </div>
                            `).join('');
                        } else {
                            qaAccordion.innerHTML = '<div class="alert alert-info small mb-0">Dataset Q&A analysis available.</div>';
                        }
                    }

                    // 6. Preview Table
                    const prevContainer = document.getElementById('sharedDetailPreviewContainer');
                    if (prevContainer) {
                        prevContainer.innerHTML = sd.preview_html || '<div class="p-3 text-muted">No preview table available.</div>';
                    }

                    // 7. Python Pipeline Code (Read-Only)
                    const codeContainer = document.getElementById('sdPipelineCodeContainer');
                    if (codeContainer) {
                        codeContainer.textContent = sd.pipeline_code || '# Auto-generated pipeline code is available for this shared dataset.';
                    }

                    // Reset to overview tab
                    const overviewTabBtn = document.getElementById('tab-sd-overview-btn');
                    if (overviewTabBtn) {
                        const tabTrigger = new bootstrap.Tab(overviewTabBtn);
                        tabTrigger.show();
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

    // Bind Copy Pipeline Code button in Shared Dashboard modal
    const copySdCodeBtn = document.getElementById('btnCopySdCodeSnippet');
    if (copySdCodeBtn) {
        copySdCodeBtn.addEventListener('click', function() {
            const codeEl = document.getElementById('sdPipelineCodeContainer');
            if (codeEl && codeEl.textContent) {
                navigator.clipboard.writeText(codeEl.textContent)
                    .then(() => {
                        showToast("Python pipeline code copied to clipboard!", "success");
                    })
                    .catch(() => {
                        showToast("Unable to copy code to clipboard.", "warning");
                    });
            }
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