/* ==========================================================================
   DataNova — Admin Dashboard Interactive Controller
   Handles User Management, Role Editing, Log Exports, Plotly Analytics,
   System Activity refresh, Sidebar/Theme controls, and Quick Action buttons.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Admin Controller Initialized.");

    // --- Helper UI Functions ---
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
                return true;
            }
        }
        return false;
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
            setTimeout(() => {
                if (toastEl && toastEl.parentNode) {
                    toastEl.remove();
                }
            }, 4000);
        }
    }
    window.showToast = showToast;

    // --- Quick Action / Header Action Handlers ---
    const actionHandlers = {
        'add-user': () => window.showAddUserModal(),
        'export-log': () => exportSystemLogs(),
        'manage-roles': () => window.showAllUsersModal(),
        'view-datasets': () => window.showAllDatasetsModal(),
        'view-reports': () => window.showViewReportsModal(),
        'system-settings': () => window.showSystemSettingsModal()
    };

    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', function (e) {
            const action = el.getAttribute('data-action');
            const handler = actionHandlers[action];
            if (handler) {
                e.preventDefault();
                handler();
            }
        });
    });

    // --- Sidebar Navigation Links & Direct Anchor Clicks ---
    document.querySelectorAll('.dn-sidebar-scroll .dn-nav-link').forEach(link => {
        link.addEventListener('click', function (e) {
            const page = link.getAttribute('data-page');
            if (page === 'settings') {
                e.preventDefault();
                window.showSystemSettingsModal();
                return;
            }
            if (page === 'shared-dashboards') {
                e.preventDefault();
                window.showSharedDashboardsModal();
                return;
            }

            const href = link.getAttribute('href');
            if (href && href.startsWith('#') && href.length > 1) {
                const targetId = href.substring(1);
                const targetEl = document.getElementById(targetId);
                if (targetEl) {
                    e.preventDefault();
                    smoothScrollToElement(targetEl, link);
                    return;
                }
            }

            const section = link.getAttribute('data-section');
            if (section) {
                e.preventDefault();
                scrollToSection(section);
                return;
            }
        });
    });

    // ScrollSpy observer for admin dashboard
    const adminSectionIds = [
        'adminOverviewSection',
        'adminRolesSection',
        'adminPlatformActivitySection',
        'adminUsersSection',
        'adminDatasetsSection',
        'adminSystemActivitySection',
        'adminApiUsageSection',
        'adminSecuritySection',
        'adminQuickActionsSection'
    ];

    let adminScrollTimeout = null;
    window.addEventListener('scroll', function () {
        if (adminScrollTimeout) return;
        adminScrollTimeout = setTimeout(function () {
            adminScrollTimeout = null;
            const scrollPos = window.pageYOffset + 140;

            let currentSectionId = null;
            for (let i = 0; i < adminSectionIds.length; i++) {
                const el = document.getElementById(adminSectionIds[i]);
                if (el) {
                    const top = el.offsetTop;
                    const height = el.offsetHeight;
                    if (scrollPos >= top && scrollPos < top + height) {
                        currentSectionId = adminSectionIds[i];
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

    // --- Profile / Settings dropdown placeholders ---
    document.querySelectorAll('.dropdown-item[data-page]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            if (page === 'profile') {
                const el = document.getElementById('adminUserProfileModal');
                if (el) bootstrap.Modal.getOrCreateInstance(el).show();
            } else if (page === 'settings') {
                window.showSystemSettingsModal();
            }
        });
    });

    // --- Help button ---
    document.querySelectorAll('[data-action="help"]').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const el = document.getElementById('adminHelpModal');
            if (el) bootstrap.Modal.getOrCreateInstance(el).show();
        });
    });

    // --- Sidebar collapse (mobile) toggle ---
    const appEl = document.querySelector('.dn-app');
    const sidebarToggleBtn = document.querySelector('.dn-sidebar-toggle-btn');
    const sidebarOverlay = document.querySelector('.dn-sidebar-overlay');
    if (sidebarToggleBtn && appEl) {
        sidebarToggleBtn.addEventListener('click', function () {
            appEl.classList.toggle('dn-sidebar-open');
        });
    }
    if (sidebarOverlay && appEl) {
        sidebarOverlay.addEventListener('click', function () {
            appEl.classList.remove('dn-sidebar-open');
        });
    }

    // --- Advanced Topbar Search & Live Filtering Controller ---
    const searchInput = document.getElementById('adminTopbarSearchInput') || document.querySelector('.dn-topbar-search input');
    const searchClearBtn = document.getElementById('adminSearchClearBtn');
    const searchDropdown = document.getElementById('adminSearchDropdown');
    const searchDropdownContent = document.getElementById('adminSearchDropdownContent');
    const searchMatchCount = document.getElementById('adminSearchMatchCount');

    let activeGlobalSearchQuery = '';

    function executeGlobalSearch(query) {
        activeGlobalSearchQuery = (query || '').trim();

        if (searchClearBtn) {
            searchClearBtn.classList.toggle('d-none', !activeGlobalSearchQuery);
        }

        const lowerQuery = activeGlobalSearchQuery.toLowerCase();

        // 1. Filter Recent Users Table
        const userMatches = filterTableWithEmptyState('#adminRecentUsersTable', lowerQuery, 6, 'No matching users found.');

        // 2. Filter Recent Datasets Table
        const datasetMatches = filterTableWithEmptyState('#adminRecentDatasetsTable', lowerQuery, 6, 'No matching datasets found.');

        // 3. Filter System Activity List
        const activityMatches = filterListItems('#adminSystemActivityList li', lowerQuery);

        // 4. Build Live Dropdown Results overlay
        if (!activeGlobalSearchQuery) {
            if (searchDropdown) searchDropdown.classList.add('d-none');
            return;
        }

        let html = '';
        let totalMatches = 0;

        // Categorized Results - Users
        if (userMatches.items.length > 0) {
            totalMatches += userMatches.items.length;
            html += `<div class="dn-search-cat-header"><i class="bi bi-people me-1"></i> Users (${userMatches.items.length})</div>`;
            userMatches.items.forEach(el => {
                const text = el.textContent.replace(/\s+/g, ' ').trim();
                html += `
                    <div class="dn-search-result-item" onclick="showAllUsersModal();">
                        <div><i class="bi bi-person-circle text-primary me-2"></i><span>${highlightMatch(text, activeGlobalSearchQuery)}</span></div>
                        <span class="badge bg-primary-subtle text-primary small">User</span>
                    </div>`;
            });
        }

        // Categorized Results - Datasets
        if (datasetMatches.items.length > 0) {
            totalMatches += datasetMatches.items.length;
            html += `<div class="dn-search-cat-header"><i class="bi bi-database me-1"></i> Datasets (${datasetMatches.items.length})</div>`;
            datasetMatches.items.forEach(el => {
                const text = el.textContent.replace(/\s+/g, ' ').trim();
                html += `
                    <div class="dn-search-result-item" onclick="showAllDatasetsModal();">
                        <div><i class="bi bi-hdd-network text-info me-2"></i><span>${highlightMatch(text, activeGlobalSearchQuery)}</span></div>
                        <span class="badge bg-info-subtle text-info small">Dataset</span>
                    </div>`;
            });
        }

        // Categorized Results - System Activity Logs
        if (activityMatches.length > 0) {
            totalMatches += activityMatches.length;
            html += `<div class="dn-search-cat-header"><i class="bi bi-activity me-1"></i> Logs &amp; Activity (${activityMatches.length})</div>`;
            activityMatches.forEach(el => {
                const text = el.textContent.replace(/\s+/g, ' ').trim();
                html += `
                    <div class="dn-search-result-item" onclick="showAllSystemActivityModal();">
                        <div><i class="bi bi-clock-history text-warning me-2"></i><span>${highlightMatch(text, activeGlobalSearchQuery)}</span></div>
                        <span class="badge bg-warning-subtle text-warning small">Activity Log</span>
                    </div>`;
            });
        }

        if (totalMatches === 0) {
            html = `<div class="p-3 text-center text-secondary small"><i class="bi bi-search me-1 fs-5 d-block mb-1"></i>No matching platform records found for "${escapeHtml(activeGlobalSearchQuery)}"</div>`;
        }

        if (searchMatchCount) searchMatchCount.textContent = `${totalMatches} ${totalMatches === 1 ? 'match' : 'matches'}`;
        if (searchDropdownContent) searchDropdownContent.innerHTML = html;
        if (searchDropdown) searchDropdown.classList.remove('d-none');
    }

    function filterTableWithEmptyState(tableSelector, query, colSpan, emptyMsg) {
        const tbody = document.querySelector(`${tableSelector} tbody`);
        if (!tbody) return { matchedCount: 0, items: [] };

        const rows = Array.from(tbody.querySelectorAll('tr:not(.dn-no-results-row)'));
        const matchedRows = [];

        rows.forEach(row => {
            const text = (row.textContent || '').toLowerCase();
            const match = !query || text.includes(query);
            row.style.display = match ? '' : 'none';
            if (match && query) matchedRows.push(row);
        });

        let existingEmpty = tbody.querySelector('.dn-no-results-row');
        if (query && rows.length > 0 && matchedRows.length === 0) {
            if (!existingEmpty) {
                const emptyRow = document.createElement('tr');
                emptyRow.className = 'dn-no-results-row';
                emptyRow.innerHTML = `<td colspan="${colSpan}" class="text-center p-3 text-secondary small"><i class="bi bi-funnel me-1"></i> ${emptyMsg}</td>`;
                tbody.appendChild(emptyRow);
            }
        } else if (existingEmpty) {
            existingEmpty.remove();
        }

        return { matchedCount: matchedRows.length, items: matchedRows };
    }

    function filterListItems(selector, query) {
        const items = Array.from(document.querySelectorAll(selector));
        const matched = [];
        items.forEach(el => {
            const text = (el.textContent || '').toLowerCase();
            const match = !query || text.includes(query);
            el.style.display = match ? '' : 'none';
            if (match && query) matched.push(el);
        });
        return matched;
    }

    function highlightMatch(text, query) {
        if (!query) return escapeHtml(text);
        const idx = text.toLowerCase().indexOf(query.toLowerCase());
        if (idx === -1) return escapeHtml(text);
        const before = text.substring(0, idx);
        const match = text.substring(idx, idx + query.length);
        const after = text.substring(idx + query.length);
        return `${escapeHtml(before)}<mark class="px-1 py-0 rounded bg-warning text-dark fw-bold">${escapeHtml(match)}</mark>${escapeHtml(after)}`;
    }

    function escapeHtml(str) {
        return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            executeGlobalSearch(e.target.value);
        });

        searchInput.addEventListener('focus', function () {
            if (searchInput.value.trim()) {
                executeGlobalSearch(searchInput.value);
            }
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                searchInput.value = '';
                executeGlobalSearch('');
                searchInput.blur();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const q = searchInput.value.trim();
                if (q) {
                    window.showAllUsersModal();
                    const modalInput = document.getElementById('allUsersModalSearchInput');
                    if (modalInput) {
                        modalInput.value = q;
                        window.filterAllUsersModalTable();
                    }
                }
            }
        });
    }

    if (searchClearBtn) {
        searchClearBtn.addEventListener('click', function () {
            if (searchInput) {
                searchInput.value = '';
                searchInput.focus();
                executeGlobalSearch('');
            }
        });
    }

    document.addEventListener('click', function (e) {
        if (searchDropdown && !e.target.closest('.dn-topbar-search')) {
            searchDropdown.classList.add('d-none');
        }
    });

    function renderAdminAnalytics(data) {
        if (!data) return;

        // KPI Card Values
        if (data.total_users !== undefined && document.getElementById('kpiTotalUsers')) {
            document.getElementById('kpiTotalUsers').textContent = data.total_users.toLocaleString();
        }
        if (data.active_users !== undefined && document.getElementById('kpiActiveUsers')) {
            document.getElementById('kpiActiveUsers').textContent = data.active_users.toLocaleString();
        }
        if (data.total_datasets !== undefined && document.getElementById('kpiTotalDatasets')) {
            document.getElementById('kpiTotalDatasets').textContent = data.total_datasets.toLocaleString();
        }
        if (data.total_reports !== undefined && document.getElementById('kpiTotalReports')) {
            document.getElementById('kpiTotalReports').textContent = data.total_reports.toLocaleString();
        }
        if (data.dashboards_count !== undefined && document.getElementById('kpiDashboardsCount')) {
            document.getElementById('kpiDashboardsCount').textContent = data.dashboards_count.toLocaleString();
        }
        if (document.getElementById('kpiStoragePct')) {
            const formattedStorage = data.storage_used_formatted || (data.storage_used_gb !== undefined ? `${data.storage_used_gb} GB` : '0 MB');
            document.getElementById('kpiStoragePct').textContent = formattedStorage;
        }
        if (document.getElementById('kpiStorageGb')) {
            const countDs = data.total_datasets !== undefined ? data.total_datasets : 0;
            document.getElementById('kpiStorageGb').innerHTML = `<i class="bi bi-database"></i> ${countDs} dataset${countDs === 1 ? '' : 's'}`;
        }

        // Render Plotly Charts using actual counts if available
        const roleData = data.users_by_role_counts || data.users_by_role;
        if (roleData) renderRoleDonutChart(roleData);
        else renderDefaultRoleDonutChart();

        if (data.weekly_activity) renderUserActivityChart(data.weekly_activity);
        else renderDefaultUserActivityChart();

        // Dynamic Recent Users Table
        if (data.recent_users && Array.isArray(data.recent_users)) {
            const tbody = document.querySelector('#adminRecentUsersTable tbody');
            if (tbody) {
                if (data.recent_users.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4">No recent users found.</td></tr>';
                } else {
                    tbody.innerHTML = data.recent_users.map(r_user => {
                        const isAct = (r_user.status || 'active').toLowerCase() === 'active';
                        const statusBadge = isAct
                            ? '<span class="dn-badge-status ok"><i class="bi bi-circle-fill" style="font-size:6px"></i> Active</span>'
                            : '<span class="dn-badge-status danger"><i class="bi bi-circle-fill" style="font-size:6px"></i> Inactive</span>';

                        const toggleBtn = isAct
                            ? `<button class="btn btn-sm btn-outline-danger py-0 px-2 small dn-btn-toggle-status" data-user-id="${r_user.id}" data-status="inactive" title="Deactivate User Account"><i class="bi bi-person-x"></i> Make Inactive</button>`
                            : `<button class="btn btn-sm btn-outline-success py-0 px-2 small dn-btn-toggle-status" data-user-id="${r_user.id}" data-status="active" title="Activate User Account"><i class="bi bi-person-check"></i> Make Active</button>`;

                        const init1 = (r_user.first_name || 'U')[0].toUpperCase();
                        const init2 = (r_user.last_name || '')[0] ? r_user.last_name[0].toUpperCase() : '';
                        const roleCap = (r_user.role || 'viewer').charAt(0).toUpperCase() + (r_user.role || 'viewer').slice(1);
                        const joinedDate = r_user.created_at ? (typeof r_user.created_at === 'string' ? r_user.created_at.substring(0, 10) : 'Active') : 'N/A';

                        return `
                            <tr>
                                <td><div class="dn-cell-user"><span class="dn-avatar-sm">${init1}${init2}</span> ${r_user.first_name || ''} ${r_user.last_name || ''}</div></td>
                                <td>${r_user.email || ''}</td>
                                <td><span class="dn-badge-role">${roleCap}</span></td>
                                <td>${statusBadge}</td>
                                <td>${joinedDate}</td>
                                <td>
                                    <div class="d-flex gap-1 align-items-center">
                                        ${toggleBtn}
                                        <button class="dn-table-action dn-btn-edit-role" data-user-id="${r_user.id}" data-role="${r_user.role}" title="Edit Role"><i class="bi bi-pencil"></i></button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('');
                }
            }
        }

        // System Activity List
        if (data.system_activity && Array.isArray(data.system_activity)) {
            const listEl = document.getElementById('adminSystemActivityList');
            if (listEl) {
                listEl.innerHTML = data.system_activity.map(act => `
                    <li><span class="dn-insight-dot" style="background:${act.color || 'var(--dn-primary)'}"></span><strong>${act.user_name}</strong> ${act.action} <span class="text-secondary ms-auto small">${act.time_ago}</span></li>
                `).join('');
            }
        }

        // Security Status & Policies
        if (data.security_details) {
            updateSecurityUI(data.security_details);
        } else if (data.security_alerts && Array.isArray(data.security_alerts)) {
            const container = document.getElementById('adminSecurityAlertsContainer');
            if (container) {
                container.innerHTML = data.security_alerts.map(alert => `
                    <div class="dn-alert dn-alert-${alert.type}"><i class="bi ${alert.icon}"></i> ${alert.text}</div>
                `).join('');
            }
        }

        // Topbar Notifications Dropdown
        if (data.notifications && Array.isArray(data.notifications)) {
            const dropdownMenu = document.querySelector('.dn-dropdown-menu');
            if (dropdownMenu) {
                const headerHtml = `<div class="dn-dropdown-header-custom"><strong>Notifications</strong></div>`;
                const notifItems = data.notifications.map(notif => `
                    <div class="dn-notif-item">
                        <div class="dn-notif-icon"><i class="bi ${notif.icon}"></i></div>
                        <div>
                            <div class="dn-notif-text">${notif.text}</div>
                            <div class="dn-notif-time">${notif.time}</div>
                        </div>
                    </div>
                `).join('');
                dropdownMenu.innerHTML = headerHtml + notifItems;
            }
        }

        if (activeGlobalSearchQuery) {
            executeGlobalSearch(activeGlobalSearchQuery);
        }
    }

    window.renderAdminAnalytics = renderAdminAnalytics;

    const plotlyChartConfig = {
        responsive: true,
        displayModeBar: false,
        displaylogo: false
    };

    function renderRoleDonutChart(roleData) {
        const container = document.getElementById('adminRoleDonutChart');
        if (!container || typeof Plotly === 'undefined') return;

        const labels = ['Analyst', 'Manager', 'Viewer', 'Admin'];
        const values = [
            Number(roleData.analyst || 0),
            Number(roleData.manager || 0),
            Number(roleData.viewer || 0),
            Number(roleData.admin || 0)
        ];

        const sum = values.reduce((a, b) => a + b, 0);
        const displayValues = sum > 0 ? values : [1, 1, 1, 1];
        const displayLabels = sum > 0 ? labels : ['Analyst', 'Manager', 'Viewer', 'Admin'];

        const trace = {
            labels: displayLabels,
            values: displayValues,
            type: 'pie',
            hole: 0.6,
            marker: {
                colors: ['#4F46E5', '#7C3AED', '#06B6D4', '#64748B']
            },
            textinfo: sum > 0 ? 'percent' : 'label',
            hovertemplate: sum > 0 ? '<b>%{label}</b>: %{value} users (%{percent})<extra></extra>' : '<b>%{label}</b> (Baseline)<extra></extra>'
        };

        const layout = {
            margin: { t: 10, r: 10, l: 10, b: 10 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            showlegend: true,
            legend: { orientation: 'h', x: 0, y: -0.1, font: { color: '#94A3B8', size: 10 } },
            autosize: true
        };

        try {
            Plotly.newPlot(container, [trace], layout, plotlyChartConfig);
        } catch (e) {
            console.error("Error rendering role donut chart:", e);
        }
    }

    let currentPlatformActivityData = null;
    let currentPlatformActivityView = 'all';

    function renderUserActivityChart(activityData, view = null) {
        const container = document.getElementById('adminUserActivityChart');
        if (!container || typeof Plotly === 'undefined') return;

        if (activityData) {
            currentPlatformActivityData = activityData;
        } else {
            activityData = currentPlatformActivityData;
        }
        if (view) {
            currentPlatformActivityView = view;
        } else {
            view = currentPlatformActivityView || 'all';
        }

        const labels = (activityData && activityData.labels && activityData.labels.length)
            ? activityData.labels
            : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

        const fullDates = (activityData && activityData.full_dates && activityData.full_dates.length)
            ? activityData.full_dates
            : labels.map(l => `${l} (Last 7 Days)`);

        const actions = (activityData && (activityData.actions || activityData.active) && (activityData.actions || activityData.active).length)
            ? (activityData.actions || activityData.active).map(Number)
            : [0, 0, 0, 0, 0, 0, 0];

        const signups = (activityData && activityData.signups && activityData.signups.length)
            ? activityData.signups.map(Number)
            : [0, 0, 0, 0, 0, 0, 0];

        const isDark = document.body.classList.contains('theme-dark') ||
            document.documentElement.getAttribute('data-bs-theme') === 'dark';
        const textColor = isDark ? '#94A3B8' : '#64748B';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.07)' : 'rgba(0, 0, 0, 0.06)';

        // Compute max for dynamic clean whole-integer ticks
        const maxVal = Math.max(...actions, ...signups, 1);
        const dtickVal = maxVal <= 5 ? 1 : (maxVal <= 20 ? 2 : (maxVal <= 50 ? 5 : Math.ceil(maxVal / 5)));

        const traces = [];

        // Trace 1: Platform Actions (API requests, dataset uploads, queries)
        const traceActions = {
            x: labels,
            y: actions,
            customdata: fullDates,
            name: 'Platform Actions & Queries',
            type: 'scatter',
            mode: 'lines+markers',
            line: {
                shape: 'spline',
                color: '#6366F1',
                width: 3.5,
                smoothing: 1.2
            },
            fill: 'tozeroy',
            fillcolor: isDark ? 'rgba(99, 102, 241, 0.22)' : 'rgba(99, 102, 241, 0.12)',
            marker: {
                size: 7,
                color: '#4F46E5',
                symbol: 'circle',
                line: { color: isDark ? '#1E1B4B' : '#FFFFFF', width: 2 }
            },
            hovertemplate: '<b>%{customdata}</b><br><span style="color:#6366F1;">●</span> Platform Actions: <b>%{y}</b><extra></extra>'
        };

        // Trace 2: New User Registrations
        const traceSignups = {
            x: labels,
            y: signups,
            customdata: fullDates,
            name: 'New User Signups',
            type: 'scatter',
            mode: 'lines+markers',
            line: {
                shape: 'spline',
                color: '#10B981',
                width: 3,
                smoothing: 1.2
            },
            fill: 'tozeroy',
            fillcolor: isDark ? 'rgba(16, 185, 129, 0.18)' : 'rgba(16, 185, 129, 0.10)',
            marker: {
                size: 7,
                color: '#059669',
                symbol: 'diamond',
                line: { color: isDark ? '#064E3B' : '#FFFFFF', width: 2 }
            },
            hovertemplate: '<b>%{customdata}</b><br><span style="color:#10B981;">●</span> New Signups: <b>%{y}</b><extra></extra>'
        };

        if (view === 'actions') {
            traces.push(traceActions);
        } else if (view === 'signups') {
            traces.push(traceSignups);
        } else {
            traces.push(traceActions);
            traces.push(traceSignups);
        }

        const layout = {
            margin: { t: 15, r: 15, l: 35, b: 30 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            hovermode: 'x unified',
            hoverlabel: {
                bgcolor: isDark ? '#1E293B' : '#FFFFFF',
                bordercolor: isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)',
                font: { family: 'inherit', size: 12, color: isDark ? '#F1F5F9' : '#0F172A' }
            },
            xaxis: {
                showgrid: false,
                color: textColor,
                tickfont: { size: 11, color: textColor }
            },
            yaxis: {
                showgrid: true,
                gridcolor: gridColor,
                color: textColor,
                rangemode: 'tozero',
                dtick: dtickVal,
                tickformat: 'd',
                tickfont: { size: 11, color: textColor }
            },
            legend: {
                orientation: 'h',
                x: 0,
                y: 1.22,
                font: { color: textColor, size: 11 }
            },
            autosize: true
        };

        const config = {
            responsive: true,
            displayModeBar: false,
            displaylogo: false
        };

        try {
            Plotly.newPlot(container, traces, layout, config);
        } catch (e) {
            console.error("Error rendering user activity chart:", e);
        }
    }

    // Activity Filter Button Toggle Setup
    const filterGroup = document.getElementById('activityChartFilterGroup');
    if (filterGroup) {
        filterGroup.addEventListener('click', function (e) {
            const btn = e.target.closest('button[data-view]');
            if (!btn) return;
            filterGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const view = btn.getAttribute('data-view');
            renderUserActivityChart(null, view);
        });
    }

    function renderDefaultRoleDonutChart() {
        renderRoleDonutChart({ analyst: 1, manager: 1, viewer: 1, admin: 1 });
    }
    function renderDefaultUserActivityChart() {
        renderUserActivityChart({ labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], actions: [0, 0, 0, 0, 0, 0, 0], signups: [0, 0, 0, 0, 0, 0, 0] });
    }

    // --- Dynamic Admin Analytics Auto-Fetch (Executed after all functions are ready) ---
    if (window.INITIAL_ADMIN_KPI) {
        renderAdminAnalytics(window.INITIAL_ADMIN_KPI);
    }

    fetch('/api/admin/dashboard_data')
        .then(res => res.json())
        .then(resData => {
            if (resData.success && resData.data) {
                renderAdminAnalytics(resData.data);
            }
        })
        .catch(err => {
            console.log("Admin Analytics refresh warning: ", err);
        });

    // Window Resize Handler to auto-fit charts
    window.addEventListener('resize', function () {
        const donut = document.getElementById('adminRoleDonutChart');
        if (donut && typeof Plotly !== 'undefined') {
            try { Plotly.Plots.resize(donut); } catch (e) { }
        }
        const activity = document.getElementById('adminUserActivityChart');
        if (activity && typeof Plotly !== 'undefined') {
            try { Plotly.Plots.resize(activity); } catch (e) { }
        }
    });

    // --- User Management Action Buttons (delegated) ---
    document.addEventListener('click', function (e) {
        const toggleStatusBtn = e.target.closest('.dn-btn-toggle-status');
        if (toggleStatusBtn) {
            e.preventDefault();
            const uId = toggleStatusBtn.getAttribute('data-user-id');
            const st = toggleStatusBtn.getAttribute('data-status');
            if (uId && st && window.toggleUserStatus) {
                window.toggleUserStatus(uId, st);
            }
            return;
        }

        const editRoleBtn = e.target.closest('.dn-btn-edit-role');
        if (editRoleBtn) {
            e.preventDefault();
            const uId = editRoleBtn.getAttribute('data-user-id');
            const r = editRoleBtn.getAttribute('data-role');
            if (uId && window.showEditRoleModal) {
                window.showEditRoleModal(uId, r);
            }
        }
    });

    // --- Add User Modal Logic & Form Submission Workflow ---
    window.showAddUserModal = function () {
        const modalEl = document.getElementById('dnAddUserModal');
        if (!modalEl) {
            showToast("User creation modal element not found.", "danger");
            return;
        }

        const errorAlert = document.getElementById('addUserErrorAlert');
        if (errorAlert) {
            errorAlert.classList.add('d-none');
            errorAlert.textContent = '';
        }

        const form = document.getElementById('dnAddUserForm');
        if (form) form.classList.remove('was-validated');

        const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
        modalInstance.show();
    };

    // Attach Add User Form submit listener
    const addUserForm = document.getElementById('dnAddUserForm');
    if (addUserForm) {
        addUserForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const firstNameEl = document.getElementById('addUserFirstName');
            const lastNameEl = document.getElementById('addUserLastName');
            const emailEl = document.getElementById('addUserEmail');
            const orgEl = document.getElementById('addUserOrganization');
            const phoneEl = document.getElementById('addUserPhone');
            const passwordEl = document.getElementById('addUserPassword');
            const roleEl = document.getElementById('addUserRole');
            const errorAlert = document.getElementById('addUserErrorAlert');

            const firstName = (firstNameEl ? firstNameEl.value : '').trim();
            const lastName = (lastNameEl ? lastNameEl.value : '').trim();
            const email = (emailEl ? emailEl.value : '').trim();
            const organization = (orgEl ? orgEl.value : '').trim() || 'General';
            const phone = (phoneEl ? phoneEl.value : '').trim();
            const password = passwordEl ? passwordEl.value : '';
            const role = roleEl ? roleEl.value : 'viewer';

            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!firstName || !lastName) {
                showModalError(errorAlert, "First and last name are required.");
                return;
            }
            if (!email || !emailRegex.test(email)) {
                showModalError(errorAlert, "Please provide a valid email address.");
                return;
            }
            if (!organization) {
                showModalError(errorAlert, "Organization / Company name is required.");
                return;
            }
            if (!password || password.length < 6) {
                showModalError(errorAlert, "Password must be at least 6 characters long.");
                return;
            }

            if (errorAlert) errorAlert.classList.add('d-none');

            // UI Loading state
            const btnSubmit = document.getElementById('btnSubmitAddUser');
            const spinner = document.getElementById('addUserSpinner');
            const checkIcon = document.getElementById('addUserCheckIcon');

            if (btnSubmit) btnSubmit.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (checkIcon) checkIcon.classList.add('d-none');

            const payload = {
                first_name: firstName,
                last_name: lastName,
                email: email,
                organization: organization,
                phone: phone,
                password: password,
                role: role
            };

            fetch('/api/admin/create_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
                .then(res => res.json().then(data => ({ status: res.status, data: data })))
                .then(({ status, data }) => {
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');

                    if (data.success) {
                        const modalEl = document.getElementById('dnAddUserModal');
                        const modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) modalInstance.hide();

                        showToast(data.message || `User ${firstName} created successfully.`, "success");
                        addUserForm.reset();

                        if (document.getElementById('allUsersModalTableBody')) {
                            window.loadAllUsersModalData();
                        }

                        fetch('/api/admin/dashboard_data')
                            .then(r => r.json())
                            .then(d => {
                                if (d.success && d.data && window.renderAdminAnalytics) {
                                    window.renderAdminAnalytics(d.data);
                                }
                            });
                    } else {
                        showModalError(errorAlert, data.message || "Failed to create user account.");
                    }
                })
                .catch(err => {
                    console.error("Create user fetch error:", err);
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');
                    showModalError(errorAlert, "Server connection error while creating user.");
                });
        });
    }

    function showModalError(alertEl, msg) {
        if (alertEl) {
            alertEl.textContent = msg;
            alertEl.classList.remove('d-none');
        } else {
            showToast(msg, "danger");
        }
    }

    // --- Log Export Handler ---
    function exportSystemLogs(format = 'excel') {
        showToast(`Generating System Audit Logs (${format.toUpperCase()})...`, "info");
        window.location.href = `/api/admin/export_logs?format=${encodeURIComponent(format)}`;
    }
});

// --- Global Chart Zoom Reset Helpers ---
window.resetRoleChartZoom = function () {
    const el = document.getElementById('adminRoleDonutChart');
    if (el && typeof Plotly !== 'undefined') {
        try {
            Plotly.relayout(el, { 'xaxis.autorange': true, 'yaxis.autorange': true });
        } catch (e) {
            console.log("Role chart zoom reset:", e);
        }
    }
};

window.resetActivityChartZoom = function () {
    const el = document.getElementById('adminUserActivityChart');
    if (el && typeof Plotly !== 'undefined') {
        try {
            Plotly.relayout(el, { 'xaxis.autorange': true, 'yaxis.autorange': true });
        } catch (e) {
            console.log("Activity chart zoom reset:", e);
        }
    }
};

// --- See All Users Modal & User Management Handlers ---
window._currentAdminOrgFilter = 'all';
window._allUsersCache = [];

window.showAllUsersModal = function () {
    const modalEl = document.getElementById('allUsersModal');
    if (!modalEl) return;
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
    window.loadAllUsersModalData(window._currentAdminOrgFilter || 'all');
};

window.handleAdminOrgFilterChange = function (selectedOrg) {
    window._currentAdminOrgFilter = selectedOrg || 'all';
    window.loadAllUsersModalData(window._currentAdminOrgFilter);
};

window.loadAllUsersModalData = function (selectedOrg) {
    const tbody = document.getElementById('allUsersModalTableBody');
    if (!tbody) return;

    const org = selectedOrg !== undefined ? selectedOrg : (window._currentAdminOrgFilter || 'all');
    window._currentAdminOrgFilter = org;

    tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Loading users...</div></td></tr>';

    const url = (org && org !== 'all')
        ? `/api/admin/users?organization=${encodeURIComponent(org)}`
        : '/api/admin/users';

    fetch(url)
        .then(res => res.json())
        .then(data => {
            if (data.success && Array.isArray(data.users)) {
                window._allUsersCache = data.users;

                // Populate Organization select and pills if available
                if (Array.isArray(data.organizations)) {
                    window.renderAdminOrgFilterControls(data.organizations, org);
                }

                window.renderAllUsersModalTable(data.users);
            } else {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4 text-danger">Failed to load users list.</td></tr>';
            }
        })
        .catch(err => {
            console.error("Error loading all users:", err);
            tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4 text-danger">Network error loading users.</td></tr>';
        });
};

window.renderAdminOrgFilterControls = function (orgList, currentOrg) {
    const selectEl = document.getElementById('allUsersOrgFilterSelect');
    const pillsEl = document.getElementById('allUsersOrgPills');

    let totalCount = 0;
    orgList.forEach(o => totalCount += (o.count || 0));

    if (selectEl) {
        let selectHtml = `<option value="all" ${currentOrg === 'all' ? 'selected' : ''}>All Organizations (${totalCount})</option>`;
        orgList.forEach(o => {
            const orgName = o.organization || 'General';
            const sel = (currentOrg.toLowerCase() === orgName.toLowerCase()) ? 'selected' : '';
            selectHtml += `<option value="${escapeHtml(orgName)}" ${sel}>${escapeHtml(orgName)} (${o.count})</option>`;
        });
        selectEl.innerHTML = selectHtml;
    }

    if (pillsEl) {
        let pillsHtml = `
            <button class="btn btn-sm ${currentOrg === 'all' ? 'btn-primary' : 'btn-outline-secondary'} py-0 px-2 rounded-pill small" 
                    onclick="handleAdminOrgFilterChange('all'); return false;">
                All <span class="badge ${currentOrg === 'all' ? 'bg-light text-dark' : 'bg-secondary text-white'} ms-1">${totalCount}</span>
            </button>
        `;
        orgList.forEach(o => {
            const orgName = o.organization || 'General';
            const isActive = currentOrg.toLowerCase() === orgName.toLowerCase();
            pillsHtml += `
                <button class="btn btn-sm ${isActive ? 'btn-primary' : 'btn-outline-secondary'} py-0 px-2 rounded-pill small" 
                        onclick="handleAdminOrgFilterChange('${escapeHtml(orgName)}'); return false;">
                    <i class="bi bi-building me-1"></i>${escapeHtml(orgName)} <span class="badge ${isActive ? 'bg-light text-dark' : 'bg-secondary text-white'} ms-1">${o.count}</span>
                </button>
            `;
        });
        pillsEl.innerHTML = pillsHtml;
    }
};

window.renderAllUsersModalTable = function (users) {
    const tbody = document.getElementById('allUsersModalTableBody');
    if (!tbody) return;

    let activeCnt = 0;
    let inactiveCnt = 0;

    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4 text-muted">No users found for this organization / filter.</td></tr>';
        const actEl = document.getElementById('modalActiveUsersCount');
        const inactEl = document.getElementById('modalInactiveUsersCount');
        if (actEl) actEl.textContent = `Active: 0`;
        if (inactEl) inactEl.textContent = `Inactive: 0`;
        return;
    }

    tbody.innerHTML = users.map(u => {
        const isAct = (u.status || 'active').toLowerCase() === 'active';
        if (isAct) activeCnt++; else inactiveCnt++;

        const init1 = (u.first_name || 'U')[0].toUpperCase();
        const init2 = (u.last_name || '')[0] ? (u.last_name[0]).toUpperCase() : '';
        const roleCap = (u.role || 'viewer').charAt(0).toUpperCase() + (u.role || 'viewer').slice(1);
        const orgName = u.organization || 'General';
        const phoneDisplay = u.phone ? `<span class="text-secondary small"><i class="bi bi-telephone me-1"></i>${escapeHtml(u.phone)}</span>` : '<span class="text-muted small">--</span>';

        const statusBadge = isAct
            ? '<span class="dn-badge-status ok"><i class="bi bi-circle-fill" style="font-size:6px"></i> Active</span>'
            : '<span class="dn-badge-status danger"><i class="bi bi-circle-fill" style="font-size:6px"></i> Inactive</span>';

        const toggleBtn = isAct
            ? `<button class="btn btn-sm btn-outline-danger py-1 px-2 small" onclick="toggleUserStatus(${u.id}, 'inactive'); return false;" title="Deactivate User Account"><i class="bi bi-person-x"></i></button>`
            : `<button class="btn btn-sm btn-outline-success py-1 px-2 small" onclick="toggleUserStatus(${u.id}, 'active'); return false;" title="Activate User Account"><i class="bi bi-person-check"></i></button>`;

        return `
            <tr>
                <td>
                    <div class="dn-cell-user">
                        <span class="dn-avatar-sm">${init1}${init2}</span> 
                        <div>
                            <strong class="d-block">${escapeHtml(u.first_name || '')} ${escapeHtml(u.last_name || '')}</strong>
                            <small class="text-secondary">ID: #${u.id}</small>
                        </div>
                    </div>
                </td>
                <td><span class="small">${escapeHtml(u.email)}</span></td>
                <td><span class="badge bg-secondary-subtle text-body border px-2 py-1"><i class="bi bi-building me-1 text-primary"></i>${escapeHtml(orgName)}</span></td>
                <td>${phoneDisplay}</td>
                <td><span class="dn-badge-role">${roleCap}</span></td>
                <td>${statusBadge}</td>
                <td><span class="small text-secondary">${u.created_at || 'N/A'}</span></td>
                <td class="text-end">
                    <div class="d-flex gap-1 justify-content-end align-items-center">
                        ${toggleBtn}
                        <button class="btn btn-sm btn-outline-primary py-1 px-2" title="Edit Profile & Role" onclick="showAdminEditUserProfileModalById(${u.id}); return false;"><i class="bi bi-pencil-square"></i></button>
                        <button class="btn btn-sm btn-outline-danger py-1 px-2" title="Delete User" onclick="deleteUserAccount(${u.id}); return false;"><i class="bi bi-trash"></i></button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    const actEl = document.getElementById('modalActiveUsersCount');
    const inactEl = document.getElementById('modalInactiveUsersCount');
    if (actEl) actEl.textContent = `Active: ${activeCnt}`;
    if (inactEl) inactEl.textContent = `Inactive: ${inactiveCnt}`;
};

window.filterAllUsersModalTable = function () {
    const input = document.getElementById('allUsersModalSearchInput');
    if (!input) return;
    const query = input.value.trim().toLowerCase();
    const rows = document.querySelectorAll('#allUsersModalTableBody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = (!query || text.includes(query)) ? '' : 'none';
    });
};

window.toggleUserStatus = function (userId, newStatus) {
    if (!userId) return;
    const actionText = newStatus === 'inactive' ? 'deactivate' : 'activate';
    if (!confirm(`Are you sure you want to ${actionText} this user account?`)) return;

    fetch('/api/admin/update_user_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, status: newStatus })
    })
        .then(res => res.json())
        .then(res => {
            const toastFn = window.showToast || function (m) { console.log(m); };
            if (res.success) {
                toastFn(res.message || `User status updated to ${newStatus}.`, "success");

                if (document.getElementById('allUsersModalTableBody')) {
                    window.loadAllUsersModalData(window._currentAdminOrgFilter);
                }

                fetch('/api/admin/dashboard_data')
                    .then(r => r.json())
                    .then(d => {
                        if (d.success && d.data && window.renderAdminAnalytics) {
                            window.renderAdminAnalytics(d.data);
                        }
                    });
            } else {
                toastFn(res.message || "Failed to update user status.", "danger");
            }
        })
        .catch(err => {
            console.error("Error updating user status:", err);
            const toastFn = window.showToast || function (m) { console.log(m); };
            toastFn("Server connection error updating user status.", "danger");
        });
};

// --- Admin Edit User Profile & Role Modal Handling ---
window.showAdminEditUserProfileModalById = function (userId) {
    const user = (window._allUsersCache || []).find(u => u.id === userId);
    if (!user) {
        window.showToast("User details not found in cache. Reloading...", "warning");
        window.loadAllUsersModalData();
        return;
    }
    window.showAdminEditUserProfileModal(user);
};

window.showAdminEditUserProfileModal = function (user) {
    const modalEl = document.getElementById('dnAdminEditUserProfileModal');
    if (!modalEl) {
        window.showToast("Admin edit user modal element not found.", "danger");
        return;
    }

    const errorAlert = document.getElementById('adminEditErrorAlert');
    if (errorAlert) {
        errorAlert.classList.add('d-none');
        errorAlert.textContent = '';
    }

    // Populate inputs
    const idEl = document.getElementById('adminEditUserId');
    const fnEl = document.getElementById('adminEditFirstName');
    const lnEl = document.getElementById('adminEditLastName');
    const emEl = document.getElementById('adminEditEmail');
    const orgEl = document.getElementById('adminEditOrganization');
    const phEl = document.getElementById('adminEditPhone');
    const roleEl = document.getElementById('adminEditRole');
    const statusEl = document.getElementById('adminEditStatus');

    if (idEl) idEl.value = user.id || '';
    if (fnEl) fnEl.value = user.first_name || '';
    if (lnEl) lnEl.value = user.last_name || '';
    if (emEl) emEl.value = user.email || '';
    if (orgEl) orgEl.value = user.organization || 'General';
    if (phEl) phEl.value = user.phone || '';
    if (roleEl) roleEl.value = (user.role || 'viewer').toLowerCase();
    if (statusEl) statusEl.value = (user.status || 'active').toLowerCase();

    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
};

// Helper HTML escaper
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Attach Admin Edit User Form & Profile Self-Edit Form submit listeners
document.addEventListener('DOMContentLoaded', function () {
    // 1. Admin Edit User Form
    const adminEditForm = document.getElementById('dnAdminEditUserForm');
    if (adminEditForm) {
        adminEditForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const uid = document.getElementById('adminEditUserId').value;
            const firstName = (document.getElementById('adminEditFirstName').value || '').trim();
            const lastName = (document.getElementById('adminEditLastName').value || '').trim();
            const email = (document.getElementById('adminEditEmail').value || '').trim();
            const organization = (document.getElementById('adminEditOrganization').value || '').trim();
            const phone = (document.getElementById('adminEditPhone').value || '').trim();
            const role = document.getElementById('adminEditRole').value;
            const status = document.getElementById('adminEditStatus').value;
            const errorAlert = document.getElementById('adminEditErrorAlert');

            const btnSubmit = document.getElementById('btnSubmitAdminEditUser');
            const spinner = document.getElementById('adminEditSpinner');
            const checkIcon = document.getElementById('adminEditCheckIcon');

            if (!firstName) {
                if (errorAlert) {
                    errorAlert.textContent = "First name is required.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }
            if (!email) {
                if (errorAlert) {
                    errorAlert.textContent = "Email address is required.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }
            if (!organization) {
                if (errorAlert) {
                    errorAlert.textContent = "Organization name is required.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }

            if (errorAlert) errorAlert.classList.add('d-none');

            if (btnSubmit) btnSubmit.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (checkIcon) checkIcon.classList.add('d-none');

            fetch('/api/admin/update_user_profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: uid,
                    first_name: firstName,
                    last_name: lastName,
                    email: email,
                    organization: organization,
                    phone: phone,
                    role: role,
                    status: status
                })
            })
                .then(r => r.json())
                .then(res => {
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');

                    const modalEl = document.getElementById('dnAdminEditUserProfileModal');
                    const modalInstance = bootstrap.Modal.getInstance(modalEl);

                    if (res.success) {
                        if (modalInstance) modalInstance.hide();
                        window.showToast(res.message || "User profile updated successfully.", "success");

                        if (document.getElementById('allUsersModalTableBody')) {
                            window.loadAllUsersModalData(window._currentAdminOrgFilter);
                        }
                        fetch('/api/admin/dashboard_data')
                            .then(r => r.json())
                            .then(d => {
                                if (d.success && d.data && window.renderAdminAnalytics) {
                                    window.renderAdminAnalytics(d.data);
                                }
                            });
                    } else {
                        if (errorAlert) {
                            errorAlert.textContent = res.message || "Failed to update user profile.";
                            errorAlert.classList.remove('d-none');
                        } else {
                            window.showToast(res.message || "Failed to update user profile.", "danger");
                        }
                    }
                })
                .catch(err => {
                    console.error("Update profile error:", err);
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');
                    window.showToast("Network error updating user profile.", "danger");
                });
        });
    }

    // 2. User Self-Service Profile Form
    const userProfileForm = document.getElementById('dnUserProfileForm');
    if (userProfileForm) {
        userProfileForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const firstName = (document.getElementById('userProfileFirstName').value || '').trim();
            const lastName = (document.getElementById('userProfileLastName').value || '').trim();
            const organization = (document.getElementById('userProfileOrganization').value || '').trim();
            const phone = (document.getElementById('userProfilePhone').value || '').trim();
            const bio = (document.getElementById('userProfileBio').value || '').trim();
            const errorAlert = document.getElementById('userProfileErrorAlert');

            const btnSubmit = document.getElementById('btnSubmitUserProfile');
            const spinner = document.getElementById('userProfileSpinner');
            const saveIcon = document.getElementById('userProfileSaveIcon');

            if (!firstName) {
                if (errorAlert) {
                    errorAlert.textContent = "First name cannot be empty.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }
            if (!organization) {
                if (errorAlert) {
                    errorAlert.textContent = "Organization cannot be empty.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }

            if (errorAlert) errorAlert.classList.add('d-none');

            if (btnSubmit) btnSubmit.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (saveIcon) saveIcon.classList.add('d-none');

            fetch('/api/user/profile/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    organization: organization,
                    phone: phone,
                    bio: bio
                })
            })
                .then(r => r.json())
                .then(res => {
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (saveIcon) saveIcon.classList.remove('d-none');

                    if (res.success) {
                        const modalEl = document.getElementById('adminUserProfileModal');
                        const modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) modalInstance.hide();

                        window.showToast(res.message || "Profile updated successfully.", "success");

                        // Update page display name and avatar initials if present
                        const fullNameDisplay = document.getElementById('userProfileFullNameDisplay');
                        if (fullNameDisplay) fullNameDisplay.textContent = `${firstName} ${lastName}`;

                        const avatarBadge = document.getElementById('userProfileAvatarBadge');
                        if (avatarBadge) {
                            const init1 = firstName[0] ? firstName[0].toUpperCase() : 'U';
                            const init2 = lastName[0] ? lastName[0].toUpperCase() : '';
                            avatarBadge.textContent = `${init1}${init2}`;
                        }

                        // Also update topbar username if present
                        const topbarUserName = document.querySelector('.dn-topbar-user .fw-semibold');
                        if (topbarUserName) topbarUserName.textContent = `${firstName} ${lastName}`;
                    } else {
                        if (errorAlert) {
                            errorAlert.textContent = res.message || "Failed to update profile.";
                            errorAlert.classList.remove('d-none');
                        } else {
                            window.showToast(res.message || "Failed to update profile.", "danger");
                        }
                    }
                })
                .catch(err => {
                    console.error("Self profile update error:", err);
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (saveIcon) saveIcon.classList.remove('d-none');
                    window.showToast("Network error updating your profile.", "danger");
                });
        });
    }

    // Prefill profile on opening adminUserProfileModal
    const profileModalEl = document.getElementById('adminUserProfileModal');
    if (profileModalEl) {
        profileModalEl.addEventListener('show.bs.modal', function () {
            fetch('/api/user/profile')
                .then(r => r.json())
                .then(res => {
                    if (res.success && res.profile) {
                        const p = res.profile;
                        const fnEl = document.getElementById('userProfileFirstName');
                        const lnEl = document.getElementById('userProfileLastName');
                        const emEl = document.getElementById('userProfileEmail');
                        const orgEl = document.getElementById('userProfileOrganization');
                        const phEl = document.getElementById('userProfilePhone');
                        const bioEl = document.getElementById('userProfileBio');

                        if (fnEl) fnEl.value = p.first_name || '';
                        if (lnEl) lnEl.value = p.last_name || '';
                        if (emEl) emEl.value = p.email || '';
                        if (orgEl) orgEl.value = p.organization || 'General';
                        if (phEl) phEl.value = p.phone || '';
                        if (bioEl) bioEl.value = p.bio || '';
                    }
                })
                .catch(err => console.error("Error fetching self profile:", err));
        });
    }
});

window.deleteUserAccount = function (userId) {
    if (!confirm(`Are you sure you want to permanently delete User ID #${userId}?`)) return;
    const toastFn = window.showToast || function (m) { console.log(m); };

    fetch('/api/admin/delete_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
    })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                toastFn(res.message || "User deleted successfully.", "success");
                if (window.DataNovaStateBus) window.DataNovaStateBus.notify('MUTATION_USER_DELETED', { userId: userId });
                if (document.getElementById('allUsersModalTableBody')) window.loadAllUsersModalData();
                fetch('/api/admin/dashboard_data').then(r => r.json()).then(d => {
                    if (d.success && d.data && window.renderAdminAnalytics) window.renderAdminAnalytics(d.data);
                });
            } else {
                toastFn(res.message || "Failed to delete user.", "danger");
            }
        })
        .catch(() => {
            toastFn("Network error deleting user.", "danger");
        });
};

// Global State Bus Listener for Admin Dashboard
if (window.DataNovaStateBus) {
    window.DataNovaStateBus.on('*', function (eventType) {
        if (eventType !== 'MUTATION_ADMIN_FETCH') {
            console.log("Admin Dashboard syncing with Global State Bus:", eventType);
            fetch('/api/admin/dashboard_data')
                .then(r => r.json())
                .then(d => {
                    if (d.success && d.data && window.renderAdminAnalytics) {
                        window.renderAdminAnalytics(d.data);
                    }
                });
            if (document.getElementById('allUsersModalTableBody') && window.loadAllUsersModalData) {
                window.loadAllUsersModalData();
            }
        }
    });
}

// --- All Datasets Modal Controller ---
window.showAllDatasetsModal = function () {
    const modalEl = document.getElementById('allDatasetsModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
    window.loadAllDatasetsModalData();
};

window.loadAllDatasetsModalData = function () {
    const tbody = document.getElementById('allDatasetsModalTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" class="text-center p-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Loading datasets...</div></td></tr>`;

    fetch('/api/admin/datasets/all')
        .then(r => r.json())
        .then(res => {
            if (res.success && Array.isArray(res.datasets)) {
                if (document.getElementById('modalDatasetsCount')) {
                    document.getElementById('modalDatasetsCount').textContent = `Total Datasets: ${res.total}`;
                }
                if (res.datasets.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" class="text-center p-4 text-secondary">No datasets uploaded yet.</td></tr>`;
                    return;
                }
                tbody.innerHTML = res.datasets.map(d => `
                    <tr>
                        <td class="fw-semibold text-black">${d.file_name || 'Untitled'}</td>
                        <td>${d.owner_name || 'Unknown'}<br><small class="text-secondary">${d.owner_email || ''}</small></td>
                        <td><span class="badge bg-indigo text-black">${(d.file_type || 'CSV').toUpperCase()}</span></td>
                        <td>${d.uploaded_at}</td>
                        <td>${((d.file_size || 0) / (1024 * 1024)).toFixed(2)} MB</td>
                        <td><small class="font-monospace">${d.row_count || '--'} rows × ${d.column_count || '--'} cols</small></td>
                        <td><span class="dn-badge-status ok"><i class="bi bi-circle-fill" style="font-size:6px"></i> ${(d.status || 'ready').toUpperCase()}</span></td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center p-4 text-danger">Failed to load datasets.</td></tr>`;
            }
        })
        .catch(err => {
            console.error("Error fetching all datasets:", err);
            tbody.innerHTML = `<tr><td colspan="7" class="text-center p-4 text-danger">Network error loading datasets.</td></tr>`;
        });
};

window.filterAllDatasetsModalTable = function () {
    const query = (document.getElementById('allDatasetsModalSearchInput').value || '').toLowerCase();
    const rows = document.querySelectorAll('#allDatasetsModalTableBody tr');
    rows.forEach(r => {
        const text = (r.textContent || '').toLowerCase();
        r.style.display = (!query || text.includes(query)) ? '' : 'none';
    });
};

// --- All System Activity Modal Controller ---
window.showAllSystemActivityModal = function () {
    const modalEl = document.getElementById('allSystemActivityModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
    window.loadAllSystemActivityModalData();
};

window.loadAllSystemActivityModalData = function () {
    const tbody = document.getElementById('allActivityModalTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4"><div class="spinner-border text-info" role="status"></div><div class="mt-2 text-secondary">Loading system audit logs...</div></td></tr>`;

    fetch('/api/admin/activities/all')
        .then(r => r.json())
        .then(res => {
            if (res.success && Array.isArray(res.activities)) {
                if (res.activities.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-secondary">No activity logs recorded.</td></tr>`;
                    return;
                }
                tbody.innerHTML = res.activities.map(a => `
                    <tr>
                        <td><div class="fw-semibold text-black">${a.user_name}</div><small class="text-secondary">${a.user_email}</small></td>
                        <td><span class="badge bg-secondary-subtle text-secondary border">${a.user_role}</span></td>
                        <td><span class="font-monospace small">${a.endpoint}</span></td>
                        <td><span class="badge ${a.status === 'success' ? 'bg-success' : 'bg-danger'}">${a.status.toUpperCase()}</span></td>
                        <td><small class="text-secondary">${a.timestamp}</small><br><small class="text-info">${a.time_ago}</small></td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-danger">Failed to load system activity logs.</td></tr>`;
            }
        })
        .catch(err => {
            console.error("Error fetching activity logs:", err);
            tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-danger">Network error loading activity logs.</td></tr>`;
        });
};

window.filterAllActivityModalTable = function () {
    const query = (document.getElementById('allActivityModalSearchInput').value || '').toLowerCase();
    const rows = document.querySelectorAll('#allActivityModalTableBody tr');
    rows.forEach(r => {
        const text = (r.textContent || '').toLowerCase();
        r.style.display = (!query || text.includes(query)) ? '' : 'none';
    });
};

// --- System Settings & Diagnostics Controller ---
function loadSystemDiagnostics() {
    fetch('/api/admin/settings/diagnostics')
        .then(r => r.json())
        .then(res => {
            if (res.success && res.diagnostics) {
                const d = res.diagnostics;

                // Database
                const dbEl = document.getElementById('diagDbStatus');
                if (dbEl && d.database) {
                    const isOk = d.database.status === 'healthy';
                    dbEl.className = `small fw-bold ${isOk ? 'text-success' : 'text-danger'}`;
                    dbEl.innerHTML = `<i class="bi ${isOk ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-1"></i> ${d.database.label} (${d.database.latency_ms || 0}ms)`;
                }

                // Storage
                const storageEl = document.getElementById('diagStorageStatus');
                if (storageEl && d.storage) {
                    const isOk = d.storage.status === 'healthy';
                    storageEl.className = `small fw-bold ${isOk ? 'text-success' : 'text-warning'}`;
                    storageEl.innerHTML = `<i class="bi ${isOk ? 'bi-folder-check' : 'bi-exclamation-triangle-fill'} me-1"></i> ${d.storage.label}`;
                }

                // SMTP
                const smtpEl = document.getElementById('diagSmtpStatus');
                if (smtpEl && d.smtp) {
                    const isOk = d.smtp.status === 'healthy';
                    smtpEl.className = `small fw-bold ${isOk ? 'text-info' : 'text-secondary'}`;
                    smtpEl.innerHTML = `<i class="bi ${isOk ? 'bi-envelope-check' : 'bi-envelope-slash'} me-1"></i> ${d.smtp.label}`;
                }

                // AI Engine
                const aiEl = document.getElementById('diagAiStatus');
                if (aiEl && d.ai) {
                    const isOk = d.ai.status === 'healthy';
                    const isWarn = d.ai.status === 'warning';
                    aiEl.className = `small fw-bold ${isOk ? 'text-success' : (isWarn ? 'text-warning' : 'text-secondary')}`;
                    aiEl.innerHTML = `<i class="bi ${isOk ? 'bi-cpu-fill' : 'bi-cpu'} me-1"></i> ${d.ai.label}`;
                }
            }
        })
        .catch(err => console.error("Error loading diagnostics:", err));
}
window.loadSystemDiagnostics = loadSystemDiagnostics;

window.showSystemSettingsModal = function () {
    const modalEl = document.getElementById('dnSystemSettingsModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();

    // Fetch system settings from backend
    fetch('/api/admin/settings')
        .then(r => r.json())
        .then(res => {
            if (res.success && res.settings) {
                const s = res.settings;
                // General
                if (document.getElementById('settingPlatformName')) document.getElementById('settingPlatformName').value = s.platform_name || 'DataNova Analytics Platform';
                if (document.getElementById('settingDefaultRole')) document.getElementById('settingDefaultRole').value = s.default_role || 'viewer';
                if (document.getElementById('settingMaxFileSize')) document.getElementById('settingMaxFileSize').value = s.max_file_size_mb || '50';
                if (document.getElementById('settingAllowedExtensions')) document.getElementById('settingAllowedExtensions').value = s.allowed_extensions || '.csv, .xlsx, .xls, .json';
                if (document.getElementById('settingAllowUserRegistration')) document.getElementById('settingAllowUserRegistration').checked = s.allow_user_registration !== false;
                if (document.getElementById('settingMaintenanceMode')) document.getElementById('settingMaintenanceMode').checked = Boolean(s.maintenance_mode);

                // Security
                if (document.getElementById('settingSessionTimeout')) document.getElementById('settingSessionTimeout').value = s.session_timeout || '60';
                if (document.getElementById('settingMaxLoginAttempts')) document.getElementById('settingMaxLoginAttempts').value = s.max_login_attempts || '5';
                if (document.getElementById('settingLockoutDuration')) document.getElementById('settingLockoutDuration').value = s.lockout_duration_mins || '15';
                if (document.getElementById('settingEnforceStrongPasswords')) document.getElementById('settingEnforceStrongPasswords').checked = s.enforce_strong_passwords !== false;
                if (document.getElementById('settingRequireEmailVerification')) document.getElementById('settingRequireEmailVerification').checked = Boolean(s.require_email_verification);

                // Email & SMTP
                if (document.getElementById('settingSmtpHost')) document.getElementById('settingSmtpHost').value = s.smtp_host || 'smtp.gmail.com';
                if (document.getElementById('settingSmtpPort')) document.getElementById('settingSmtpPort').value = s.smtp_port || '587';
                if (document.getElementById('settingSmtpEncryption')) document.getElementById('settingSmtpEncryption').value = s.smtp_encryption || 'tls';
                if (document.getElementById('settingSenderEmail')) document.getElementById('settingSenderEmail').value = s.sender_email || 'noreply@datanova.com';
                if (document.getElementById('settingSmtpUsername')) document.getElementById('settingSmtpUsername').value = s.smtp_username || '';
                if (document.getElementById('settingSmtpPassword')) {
                    document.getElementById('settingSmtpPassword').value = s.has_smtp_password ? '••••••••••••' : '';
                }

                // AI & Analytics
                if (document.getElementById('settingAiEnabled')) document.getElementById('settingAiEnabled').checked = s.ai_insights_enabled !== false;
                if (document.getElementById('settingAutoEda')) document.getElementById('settingAutoEda').checked = s.auto_eda_on_upload !== false;
                if (document.getElementById('settingAiModel')) document.getElementById('settingAiModel').value = s.ai_model || 'gemini-2.0-flash';
                if (document.getElementById('settingAiMaxTokens')) document.getElementById('settingAiMaxTokens').value = s.ai_max_tokens || '1024';
                if (document.getElementById('settingAiTemperature')) {
                    const temp = s.ai_temperature !== undefined ? s.ai_temperature : '0.7';
                    document.getElementById('settingAiTemperature').value = temp;
                    if (document.getElementById('settingAiTemperatureValue')) {
                        document.getElementById('settingAiTemperatureValue').textContent = temp;
                    }
                }
            }
        })
        .catch(err => console.error("Error fetching system settings:", err));

    loadSystemDiagnostics();
};

document.addEventListener('DOMContentLoaded', function () {
    // --- Live Temperature Slider Value ---
    const tempSlider = document.getElementById('settingAiTemperature');
    const tempValBadge = document.getElementById('settingAiTemperatureValue');
    if (tempSlider && tempValBadge) {
        tempSlider.addEventListener('input', function () {
            tempValBadge.textContent = this.value;
        });
    }

    // --- Toggle SMTP Password Visibility ---
    const btnTogglePass = document.getElementById('btnToggleSmtpPassword');
    const inputSmtpPass = document.getElementById('settingSmtpPassword');
    const iconTogglePass = document.getElementById('iconToggleSmtpPassword');
    if (btnTogglePass && inputSmtpPass) {
        btnTogglePass.addEventListener('click', function () {
            const isPassword = inputSmtpPass.getAttribute('type') === 'password';
            inputSmtpPass.setAttribute('type', isPassword ? 'text' : 'password');
            if (iconTogglePass) {
                iconTogglePass.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
            }
        });
    }

    // --- Send Test Email Live Action ---
    const btnSendTestEmail = document.getElementById('btnSendTestEmail');
    if (btnSendTestEmail) {
        btnSendTestEmail.addEventListener('click', function () {
            const recipientInput = document.getElementById('settingTestEmailRecipient');
            const alertEl = document.getElementById('testEmailAlert');
            const toEmail = recipientInput ? recipientInput.value.trim() : '';

            if (!toEmail || !toEmail.includes('@')) {
                if (alertEl) {
                    alertEl.className = 'alert alert-danger p-2 small mt-2';
                    alertEl.textContent = 'Please enter a valid recipient email address.';
                    alertEl.classList.remove('d-none');
                }
                return;
            }

            const originalHtml = btnSendTestEmail.innerHTML;
            btnSendTestEmail.disabled = true;
            btnSendTestEmail.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Testing SMTP...';

            if (alertEl) alertEl.classList.add('d-none');

            const payload = {
                to_email: toEmail,
                smtp_host: document.getElementById('settingSmtpHost') ? document.getElementById('settingSmtpHost').value : '',
                smtp_port: document.getElementById('settingSmtpPort') ? document.getElementById('settingSmtpPort').value : '',
                smtp_encryption: document.getElementById('settingSmtpEncryption') ? document.getElementById('settingSmtpEncryption').value : 'tls',
                sender_email: document.getElementById('settingSenderEmail') ? document.getElementById('settingSenderEmail').value : '',
                smtp_username: document.getElementById('settingSmtpUsername') ? document.getElementById('settingSmtpUsername').value : '',
                smtp_password: document.getElementById('settingSmtpPassword') ? document.getElementById('settingSmtpPassword').value : ''
            };

            fetch('/api/admin/settings/test_email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(res => {
                    btnSendTestEmail.disabled = false;
                    btnSendTestEmail.innerHTML = originalHtml;
                    if (alertEl) {
                        alertEl.className = res.success ? 'alert alert-success p-2 small mt-2' : 'alert alert-danger p-2 small mt-2';
                        alertEl.innerHTML = `<i class="bi ${res.success ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'} me-1"></i> ${res.message}`;
                        alertEl.classList.remove('d-none');
                    }
                    if (res.success) {
                        window.showToast("Test email sent successfully!", "success");
                    }
                })
                .catch(err => {
                    btnSendTestEmail.disabled = false;
                    btnSendTestEmail.innerHTML = originalHtml;
                    if (alertEl) {
                        alertEl.className = 'alert alert-danger p-2 small mt-2';
                        alertEl.textContent = 'Network or server error while connecting to SMTP host.';
                        alertEl.classList.remove('d-none');
                    }
                });
        });
    }

    // --- Refresh Diagnostics Button ---
    const btnRefreshDiag = document.getElementById('btnRefreshDiagnostics');
    if (btnRefreshDiag) {
        btnRefreshDiag.addEventListener('click', function () {
            btnRefreshDiag.disabled = true;
            btnRefreshDiag.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Checking...';
            loadSystemDiagnostics();
            setTimeout(() => {
                btnRefreshDiag.disabled = false;
                btnRefreshDiag.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Refresh';
                window.showToast("System health diagnostics updated!", "info");
            }, 600);
        });
    }

    // --- Purge Temporary Cache ---
    const btnClearCache = document.getElementById('btnClearCache');
    if (btnClearCache) {
        btnClearCache.addEventListener('click', function () {
            if (!confirm("Are you sure you want to clear temporary uploads and cache buffers?")) return;

            btnClearCache.disabled = true;
            btnClearCache.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Purging...';

            fetch('/api/admin/settings/clear_cache', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
                .then(r => r.json())
                .then(res => {
                    btnClearCache.disabled = false;
                    btnClearCache.innerHTML = '<i class="bi bi-trash3"></i> Purge Temporary Cache';
                    if (res.success) {
                        window.showToast(res.message, "success");
                        loadSystemDiagnostics();
                    } else {
                        window.showToast(res.message || "Failed to clear cache.", "danger");
                    }
                })
                .catch(err => {
                    btnClearCache.disabled = false;
                    btnClearCache.innerHTML = '<i class="bi bi-trash3"></i> Purge Temporary Cache';
                    window.showToast("Network error purging cache.", "danger");
                });
        });
    }

    // --- Factory Defaults Reset ---
    const btnResetSettings = document.getElementById('btnResetSettings');
    if (btnResetSettings) {
        btnResetSettings.addEventListener('click', function () {
            if (!confirm("Are you sure you want to reset ALL system settings to factory defaults?")) return;

            fetch('/api/admin/settings/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        window.showToast("System settings restored to defaults!", "warning");
                        window.showSystemSettingsModal();
                    } else {
                        window.showToast(res.message || "Failed to reset settings.", "danger");
                    }
                })
                .catch(err => {
                    window.showToast("Network error resetting settings.", "danger");
                });
        });
    }

    // --- Import Settings JSON ---
    const inputImportSettings = document.getElementById('inputImportSettings');
    if (inputImportSettings) {
        inputImportSettings.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/admin/settings/import', {
                method: 'POST',
                body: formData
            })
                .then(r => r.json())
                .then(res => {
                    inputImportSettings.value = '';
                    if (res.success) {
                        window.showToast("System configuration imported successfully!", "success");
                        window.showSystemSettingsModal();
                    } else {
                        window.showToast(res.message || "Failed to import settings.", "danger");
                    }
                })
                .catch(err => {
                    inputImportSettings.value = '';
                    window.showToast("Network error importing settings.", "danger");
                });
        });
    }

    // --- Save System Settings Form Submission ---
    const settingsForm = document.getElementById('dnSystemSettingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const btn = document.getElementById('btnSaveSettings');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Saving...';
            }

            const rawPassword = document.getElementById('settingSmtpPassword') ? document.getElementById('settingSmtpPassword').value : '';
            const payload = {
                platform_name: document.getElementById('settingPlatformName') ? document.getElementById('settingPlatformName').value : '',
                default_role: document.getElementById('settingDefaultRole') ? document.getElementById('settingDefaultRole').value : 'viewer',
                max_file_size_mb: document.getElementById('settingMaxFileSize') ? document.getElementById('settingMaxFileSize').value : '50',
                allowed_extensions: document.getElementById('settingAllowedExtensions') ? document.getElementById('settingAllowedExtensions').value : '.csv, .xlsx, .xls, .json',
                allow_user_registration: document.getElementById('settingAllowUserRegistration') ? document.getElementById('settingAllowUserRegistration').checked : true,
                maintenance_mode: document.getElementById('settingMaintenanceMode') ? document.getElementById('settingMaintenanceMode').checked : false,

                session_timeout: document.getElementById('settingSessionTimeout') ? document.getElementById('settingSessionTimeout').value : '60',
                max_login_attempts: document.getElementById('settingMaxLoginAttempts') ? document.getElementById('settingMaxLoginAttempts').value : '5',
                lockout_duration_mins: document.getElementById('settingLockoutDuration') ? document.getElementById('settingLockoutDuration').value : '15',
                enforce_strong_passwords: document.getElementById('settingEnforceStrongPasswords') ? document.getElementById('settingEnforceStrongPasswords').checked : true,
                require_email_verification: document.getElementById('settingRequireEmailVerification') ? document.getElementById('settingRequireEmailVerification').checked : false,

                smtp_host: document.getElementById('settingSmtpHost') ? document.getElementById('settingSmtpHost').value : '',
                smtp_port: document.getElementById('settingSmtpPort') ? document.getElementById('settingSmtpPort').value : '587',
                smtp_encryption: document.getElementById('settingSmtpEncryption') ? document.getElementById('settingSmtpEncryption').value : 'tls',
                sender_email: document.getElementById('settingSenderEmail') ? document.getElementById('settingSenderEmail').value : '',
                smtp_username: document.getElementById('settingSmtpUsername') ? document.getElementById('settingSmtpUsername').value : '',
                smtp_password: rawPassword === '••••••••••••' ? '' : rawPassword,

                ai_insights_enabled: document.getElementById('settingAiEnabled') ? document.getElementById('settingAiEnabled').checked : true,
                auto_eda_on_upload: document.getElementById('settingAutoEda') ? document.getElementById('settingAutoEda').checked : true,
                ai_model: document.getElementById('settingAiModel') ? document.getElementById('settingAiModel').value : 'gemini-2.0-flash',
                ai_max_tokens: document.getElementById('settingAiMaxTokens') ? document.getElementById('settingAiMaxTokens').value : '1024',
                ai_temperature: document.getElementById('settingAiTemperature') ? document.getElementById('settingAiTemperature').value : '0.7'
            };

            fetch('/api/admin/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(res => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Save Platform Settings';
                    }
                    const alertEl = document.getElementById('settingsAlert');
                    if (res.success) {
                        if (alertEl) {
                            alertEl.textContent = res.message || "Settings saved!";
                            alertEl.classList.remove('d-none');
                            setTimeout(() => alertEl.classList.add('d-none'), 3500);
                        }
                        window.showToast("System settings updated successfully!", "success");
                        loadSystemDiagnostics();
                    } else {
                        window.showToast(res.message || "Failed to update settings.", "danger");
                    }
                })
                .catch(err => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Save Platform Settings';
                    }
                    console.error("Save settings error:", err);
                    window.showToast("Network error saving settings.", "danger");
                });
        });
    }
});

// --- View Reports Modal Controller ---
window.showViewReportsModal = function () {
    const modalEl = document.getElementById('adminViewReportsModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();

    const tbody = document.getElementById('adminReportsModalTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4"><div class="spinner-border text-warning" role="status"></div><div class="mt-2 text-secondary">Loading reports...</div></td></tr>`;

    fetch('/api/admin/reports')
        .then(r => r.json())
        .then(res => {
            if (res.success && Array.isArray(res.reports)) {
                if (document.getElementById('modalReportsCount')) {
                    document.getElementById('modalReportsCount').textContent = `Total Reports: ${res.count}`;
                }
                if (res.reports.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-secondary">No reports generated yet.</td></tr>`;
                    return;
                }
                tbody.innerHTML = res.reports.map(rep => `
                    <tr>
                        <td class="fw-semibold"><i class="bi bi-file-earmark-pdf text-danger me-1"></i> ${rep.report_name || 'Report'}</td>
                        <td>${rep.first_name || 'User'} ${rep.last_name || ''}<br><small class="text-secondary">${rep.email || ''}</small></td>
                        <td><span class="badge bg-primary-subtle text-primary">${rep.dataset_name || 'Dataset'}</span></td>
                        <td><span class="badge bg-info text-white">${(rep.report_type || 'HTML').toUpperCase()}</span></td>
                        <td>${rep.created_at || 'N/A'}</td>
                        <td class="text-end">
                            <a href="/api/report/download/${rep.id}" class="btn btn-sm btn-outline-success py-0 px-2" target="_blank"><i class="bi bi-download"></i> View</a>
                        </td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-danger">Failed to load reports.</td></tr>`;
            }
        })
        .catch(err => {
            console.error("Error fetching reports:", err);
            tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-danger">Network error loading reports.</td></tr>`;
        });
};

window.filterReportsModalTable = function () {
    const query = (document.getElementById('reportsModalSearchInput').value || '').toLowerCase();
    const rows = document.querySelectorAll('#adminReportsModalTableBody tr');
    rows.forEach(r => {
        const text = (r.textContent || '').toLowerCase();
        r.style.display = (!query || text.includes(query)) ? '' : 'none';
    });
};

// --- Shared Dashboards Modal Controller ---
window.showSharedDashboardsModal = function () {
    const modalEl = document.getElementById('adminSharedDashboardsModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();

    const tbody = document.getElementById('adminSharedDashboardsTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Loading shared dashboards...</div></td></tr>`;

    fetch('/api/admin/shared_dashboards')
        .then(r => r.json())
        .then(res => {
            if (res.success && Array.isArray(res.dashboards)) {
                if (res.dashboards.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-secondary">No shared dashboards available.</td></tr>`;
                    return;
                }
                tbody.innerHTML = res.dashboards.map(sd => `
                    <tr>
                        <td class="fw-semibold"><i class="bi bi-grid-1x2 text-primary me-1"></i> ${sd.title || 'Untitled Dashboard'}</td>
                        <td>${sd.owner_name} <span class="badge bg-secondary-subtle text-secondary small">${(sd.owner_role || 'analyst').toUpperCase()}</span></td>
                        <td><span class="badge bg-info-subtle text-info border border-info-subtle">${(sd.shared_with_role || 'ALL ROLES').toUpperCase()}</span></td>
                        <td>${sd.dataset_name || 'N/A'}</td>
                        <td><small class="text-secondary">${sd.created_at}</small></td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-danger">Failed to load shared dashboards.</td></tr>`;
            }
        })
        .catch(err => {
            console.error("Error fetching shared dashboards:", err);
            tbody.innerHTML = `<tr><td colspan="5" class="text-center p-4 text-danger">Network error loading shared dashboards.</td></tr>`;
        });
};

// --- Security Status & Audit Scan Controller ---
function updateSecurityUI(secDetails) {
    if (!secDetails) return;

    // Security Score Badge Update
    const badgeEl = document.getElementById('badgeSecurityStatus');
    if (badgeEl) {
        const score = secDetails.score !== undefined ? secDetails.score : 100;
        const statusLabel = secDetails.status_label || secDetails.status || 'OPTIMAL';
        let badgeClass = 'bg-success-subtle text-success border-success-subtle';
        if (score < 70) badgeClass = 'bg-danger-subtle text-danger border-danger-subtle';
        else if (score < 85) badgeClass = 'bg-warning-subtle text-warning border-warning-subtle';

        badgeEl.className = `badge ${badgeClass} border px-2 py-1`;
        badgeEl.innerHTML = `<i class="bi bi-shield-check me-1"></i> ${statusLabel} (${score}/100)`;
    }

    // Security Alerts Update
    const alertsContainer = document.getElementById('adminSecurityAlertsContainer');
    if (alertsContainer && secDetails.alerts) {
        if (!secDetails.alerts.length) {
            alertsContainer.innerHTML = `<div class="dn-alert dn-alert-info"><i class="bi bi-shield-check"></i> System security optimal. 0 high risk threats reported.</div>`;
        } else {
            alertsContainer.innerHTML = secDetails.alerts.map(alert => `
                <div class="dn-alert dn-alert-${alert.type || 'info'}"><i class="bi ${alert.icon || 'bi-shield-check'}"></i> ${alert.text || ''}</div>
            `).join('');
        }
    }

    // Security Policies Grid Update
    const policyGrid = document.getElementById('adminSecurityPolicyGrid');
    if (policyGrid && secDetails.policies && Array.isArray(secDetails.policies)) {
        policyGrid.innerHTML = secDetails.policies.map(p => {
            const title = p.title || p.name || 'Security Policy';
            const detail = p.status_text || p.detail || p.status || 'Active';
            const icon = p.icon || 'bi-shield-check';
            const textClass = p.text_class || p.badge || 'text-success';
            const borderClass = p.border_class || '';

            return `
                <div class="col-6 col-md-4">
                    <div class="p-2 rounded bg-body-tertiary border h-100 ${borderClass}">
                        <div class="small text-secondary fw-semibold">${title}</div>
                        <div class="small fw-bold ${textClass}"><i class="bi ${icon} me-1"></i>${detail}</div>
                    </div>
                </div>
            `;
        }).join('');
    }
}
window.updateSecurityUI = updateSecurityUI;

// Handle Run Security Scan Button
document.addEventListener('click', function (e) {
    const btnRunScan = e.target.closest('#btnRunSecurityScan');
    if (!btnRunScan) return;

    const iconScan = document.getElementById('iconSecurityScan');
    if (iconScan) iconScan.classList.add('spin-animation');
    btnRunScan.disabled = true;

    fetch('/api/admin/security/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(res => res.json())
        .then(resData => {
            if (iconScan) iconScan.classList.remove('spin-animation');
            btnRunScan.disabled = false;
            if (resData.success && resData.security) {
                updateSecurityUI(resData.security);
                if (typeof window.showToast === 'function') {
                    window.showToast('Security audit scan completed! All metrics updated.', 'success');
                } else if (typeof showToast === 'function') {
                    showToast('Security audit scan completed! All metrics updated.', 'success');
                }
            } else {
                const errorMsg = resData.error || 'Failed to execute security audit scan.';
                if (typeof window.showToast === 'function') {
                    window.showToast(errorMsg, 'danger');
                } else if (typeof showToast === 'function') {
                    showToast(errorMsg, 'danger');
                }
            }
        })
        .catch(err => {
            if (iconScan) iconScan.classList.remove('spin-animation');
            btnRunScan.disabled = false;
            console.error('Security scan error:', err);
        });
});