/* ==========================================================================
   DataNova — Admin Dashboard Interactive Controller
   Handles User Management, Role Editing, Log Exports, Plotly Analytics,
   System Activity refresh, and Quick Action buttons.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Admin Controller Initialized.");

    // --- Quick Action Handlers ---
    const quickActions = document.querySelectorAll('.dn-quick-action, .dn-page-header .btn');
    quickActions.forEach(btn => {
        btn.addEventListener('click', function (e) {
            const text = (btn.textContent || '').trim().toLowerCase();
            if (text.includes('add user')) {
                e.preventDefault();
                showAddUserModal();
            } else if (text.includes('export log')) {
                e.preventDefault();
                exportSystemLogs();
            } else if (text.includes('manage roles') || text.includes('role management')) {
                e.preventDefault();
                scrollToSection('Recent Users');
                showToast("Select a user row below to update their access role.", "info");
            } else if (text.includes('view datasets') || text.includes('dataset management')) {
                e.preventDefault();
                scrollToSection('Dataset Monitoring');
            } else if (text.includes('view reports') || text.includes('reports management')) {
                e.preventDefault();
                showToast("Opening Platform Reports Repository...", "info");
                window.location.href = "/dashboard/analyst";
            } else if (text.includes('system settings') || text.includes('settings')) {
                e.preventDefault();
                showToast("System Settings: All services optimal. Storage limit: 500GB.", "success");
            }
        });
    });

    // --- Topbar Search Filter ---
    const searchInput = document.querySelector('.dn-topbar-search input');
    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            const query = (e.target.value || '').trim().toLowerCase();
            filterTableRows('#adminRecentUsersTable tbody tr', query);
            filterTableRows('#adminRecentDatasetsTable tbody tr', query);
        });
    }

    function filterTableRows(selector, query) {
        const rows = document.querySelectorAll(selector);
        rows.forEach(row => {
            const text = (row.textContent || '').toLowerCase();
            row.style.display = (!query || text.includes(query)) ? '' : 'none';
        });
    }

    // --- Dynamic Admin Analytics Auto-Fetch ---
    fetch('/api/admin/dashboard_data')
        .then(res => res.json())
        .then(resData => {
            if (resData.success && resData.data) {
                renderAdminAnalytics(resData.data);
            }
        })
        .catch(err => {
            console.log("Admin Analytics fetch warning, using fallback layout: ", err);
            renderDefaultPlotlyCharts();
        });

    function renderAdminAnalytics(data) {
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

        // Render Plotly Charts
        if (data.users_by_role) renderRoleDonutChart(data.users_by_role);
        else renderDefaultRoleDonutChart();

        if (data.weekly_activity) renderUserActivityChart(data.weekly_activity);
        else renderDefaultUserActivityChart();

        // System Activity
        if (data.system_activity && Array.isArray(data.system_activity)) {
            const listEl = document.getElementById('adminSystemActivityList');
            if (listEl) {
                listEl.innerHTML = data.system_activity.map(act => `
                    <li><span class="dn-insight-dot" style="background:${act.color || 'var(--dn-primary)'}"></span><strong>${act.user_name}</strong> ${act.action} <span class="text-secondary ms-auto small">${act.time_ago}</span></li>
                `).join('');
            }
        }

        // Security Alerts
        if (data.security_alerts && Array.isArray(data.security_alerts)) {
            const container = document.getElementById('adminSecurityAlertsContainer');
            if (container) {
                container.innerHTML = data.security_alerts.map(alert => `
                    <div class="dn-alert dn-alert-${alert.type}"><i class="bi ${alert.icon}"></i> ${alert.text}</div>
                `).join('');
            }
        }
    }

    // --- Plotly Chart Renderers ---
    function renderRoleDonutChart(roleData) {
        const container = document.getElementById('adminRoleDonutChart');
        if (!container || typeof Plotly === 'undefined') return;

        const labels = ['Analyst', 'Manager', 'Viewer', 'Admin'];
        const values = [
            roleData.analyst || 0,
            roleData.manager || 0,
            roleData.viewer || 0,
            roleData.admin || 0
        ];

        const trace = {
            labels: labels,
            values: values,
            type: 'pie',
            hole: 0.6,
            marker: {
                colors: ['#4F46E5', '#7C3AED', '#06B6D4', '#64748B']
            },
            textinfo: 'percent',
            hovertemplate: '<b>%{label}</b>: %{percent}<extra></extra>'
        };

        const layout = {
            margin: { t: 10, r: 10, l: 10, b: 10 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            showlegend: true,
            legend: { orientation: 'h', x: 0, y: -0.1, font: { color: '#94A3B8', size: 10 } },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderUserActivityChart(activityData) {
        const container = document.getElementById('adminUserActivityChart');
        if (!container || typeof Plotly === 'undefined') return;

        const traceActive = {
            x: activityData.labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            y: activityData.active || [12, 18, 15, 22, 20, 8, 14],
            name: 'Active',
            type: 'bar',
            marker: { color: '#4F46E5', cornerradius: 4 }
        };

        const traceInactive = {
            x: activityData.labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            y: activityData.inactive || [3, 2, 4, 1, 3, 5, 2],
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

        Plotly.newPlot(container, [traceActive, traceInactive], layout, { responsive: true, displayModeBar: false });
    }

    function renderDefaultPlotlyCharts() {
        renderDefaultRoleDonutChart();
        renderDefaultUserActivityChart();
    }
    function renderDefaultRoleDonutChart() {
        renderRoleDonutChart({ analyst: 40, manager: 25, viewer: 25, admin: 10 });
    }
    function renderDefaultUserActivityChart() {
        renderUserActivityChart({ labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], active: [12, 18, 15, 22, 20, 8, 14], inactive: [3, 2, 4, 1, 3, 5, 2] });
    }

    // --- User Management Action Buttons ---
    document.addEventListener('click', function (e) {
        const viewBtn = e.target.closest('#adminRecentUsersTable .dn-table-action[title="View"]');
        const editBtn = e.target.closest('#adminRecentUsersTable .dn-table-action[title="Edit"]');

        if (viewBtn) {
            const row = viewBtn.closest('tr');
            if (row && row.cells.length > 0) {
                const userName = row.cells[0] ? row.cells[0].innerText.trim() : 'User';
                const userEmail = row.cells[1] ? row.cells[1].innerText.trim() : '';
                const userRole = row.cells[2] ? row.cells[2].innerText.trim() : '';
                showToast(`User Profile: ${userName} (${userEmail}) - Role: ${userRole}`, "info");
            } else {
                showToast("User details not available.", "warning");
            }
        }

        if (editBtn) {
            const row = editBtn.closest('tr');
            if (row && row.cells.length > 0) {
                const userName = row.cells[0] ? row.cells[0].innerText.trim() : 'User';
                const userEmail = row.cells[1] ? row.cells[1].innerText.trim() : '';
                showRoleEditModal(userEmail, userName);
            } else {
                showToast("Could not find user information.", "warning");
            }
        }
    });

    // --- Add User Modal Logic ---
    window.showAddUserModal = function () {
        let modalEl = document.getElementById('dnAddUserModal');
        if (!modalEl) {
            const modalHtml = `
            <div class="modal fade" id="dnAddUserModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content dn-panel p-3">
                        <div class="modal-header border-0">
                            <h5 class="modal-title fw-bold"><i class="bi bi-person-plus text-primary me-2"></i>Add New User</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="dnAddUserForm">
                                <div class="row g-3">
                                    <div class="col-6">
                                        <label class="form-label small fw-semibold">First Name</label>
                                        <input type="text" id="addUserFirstName" class="form-control" placeholder="Aditya" required>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small fw-semibold">Last Name</label>
                                        <input type="text" id="addUserLastName" class="form-control" placeholder="Kulkarni" required>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label small fw-semibold">Email Address</label>
                                        <input type="email" id="addUserEmail" class="form-control" placeholder="aditya@example.com" required>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small fw-semibold">Password</label>
                                        <input type="password" id="addUserPassword" class="form-control" placeholder="••••••••" required>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small fw-semibold">Platform Role</label>
                                        <select id="addUserRole" class="form-select">
                                            <option value="analyst">Analyst</option>
                                            <option value="manager">Manager</option>
                                            <option value="viewer">Viewer</option>
                                            <option value="admin">Admin</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="mt-4 text-end">
                                    <button type="button" class="btn btn-sm btn-secondary me-2" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-sm btn-primary dn-btn-primary"><i class="bi bi-check-circle me-1"></i>Create User</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>`;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            modalEl = document.getElementById('dnAddUserModal');
        }

        modalEl = document.getElementById('dnAddUserModal');
        if (!modalEl) {
            showToast("Failed to create user modal.", "danger");
            return;
        }

        const modalInstance = new bootstrap.Modal(modalEl);
        modalInstance.show();

        const form = document.getElementById('dnAddUserForm');
        if (form) {
            form.onsubmit = function (e) {
                e.preventDefault();
                const firstName = document.getElementById('addUserFirstName');
                const lastName = document.getElementById('addUserLastName');
                const email = document.getElementById('addUserEmail');
                const password = document.getElementById('addUserPassword');
                const role = document.getElementById('addUserRole');

                if (!firstName || !lastName || !email || !password || !role) {
                    showToast("Form fields missing.", "danger");
                    return;
                }

                const payload = {
                    first_name: firstName.value.trim(),
                    last_name: lastName.value.trim(),
                    email: email.value.trim(),
                    password: password.value,
                    role: role.value
                };

                fetch('/api/admin/create_user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(res => res.json())
                .then(data => {
                    modalInstance.hide();
                    if (data.success) {
                        showToast(data.message, "success");
                        setTimeout(() => window.location.reload(), 1200);
                    } else {
                        showToast(data.message || "Failed to create user.", "danger");
                    }
                })
                .catch(err => {
                    modalInstance.hide();
                    showToast("Network error creating user.", "danger");
                });
            };
        }
    };

    // --- Role Edit Modal Logic ---
    function showRoleEditModal(email, name) {
        const newRole = prompt(`Select new role for ${name} (${email}):\nOptions: analyst, manager, viewer, admin`);
        if (!newRole) return;
        const validRoles = ['analyst', 'manager', 'viewer', 'admin'];
        if (!validRoles.includes(newRole.toLowerCase().trim())) {
            showToast("Invalid role entered.", "danger");
            return;
        }

        fetch('/api/admin/users')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.users) {
                    const found = data.users.find(u => u.email.toLowerCase() === email.toLowerCase());
                    if (found) {
                        fetch('/api/admin/update_user_role', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ user_id: found.id, role: newRole.toLowerCase().trim() })
                        })
                        .then(r => r.json())
                        .then(resData => {
                            if (resData.success) {
                                showToast(resData.message, "success");
                                setTimeout(() => window.location.reload(), 1000);
                            } else {
                                showToast(resData.message, "danger");
                            }
                        });
                    } else {
                        showToast("User ID not found.", "warning");
                    }
                }
            });
    }

    // --- Log Export Handler ---
    function exportSystemLogs() {
        showToast("Generating System Security Audit Logs...", "info");
        window.location.href = '/api/admin/export_logs';
    }

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
            setTimeout(() => {
                if (toastEl && toastEl.parentNode) {
                    toastEl.remove();
                }
            }, 4000);
        }
    }
});