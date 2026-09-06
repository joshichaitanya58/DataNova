/* ==========================================================================
   DataNova — Admin Dashboard Interactive Controller
   Handles User Management, Role Editing, Log Exports, Plotly Analytics,
   System Activity refresh, Sidebar/Theme controls, and Quick Action buttons.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Admin Controller Initialized.");

    // --- Helper UI Functions ---
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

    // --- Sidebar Navigation Links ---
    document.querySelectorAll('.dn-nav-link[data-section], .dn-nav-link[data-page]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            if (page === 'settings') {
                window.showSystemSettingsModal();
                return;
            }
            if (page === 'shared-dashboards') {
                window.showSharedDashboardsModal();
                return;
            }
            const section = link.getAttribute('data-section');
            if (section) {
                scrollToSection(section);
                return;
            }
        });
    });

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

    // --- Dynamic Admin Analytics Auto-Fetch ---
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
        if (data.storage_percentage !== undefined && document.getElementById('kpiStoragePct')) {
            document.getElementById('kpiStoragePct').textContent = `${Math.round(data.storage_percentage)}%`;
        }
        if (data.storage_used_gb !== undefined && document.getElementById('kpiStorageGb')) {
            document.getElementById('kpiStorageGb').innerHTML = `<i class="bi bi-arrow-up-short"></i>${data.storage_used_gb} GB`;
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

    const plotlyConfig = {
        responsive: true,
        displayModeBar: 'hover',
        displaylogo: false,
        modeBarButtonsToAdd: ['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'],
        doubleClick: 'reset+autosize'
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
            Plotly.newPlot(container, [trace], layout, plotlyConfig);
        } catch (e) {
            console.error("Error rendering role donut chart:", e);
        }
    }

    function renderUserActivityChart(activityData) {
        const container = document.getElementById('adminUserActivityChart');
        if (!container || typeof Plotly === 'undefined') return;

        const labels = (activityData && activityData.labels && activityData.labels.length)
            ? activityData.labels
            : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

        const active = (activityData && activityData.active && activityData.active.length)
            ? activityData.active
            : [0, 0, 0, 0, 0, 0, 0];

        const inactive = (activityData && activityData.inactive && activityData.inactive.length)
            ? activityData.inactive
            : [0, 0, 0, 0, 0, 0, 0];

        const traceActive = {
            x: labels,
            y: active,
            name: 'Active',
            type: 'bar',
            marker: { color: '#4F46E5', cornerradius: 4 }
        };

        const traceInactive = {
            x: labels,
            y: inactive,
            name: 'Inactive',
            type: 'bar',
            marker: { color: 'rgba(148, 163, 184, 0.3)', cornerradius: 4 }
        };

        const layout = {
            barmode: 'stack',
            margin: { t: 10, r: 10, l: 30, b: 30 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { showgrid: false, color: '#94A3B8' },
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8' },
            legend: { orientation: 'h', x: 0, y: 1.15, font: { color: '#94A3B8', size: 10 } },
            autosize: true
        };

        try {
            Plotly.newPlot(container, [traceActive, traceInactive], layout, plotlyConfig);
        } catch (e) {
            console.error("Error rendering user activity chart:", e);
        }
    }

    function renderDefaultRoleDonutChart() {
        renderRoleDonutChart({ analyst: 1, manager: 1, viewer: 1, admin: 1 });
    }
    function renderDefaultUserActivityChart() {
        renderUserActivityChart({ labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], active: [0, 0, 0, 0, 0, 0, 0], inactive: [0, 0, 0, 0, 0, 0, 0] });
    }

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
            const passwordEl = document.getElementById('addUserPassword');
            const roleEl = document.getElementById('addUserRole');
            const errorAlert = document.getElementById('addUserErrorAlert');

            const firstName = (firstNameEl ? firstNameEl.value : '').trim();
            const lastName = (lastNameEl ? lastNameEl.value : '').trim();
            const email = (emailEl ? emailEl.value : '').trim();
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

            const payload = { first_name: firstName, last_name: lastName, email: email, password: password, role: role };

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
    function exportSystemLogs() {
        showToast("Generating System Security Audit Logs...", "info");
        window.location.href = '/api/admin/export_logs';
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
window.showAllUsersModal = function () {
    const modalEl = document.getElementById('allUsersModal');
    if (!modalEl) return;
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
    window.loadAllUsersModalData();
};

window.loadAllUsersModalData = function () {
    const tbody = document.getElementById('allUsersModalTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Loading all registered users...</div></td></tr>';

    fetch('/api/admin/users')
        .then(res => res.json())
        .then(data => {
            if (data.success && Array.isArray(data.users)) {
                window.renderAllUsersModalTable(data.users);
            } else {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4 text-danger">Failed to load users list.</td></tr>';
            }
        })
        .catch(err => {
            console.error("Error loading all users:", err);
            tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4 text-danger">Network error loading users.</td></tr>';
        });
};

window.renderAllUsersModalTable = function (users) {
    const tbody = document.getElementById('allUsersModalTableBody');
    if (!tbody) return;

    let activeCnt = 0;
    let inactiveCnt = 0;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4">No registered users found.</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => {
        const isAct = (u.status || 'active').toLowerCase() === 'active';
        if (isAct) activeCnt++; else inactiveCnt++;

        const init1 = (u.first_name || 'U')[0].toUpperCase();
        const init2 = (u.last_name || '')[0] ? (u.last_name[0]).toUpperCase() : '';
        const roleCap = (u.role || 'viewer').charAt(0).toUpperCase() + (u.role || 'viewer').slice(1);
        const statusBadge = isAct
            ? '<span class="dn-badge-status ok"><i class="bi bi-circle-fill" style="font-size:6px"></i> Active</span>'
            : '<span class="dn-badge-status danger"><i class="bi bi-circle-fill" style="font-size:6px"></i> Inactive</span>';

        const toggleBtn = isAct
            ? `<button class="btn btn-sm btn-outline-danger py-1 px-2 small" onclick="toggleUserStatus(${u.id}, 'inactive'); return false;" title="Deactivate User Account"><i class="bi bi-person-x"></i> Make Inactive</button>`
            : `<button class="btn btn-sm btn-outline-success py-1 px-2 small" onclick="toggleUserStatus(${u.id}, 'active'); return false;" title="Activate User Account"><i class="bi bi-person-check"></i> Make Active</button>`;

        return `
            <tr>
                <td>
                    <div class="dn-cell-user"><span class="dn-avatar-sm">${init1}${init2}</span> <strong>${u.first_name || ''} ${u.last_name || ''}</strong></div>
                </td>
                <td>${u.email}</td>
                <td><span class="dn-badge-role">${roleCap}</span></td>
                <td>${statusBadge}</td>
                <td>${u.created_at || 'N/A'}</td>
                <td class="text-end">
                    <div class="d-flex gap-1 justify-content-end align-items-center">
                        ${toggleBtn}
                        <button class="btn btn-sm dn-btn-outline-dn py-1 px-2" title="Edit Role" onclick="showEditRoleModal(${u.id}, '${u.role}'); return false;"><i class="bi bi-pencil"></i></button>
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
                toastFn(res.message || "Failed to update user status.", "danger");
            }
        })
        .catch(err => {
            console.error("Error updating user status:", err);
            const toastFn = window.showToast || function (m) { console.log(m); };
            toastFn("Server connection error updating user status.", "danger");
        });
};

// --- Edit Role Modal Handling ---
window.showEditRoleModal = function (userId, currentRole) {
    const modalEl = document.getElementById('dnEditRoleModal');
    if (!modalEl) {
        window.showToast("Edit role modal element not found.", "danger");
        return;
    }

    const errorAlert = document.getElementById('editRoleErrorAlert');
    if (errorAlert) {
        errorAlert.classList.add('d-none');
        errorAlert.textContent = '';
    }

    document.getElementById('editRoleUserId').value = userId;
    document.getElementById('editRoleSelect').value = (currentRole || 'viewer').toLowerCase();

    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
};

// Attach Edit Role Form submit listener
document.addEventListener('DOMContentLoaded', function () {
    const editRoleForm = document.getElementById('dnEditRoleForm');
    if (editRoleForm) {
        editRoleForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const uid = document.getElementById('editRoleUserId').value;
            const role = document.getElementById('editRoleSelect').value;
            const errorAlert = document.getElementById('editRoleErrorAlert');

            const btnSubmit = document.getElementById('btnSubmitEditRole');
            const spinner = document.getElementById('editRoleSpinner');
            const checkIcon = document.getElementById('editRoleCheckIcon');

            if (btnSubmit) btnSubmit.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (checkIcon) checkIcon.classList.add('d-none');

            fetch('/api/admin/update_user_role', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: uid, role: role })
            })
                .then(r => r.json())
                .then(res => {
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');

                    const modalEl = document.getElementById('dnEditRoleModal');
                    const modalInstance = bootstrap.Modal.getInstance(modalEl);

                    if (res.success) {
                        if (modalInstance) modalInstance.hide();
                        window.showToast(res.message || "Role updated successfully.", "success");

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
                        if (errorAlert) {
                            errorAlert.textContent = res.message || "Failed to update role.";
                            errorAlert.classList.remove('d-none');
                        } else {
                            window.showToast(res.message || "Failed to update role.", "danger");
                        }
                    }
                })
                .catch(err => {
                    console.error("Update role error:", err);
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (checkIcon) checkIcon.classList.remove('d-none');
                    window.showToast("Network error updating user role.", "danger");
                });
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

// --- System Settings Modal Controller ---
window.showSystemSettingsModal = function () {
    const modalEl = document.getElementById('dnSystemSettingsModal');
    if (!modalEl) return;
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();

    fetch('/api/admin/settings')
        .then(r => r.json())
        .then(res => {
            if (res.success && res.settings) {
                const s = res.settings;
                if (document.getElementById('settingDefaultRole')) document.getElementById('settingDefaultRole').value = s.default_role || 'viewer';
                if (document.getElementById('settingMaxFileSize')) document.getElementById('settingMaxFileSize').value = s.max_file_size_mb || '50';
                if (document.getElementById('settingMaintenanceMode')) document.getElementById('settingMaintenanceMode').checked = Boolean(s.maintenance_mode);
                if (document.getElementById('settingSessionTimeout')) document.getElementById('settingSessionTimeout').value = s.session_timeout || '60';
                if (document.getElementById('settingSmtpHost')) document.getElementById('settingSmtpHost').value = s.smtp_host || 'smtp.gmail.com';
                if (document.getElementById('settingSmtpPort')) document.getElementById('settingSmtpPort').value = s.smtp_port || '587';
                if (document.getElementById('settingSenderEmail')) document.getElementById('settingSenderEmail').value = s.sender_email || 'noreply@datanova.com';
                if (document.getElementById('settingAiEnabled')) document.getElementById('settingAiEnabled').checked = Boolean(s.ai_insights_enabled);
            }
        });
};

document.addEventListener('DOMContentLoaded', function () {
    const settingsForm = document.getElementById('dnSystemSettingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const btn = document.getElementById('btnSaveSettings');
            if (btn) btn.disabled = true;

            const payload = {
                default_role: document.getElementById('settingDefaultRole').value,
                max_file_size_mb: document.getElementById('settingMaxFileSize').value,
                maintenance_mode: document.getElementById('settingMaintenanceMode').checked,
                session_timeout: document.getElementById('settingSessionTimeout').value,
                smtp_host: document.getElementById('settingSmtpHost').value,
                smtp_port: document.getElementById('settingSmtpPort').value,
                sender_email: document.getElementById('settingSenderEmail').value,
                ai_insights_enabled: document.getElementById('settingAiEnabled').checked
            };

            fetch('/api/admin/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(res => {
                    if (btn) btn.disabled = false;
                    const alertEl = document.getElementById('settingsAlert');
                    if (res.success) {
                        if (alertEl) {
                            alertEl.textContent = res.message || "Settings saved!";
                            alertEl.classList.remove('d-none');
                            setTimeout(() => alertEl.classList.add('d-none'), 3000);
                        }
                        window.showToast("System settings updated successfully!", "success");
                    } else {
                        window.showToast(res.message || "Failed to update settings.", "danger");
                    }
                })
                .catch(err => {
                    if (btn) btn.disabled = false;
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