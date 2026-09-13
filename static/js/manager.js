/* ==========================================================================
   DataNova — Manager Dashboard Interactive Controller
   Handles Team Management, Task Delegation, Live Workload Metrics,
   Plotly Analytics, Dataset Comparison, and Quick Action Triggers.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    console.log("DataNova Manager Controller Initialized.");

    // Global Modal References
    let addMemberModalInstance = null;
    let assignTaskModalInstance = null;
    let reopenTaskModalInstance = null;

    const addMemberModalEl = document.getElementById('dnAddTeamMemberModal');
    if (addMemberModalEl) {
        addMemberModalInstance = new bootstrap.Modal(addMemberModalEl);
    }

    const assignTaskModalEl = document.getElementById('dnAssignTaskModal');
    if (assignTaskModalEl) {
        assignTaskModalInstance = new bootstrap.Modal(assignTaskModalEl);
    }

    const reopenTaskModalEl = document.getElementById('reopenTaskModal');
    if (reopenTaskModalEl) {
        reopenTaskModalInstance = new bootstrap.Modal(reopenTaskModalEl);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // --- Action Triggers (Event Delegation) ---
    document.body.addEventListener('click', function (e) {
        const trigger = e.target.closest('[data-action]');
        if (!trigger) return;

        const action = trigger.getAttribute('data-action');

        switch (action) {
            case 'add-member':
            case 'add-team-member':
                e.preventDefault();
                showAddMemberModal();
                break;

            case 'quick-add-to-team':
                e.preventDefault();
                const qUserId = trigger.getAttribute('data-user-id');
                const qUserName = trigger.getAttribute('data-user-name');
                quickAddToTeam(qUserId, qUserName, trigger);
                break;

            case 'remove-team-member':
                e.preventDefault();
                const remMemberId = trigger.getAttribute('data-member-id');
                const remMemberName = trigger.getAttribute('data-member-name');
                removeTeamMember(remMemberId, remMemberName);
                break;

            case 'assign-task':
                e.preventDefault();
                showAssignTaskModal();
                break;

            case 'assign-task-to':
                e.preventDefault();
                const memberId = trigger.getAttribute('data-member-id');
                showAssignTaskModal(memberId);
                break;

            case 'reopen-task-modal':
                e.preventDefault();
                const rTaskId = trigger.getAttribute('data-task-id');
                const rTaskTitle = trigger.getAttribute('data-task-title') || 'Task';
                const rAssignee = trigger.getAttribute('data-assigned-to') || 'Team Member';
                showReopenTaskModal(rTaskId, rTaskTitle, rAssignee);
                break;

            case 'update-task-status':
                e.preventDefault();
                const taskId = trigger.getAttribute('data-task-id');
                const newStatus = trigger.getAttribute('data-status');
                updateTaskStatus(taskId, newStatus);
                break;

            case 'delete-task':
                e.preventDefault();
                const delTaskId = trigger.getAttribute('data-task-id');
                deleteTask(delTaskId);
                break;

            case 'toggle-status':
                e.preventDefault();
                const memId = trigger.getAttribute('data-member-id');
                const currStatus = trigger.getAttribute('data-current-status');
                toggleMemberStatus(memId, currStatus);
                break;

            case 'view-dashboard':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('dashboardOverviewSection'), trigger);
                break;

            case 'view-business':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('businessOverviewSection'), trigger);
                break;

            case 'view-datasets':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('datasetsOverviewSection'), trigger);
                break;

            case 'view-team':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('teamSection'), trigger);
                break;

            case 'view-tasks':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('taskSection'), trigger);
                break;

            case 'view-shared':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('sharedDashboardsSection'), trigger);
                break;

            case 'compare-data':
                e.preventDefault();
                showCompareDatasetsModal();
                break;

            case 'view-reports':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('reportsSection'), trigger);
                break;

            case 'ai-insights':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('aiInsightsSection'), trigger);
                break;

            case 'view-trends':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('trendsSection'), trigger);
                break;

            case 'view-predictions':
                e.preventDefault();
                smoothScrollToElement(document.getElementById('predictionsSection'), trigger);
                break;

            case 'help':
                e.preventDefault();
                showToast("Manager Help: Delegate tasks, monitor real-time workloads, and review AI insights.", "info");
                break;
        }
    });

    // --- Modal Handler Functions ---
    let compareDatasetsModalInstance = null;
    const compareModalEl = document.getElementById('dnCompareDatasetsModal');
    if (compareModalEl) {
        compareDatasetsModalInstance = new bootstrap.Modal(compareModalEl);
    }

    function showCompareDatasetsModal() {
        if (!compareDatasetsModalInstance && compareModalEl) {
            compareDatasetsModalInstance = new bootstrap.Modal(compareModalEl);
        }
        if (compareDatasetsModalInstance) {
            const form = document.getElementById('dnCompareDatasetsForm');
            if (form) form.reset();
            const alertEl = document.getElementById('compareDatasetsAlert');
            if (alertEl) alertEl.classList.add('d-none');
            const resContainer = document.getElementById('compareResultsContainer');
            if (resContainer) resContainer.classList.add('d-none');
            compareDatasetsModalInstance.show();
        } else {
            showToast("Comparison feature initialized.", "info");
        }
    }

    const compareForm = document.getElementById('dnCompareDatasetsForm');
    if (compareForm) {
        compareForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const ds1 = (document.getElementById('compareDs1Input').value || '').trim();
            const ds2 = (document.getElementById('compareDs2Input').value || '').trim();
            const alertEl = document.getElementById('compareDatasetsAlert');
            const btnSubmit = document.getElementById('btnSubmitCompare');

            if (!ds1 || !ds2) {
                showFormAlert(alertEl, "Please enter two dataset IDs to compare.");
                return;
            }

            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Comparing...';
            }

            fetch('/api/compare_datasets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dataset_id_1: ds1, dataset_id_2: ds2 })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const resContainer = document.getElementById('compareResultsContainer');
                        if (resContainer) {
                            resContainer.classList.remove('d-none');
                            document.getElementById('compHeadDs1').textContent = data.dataset1.name || `Dataset #${ds1}`;
                            document.getElementById('compHeadDs2').textContent = data.dataset2.name || `Dataset #${ds2}`;
                            document.getElementById('compRows1').textContent = (data.dataset1.rows || 0).toLocaleString();
                            document.getElementById('compRows2').textContent = (data.dataset2.rows || 0).toLocaleString();
                            document.getElementById('compCols1').textContent = (data.dataset1.cols || 0).toLocaleString();
                            document.getElementById('compCols2').textContent = (data.dataset2.cols || 0).toLocaleString();
                            document.getElementById('compMiss1').textContent = (data.dataset1.missing || 0).toLocaleString();
                            document.getElementById('compMiss2').textContent = (data.dataset2.missing || 0).toLocaleString();

                            const commonTxt = document.getElementById('compCommonColsText');
                            if (commonTxt) {
                                commonTxt.textContent = `Common overlapping columns count: ${data.common_columns_count || 0}`;
                            }
                        }
                        if (alertEl) alertEl.classList.add('d-none');
                        showToast("Dataset comparison complete!", "success");
                    } else {
                        showFormAlert(alertEl, data.message || "Failed to compare datasets.");
                    }
                })
                .catch(err => {
                    showFormAlert(alertEl, "Network error during comparison.");
                })
                .finally(() => {
                    if (btnSubmit) {
                        btnSubmit.disabled = false;
                        btnSubmit.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i>Run Comparison';
                    }
                });
        });
    }
    function showAddMemberModal() {
        if (!addMemberModalInstance && addMemberModalEl) {
            addMemberModalInstance = new bootstrap.Modal(addMemberModalEl);
        }
        if (addMemberModalInstance) {
            const form = document.getElementById('dnAddTeamMemberForm');
            if (form) form.reset();
            const alertEl = document.getElementById('addTeamMemberAlert');
            if (alertEl) alertEl.classList.add('d-none');
            addMemberModalInstance.show();
        }
    }

    function showAssignTaskModal(preselectMemberId = null) {
        if (!assignTaskModalInstance && assignTaskModalEl) {
            assignTaskModalInstance = new bootstrap.Modal(assignTaskModalEl);
        }
        if (assignTaskModalInstance) {
            const form = document.getElementById('dnAssignTaskForm');
            if (form) form.reset();
            const alertEl = document.getElementById('assignTaskAlert');
            if (alertEl) alertEl.classList.add('d-none');

            if (preselectMemberId) {
                const selectEl = document.getElementById('taskAssignedToSelect');
                if (selectEl) selectEl.value = preselectMemberId;
            }

            assignTaskModalInstance.show();
        }
    }

    // --- Form Submission Handlers ---
    const addMemberForm = document.getElementById('dnAddTeamMemberForm');
    if (addMemberForm) {
        addMemberForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const alertEl = document.getElementById('addTeamMemberAlert');
            const submitBtn = document.getElementById('btnSubmitAddMember');

            const payload = {
                first_name: document.getElementById('tmFirstName').value.trim(),
                last_name: document.getElementById('tmLastName').value.trim(),
                email: document.getElementById('tmEmail').value.trim(),
                password: document.getElementById('tmPassword').value.trim(),
                role: document.getElementById('tmRole').value
            };

            if (!payload.first_name || !payload.last_name || !payload.email || !payload.password) {
                showFormAlert(alertEl, "All fields are required.");
                return;
            }

            if (payload.password.length < 6) {
                showFormAlert(alertEl, "Password must be at least 6 characters.");
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creating...';
            }

            fetch('/api/manager/add_team_member', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (addMemberModalInstance) addMemberModalInstance.hide();
                        showToast(data.message || "Team member account created successfully!", "success");
                        refreshTeamData();
                    } else {
                        showFormAlert(alertEl, data.message || "Failed to create team member.");
                    }
                })
                .catch(err => {
                    showFormAlert(alertEl, "Network error while creating account.");
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-person-check me-1"></i>Create Account';
                    }
                });
        });
    }

    const assignTaskForm = document.getElementById('dnAssignTaskForm');
    if (assignTaskForm) {
        assignTaskForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const alertEl = document.getElementById('assignTaskAlert');
            const submitBtn = document.getElementById('btnSubmitAssignTask');

            const assignedToId = document.getElementById('taskAssignedToSelect').value;
            const taskTitle = document.getElementById('taskTitleInput').value.trim();
            const priority = document.getElementById('taskPrioritySelect').value;
            const dueDate = document.getElementById('taskDueDateInput').value;
            const description = document.getElementById('taskDescInput').value.trim();
            const fileInput = document.getElementById('taskDatasetFileInput');
            const existingDsSelect = document.getElementById('taskExistingDatasetSelect');

            if (!assignedToId || !taskTitle) {
                showFormAlert(alertEl, "Please select a team member and enter a task title.");
                return;
            }

            const formData = new FormData();
            formData.append('assigned_to_id', assignedToId);
            formData.append('task_title', taskTitle);
            formData.append('priority', priority);
            formData.append('due_date', dueDate);
            formData.append('description', description);

            if (fileInput && fileInput.files && fileInput.files[0]) {
                formData.append('file', fileInput.files[0]);
            } else if (existingDsSelect && existingDsSelect.value) {
                formData.append('dataset_id', existingDsSelect.value);
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Assigning...';
            }

            fetch('/api/manager/assign_task', {
                method: 'POST',
                body: formData
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (assignTaskModalInstance) assignTaskModalInstance.hide();
                        showToast(data.message || "Task assigned successfully!", "success");
                        assignTaskForm.reset();
                        refreshTeamData();
                    } else {
                        showFormAlert(alertEl, data.message || "Failed to assign task.");
                    }
                })
                .catch(err => {
                    showFormAlert(alertEl, "Network error while assigning task.");
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-1"></i>Assign Workload';
                    }
                });
        });
    }

    // --- Reopen Task Modal Helpers ---
    function showReopenTaskModal(taskId, title, assignee) {
        if (!reopenTaskModalInstance && reopenTaskModalEl) {
            reopenTaskModalInstance = new bootstrap.Modal(reopenTaskModalEl);
        }
        const idInput = document.getElementById('reopenTaskId');
        const titleEl = document.getElementById('reopenTaskTitleText');
        const assigneeEl = document.getElementById('reopenTaskAssigneeText');
        const remarkInput = document.getElementById('reopenTaskRemark');

        if (idInput) idInput.value = taskId;
        if (titleEl) titleEl.textContent = title;
        if (assigneeEl) assigneeEl.textContent = assignee;
        if (remarkInput) remarkInput.value = '';

        if (reopenTaskModalInstance) reopenTaskModalInstance.show();
    }

    const reopenTaskForm = document.getElementById('reopenTaskForm');
    if (reopenTaskForm) {
        reopenTaskForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const taskId = document.getElementById('reopenTaskId').value;
            const remark = document.getElementById('reopenTaskRemark').value.trim();
            const submitBtn = document.getElementById('submitReopenTaskBtn');

            if (!remark) {
                showToast("Please enter a remark explaining why the task is being reopened.", "warning");
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Reopening...';
            }

            fetch('/api/manager/update_task_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: parseInt(taskId),
                    status: 'Reopened',
                    remark: remark
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || "Task re-opened with your remarks!", "success");
                    if (reopenTaskModalInstance) reopenTaskModalInstance.hide();
                    refreshTeamData();
                    if (window.DataNovaStateBus) {
                        window.DataNovaStateBus.notify('MUTATION_TASK_UPDATE', { task_id: taskId, status: 'Reopened', remark: remark });
                    }
                } else {
                    showToast(data.message || "Failed to reopen task.", "danger");
                }
            })
            .catch(err => {
                console.error("Reopen task error:", err);
                showToast("Network error while reopening task.", "danger");
            })
            .finally(() => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Confirm &amp; Re-open';
                }
            });
        });
    }

    // --- Task & Team Member Action Helpers ---
    function updateTaskStatus(taskId, status) {
        fetch('/api/manager/update_task_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: parseInt(taskId), status: status })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, "success");
                    refreshTeamData();
                } else {
                    showToast(data.message || "Failed to update task.", "danger");
                }
            })
            .catch(err => showToast("Network error updating task status.", "danger"));
    }

    function deleteTask(taskId) {
        if (!confirm("Are you sure you want to delete this assigned task?")) return;

        fetch(`/api/manager/delete_task/${taskId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, "success");
                    refreshTeamData();
                } else {
                    showToast(data.message || "Failed to delete task.", "danger");
                }
            })
            .catch(err => showToast("Network error deleting task.", "danger"));
    }

    function toggleMemberStatus(memberId, currentStatus) {
        const newStatus = (currentStatus === 'active') ? 'inactive' : 'active';
        fetch('/api/manager/update_team_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ member_id: parseInt(memberId), status: newStatus })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(`Team member status updated to ${newStatus}.`, "success");
                    refreshTeamData();
                } else {
                    showToast(data.message || "Failed to update status.", "danger");
                }
            })
            .catch(err => showToast("Network error updating status.", "danger"));
    }

    function quickAddToTeam(userId, userName, btnElement) {
        if (!userId) return;
        if (btnElement) {
            btnElement.disabled = true;
            btnElement.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Adding...';
        }

        fetch('/api/manager/add_team_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: parseInt(userId) })
        })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    showToast(`${userName || 'User'} has been added to your team squad!`, "success");
                    refreshTeamData();
                } else {
                    if (btnElement) {
                        btnElement.disabled = false;
                        btnElement.innerHTML = '<i class="bi bi-person-plus-fill me-1"></i> Add in Team';
                    }
                    showToast(res.message || "Failed to add member.", "danger");
                }
            })
            .catch(err => {
                if (btnElement) {
                    btnElement.disabled = false;
                    btnElement.innerHTML = '<i class="bi bi-person-plus-fill me-1"></i> Add in Team';
                }
                showToast("Network error adding team member.", "danger");
            });
    }

    // --- Fetch & Re-render Team & Task Tables Dynamically ---
    function refreshTeamData() {
        fetch('/api/manager/team')
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    renderTeamMembersTable(resData.members || []);
                    renderAvailableUsersTable(resData.available_users || []);
                    renderTasksTable(resData.tasks || []);
                    updateAssignTaskSelectOptions(resData.members || []);

                    const teamCount = (resData.members || []).length;
                    const availCount = (resData.available_users || []).length;

                    const tmBadge = document.getElementById('teamMembersBadge');
                    if (tmBadge) tmBadge.textContent = teamCount;

                    const avBadge = document.getElementById('availableUsersBadge');
                    if (avBadge) avBadge.textContent = availCount;

                    if (resData.stats) {
                        const s = resData.stats;
                        if (document.getElementById('kpiTeamMembersCount')) document.getElementById('kpiTeamMembersCount').textContent = s.total_members;
                        if (document.getElementById('kpiTaskCompletionRate')) document.getElementById('kpiTaskCompletionRate').textContent = s.completion_rate;
                        if (document.getElementById('kpiPendingTasksCount')) document.getElementById('kpiPendingTasksCount').textContent = s.pending_tasks;
                        if (document.getElementById('kpiTotalTasksCount')) document.getElementById('kpiTotalTasksCount').textContent = s.total_tasks;
                    }

                    if (resData.datasets) {
                        const dsSelect = document.getElementById('taskExistingDatasetSelect');
                        if (dsSelect) {
                            const curVal = dsSelect.value;
                            dsSelect.innerHTML = '<option value="">-- Select Active Dataset (Optional) --</option>' +
                                resData.datasets.map(d => `<option value="${d.id}">${escapeHtml(d.file_name)} (${d.row_count || 0} rows)</option>`).join('');
                            if (curVal) dsSelect.value = curVal;
                        }
                    }
                }
            })
            .catch(err => console.log("Error refreshing team data: ", err));
    }

    function renderTeamMembersTable(members) {
        const tbody = document.getElementById('managerTeamTableBody');
        if (!tbody) return;

        if (!members || members.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-4 text-muted">
                        <i class="bi bi-people fs-2 d-block mb-2 text-secondary opacity-50"></i>
                        <div class="fw-semibold">No team members added yet</div>
                        <p class="small text-muted mb-2">Select from the "Available Platform Users" tab to build your team squad.</p>
                        <button class="btn btn-sm dn-btn-primary" onclick="document.getElementById('availableUsersTabBtn').click()"><i class="bi bi-person-plus-fill me-1"></i> Browse Available Users</button>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = members.map(m => `
            <tr data-member-id="${m.id}">
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="dn-user-avatar-sm" style="width:32px;height:32px;border-radius:50%;background:rgba(99,102,241,0.15);color:var(--dn-primary);display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.85rem;">
                            ${(m.first_name || 'U')[0].toUpperCase()}
                        </div>
                        <div>
                            <div class="fw-semibold">${escapeHtml(m.first_name || '')} ${escapeHtml(m.last_name || '')}</div>
                            <div class="small text-secondary">${escapeHtml(m.email || '')}</div>
                        </div>
                    </div>
                </td>
                <td><span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">${escapeHtml((m.role || 'user').toUpperCase())}</span></td>
                <td><span class="badge ${m.status === 'active' ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-warning-subtle text-warning border border-warning-subtle'}">${escapeHtml(m.status || 'active')}</span></td>
                <td><span class="badge bg-primary-subtle text-primary border border-primary-subtle">${m.active_tasks || 0} active</span></td>
                <td><span class="badge bg-success-subtle text-success border border-success-subtle">${m.completed_tasks || 0} done</span></td>
                <td class="small text-secondary">${escapeHtml(m.joined_at || 'Recently')}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-primary me-1" data-action="assign-task-to" data-member-id="${m.id}" data-member-name="${escapeHtml(m.first_name || '')} ${escapeHtml(m.last_name || '')}"><i class="bi bi-plus-lg"></i> Task</button>
                    <button class="btn btn-sm btn-outline-danger" data-action="remove-member" data-member-id="${m.id}" data-member-name="${escapeHtml(m.first_name || '')} ${escapeHtml(m.last_name || '')}"><i class="bi bi-person-x"></i></button>
                </td>
            </tr>
        `).join('');
    }

    function renderAvailableUsersTable(users) {
        const tbody = document.getElementById('availableUsersTableBody');
        if (!tbody) return;

        if (!users || users.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-4 text-muted">
                        <i class="bi bi-check2-all fs-2 d-block mb-2 text-success opacity-50"></i>
                        <div class="fw-semibold">All active users are currently assigned to teams</div>
                        <p class="small text-muted mb-0">Use the registration form below to create new analyst or viewer accounts.</p>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = users.map(u => `
            <tr data-user-id="${u.id}">
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="dn-user-avatar-sm" style="width:32px;height:32px;border-radius:50%;background:rgba(14,165,233,0.15);color:var(--dn-cyan);display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.85rem;">
                            ${(u.first_name || 'U')[0].toUpperCase()}
                        </div>
                        <div>
                            <div class="fw-semibold">${escapeHtml(u.first_name || '')} ${escapeHtml(u.last_name || '')}</div>
                            <div class="small text-secondary">${escapeHtml(u.email || '')}</div>
                        </div>
                    </div>
                </td>
                <td><span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">${escapeHtml((u.role || 'user').toUpperCase())}</span></td>
                <td><span class="badge bg-success-subtle text-success border border-success-subtle">Active</span></td>
                <td class="small text-secondary">${escapeHtml(u.joined_at || 'Recently')}</td>
                <td class="text-end">
                    <button class="btn btn-sm dn-btn-primary btn-add-member" data-action="add-member" data-user-id="${u.id}"><i class="bi bi-person-plus-fill me-1"></i> Add in Team</button>
                </td>
            </tr>
        `).join('');
    }

    function renderTasksTable(tasks) {
        const tbody = document.getElementById('managerTaskTableBody');
        if (!tbody) return;

        if (!tasks || tasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-4 text-muted">
                        <i class="bi bi-check2-circle fs-3 d-block mb-1"></i> No tasks assigned yet. Click "Assign Task" to allocate workload.
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = tasks.map(t => {
            let priorityBadge = '<span class="badge bg-info-subtle text-info border border-info-subtle">Low</span>';
            if (t.priority === 'High') {
                priorityBadge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-exclamation-triangle me-1"></i>High</span>';
            } else if (t.priority === 'Medium') {
                priorityBadge = '<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Medium</span>';
            }

            let statusBadge = '<span class="badge bg-warning text-dark" style="background:#f59e0b"><i class="bi bi-clock me-1"></i>Pending</span>';
            if (t.status === 'Completed') {
                statusBadge = '<span class="badge bg-success text-white"><i class="bi bi-check-circle me-1"></i>Completed</span>';
            } else if (t.status === 'In Progress') {
                statusBadge = '<span class="badge bg-primary text-white"><i class="bi bi-hourglass-split me-1"></i>In Progress</span>';
            } else if (t.status === 'Reopened') {
                statusBadge = '<span class="badge bg-warning text-dark border border-warning-subtle"><i class="bi bi-arrow-counterclockwise me-1"></i>Reopened</span>';
            }

            const descHtml = t.description ? `<div class="small text-secondary text-truncate" style="max-width:250px;">${escapeHtml(t.description)}</div>` : '';
            const datasetBadge = t.dataset_file_name ? `<div class="small mt-1 text-primary d-inline-flex align-items-center bg-primary-subtle px-2 py-0 rounded border border-primary-subtle" style="font-size:0.75rem;"><i class="bi bi-file-earmark-spreadsheet me-1"></i>${escapeHtml(t.dataset_file_name)}</div>` : '';
            const remarkHtml = t.remark ? `<div class="small mt-1 p-1 px-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle" style="max-width:280px;"><i class="bi bi-chat-left-dots-fill me-1"></i><strong>Remark:</strong> ${escapeHtml(t.remark)}</div>` : '';

            let actionBtns = `
                <div class="btn-group btn-group-sm">
                    ${t.status !== 'Completed'
                ? `<button class="btn btn-outline-success" data-action="update-task-status" data-task-id="${t.id}" data-status="Completed"><i class="bi bi-check-lg"></i> Done</button>
                   <button class="btn btn-outline-primary" data-action="update-task-status" data-task-id="${t.id}" data-status="In Progress"><i class="bi bi-play-fill"></i> In Progress</button>`
                : `<button class="btn btn-outline-warning" data-action="reopen-task-modal" data-task-id="${t.id}" data-task-title="${escapeHtml(t.task_title || '')}" data-assigned-to="${escapeHtml(t.assigned_to_name || '')}"><i class="bi bi-arrow-counterclockwise"></i> Re-open</button>`}
                    <button class="btn btn-outline-danger" data-action="delete-task" data-task-id="${t.id}"><i class="bi bi-trash"></i></button>
                </div>`;

            return `
            <tr data-task-id="${t.id}">
                <td>
                    <div class="fw-semibold">${escapeHtml(t.task_title || '')}</div>
                    ${descHtml}
                    ${datasetBadge}
                    ${remarkHtml}
                </td>
                <td>
                    <div class="small fw-semibold">${escapeHtml(t.assigned_to_name || 'Member')}</div>
                    <div class="small text-secondary">${escapeHtml(t.assigned_to_email || '')}</div>
                </td>
                <td>${priorityBadge}</td>
                <td>${statusBadge}</td>
                <td class="small">${escapeHtml(t.due_date || 'Flexible')}</td>
                <td class="text-end">${actionBtns}</td>
            </tr>`;
        }).join('');
    }

    function updateAssignTaskSelectOptions(members) {
        const selectEl = document.getElementById('taskAssignedToSelect');
        if (!selectEl) return;
        const currentVal = selectEl.value;

        selectEl.innerHTML = '<option value="">-- Choose Member --</option>' +
            members.map(m => `<option value="${m.id}">${m.first_name || ''} ${m.last_name || ''} (${(m.role || 'user').toUpperCase()})</option>`).join('');

        if (currentVal) selectEl.value = currentVal;
    }

    // --- Search & Filter Listeners ---
    const teamSearchInput = document.getElementById('teamSearchInput');
    const teamRoleFilter = document.getElementById('teamRoleFilter');

    if (teamSearchInput) {
        teamSearchInput.addEventListener('input', filterTeamTable);
    }
    if (teamRoleFilter) {
        teamRoleFilter.addEventListener('change', filterTeamTable);
    }

    function filterTeamTable() {
        const query = (teamSearchInput ? teamSearchInput.value : '').toLowerCase().trim();
        const role = teamRoleFilter ? teamRoleFilter.value.toLowerCase() : 'all';

        ['managerTeamTableBody', 'managerAvailableUsersTableBody'].forEach(tbodyId => {
            const tbody = document.getElementById(tbodyId);
            if (!tbody) return;
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                if (row.querySelector('td[colspan]')) return;
                const text = row.textContent.toLowerCase();
                const roleBadge = row.querySelector('.dn-role-badge');
                const rowRole = roleBadge ? roleBadge.textContent.toLowerCase().trim() : '';

                const matchesQuery = !query || text.includes(query);
                const matchesRole = (role === 'all') || (rowRole === role);

                row.style.display = (matchesQuery && matchesRole) ? '' : 'none';
            });
        });
    }

    const refreshBtn = document.getElementById('refreshTeamBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshTeamData();
            showToast("Team roster refreshed.", "info");
        });
    }

    // --- Plotly Chart Auto-Fetch ---
    fetch('/api/manager/dashboard_data')
        .then(res => res.json())
        .then(resData => {
            if (resData.success && resData.data) {
                renderPlotlyCharts(resData.data);
            }
        })
        .catch(err => renderEmptyCharts());

    function renderPlotlyCharts(data) {
        if (data.revenue_trend) renderRevenueChart(data.revenue_trend);
        if (data.category_perf) renderCategoryChart(data.category_perf);
        if (data.sales_perf) renderSalesChart(data.sales_perf);
    }

    function renderRevenueChart(trendData) {
        const container = document.getElementById('managerRevenueChart');
        if (!container || typeof Plotly === 'undefined' || !trendData || !trendData.values) return;

        const trace = {
            x: trendData.labels || [],
            y: trendData.values || [],
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
            yaxis: { showgrid: true, gridcolor: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8', tickprefix: '₹' },
            autosize: true
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderCategoryChart(catData) {
        const container = document.getElementById('managerCategoryChart');
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

    function renderSalesChart(salesData) {
        const container = document.getElementById('managerSalesChart');
        if (!container || typeof Plotly === 'undefined' || !salesData || !salesData.values) return;

        const trace = {
            x: salesData.labels || [],
            y: salesData.values || [],
            type: 'bar',
            marker: { color: '#06B6D4' }
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

    function renderEmptyCharts() {
        ['managerRevenueChart', 'managerCategoryChart', 'managerSalesChart'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="p-3 text-center text-muted small"><i class="bi bi-info-circle me-1"></i> No chart metrics available.</div>';
        });
    }

    window.addEventListener('resize', function () {
        ['managerRevenueChart', 'managerCategoryChart', 'managerSalesChart'].forEach(id => {
            const el = document.getElementById(id);
            if (el && typeof Plotly !== 'undefined') {
                try { Plotly.Plots.resize(el); } catch (e) { }
            }
        });
    });

    // Helper functions
    function showFormAlert(alertEl, msg) {
        if (!alertEl) return;
        alertEl.textContent = msg;
        alertEl.classList.remove('d-none');
    }

    function smoothScrollToElement(targetEl, linkEl) {
        if (!targetEl) return;

        // Update active class on sidebar navigation links
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

        // Trigger pulse glow animation
        targetEl.classList.remove('dn-section-highlight');
        void targetEl.offsetWidth; // force reflow
        targetEl.classList.add('dn-section-highlight');
        setTimeout(() => targetEl.classList.remove('dn-section-highlight'), 1600);

        // Auto-close sidebar on mobile viewports
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

    // Direct Anchor Click binding for all Sidebar Nav links
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

    // ScrollSpy observer to automatically update active sidebar item on scroll
    const managerSectionIds = [
        'dashboardOverviewSection',
        'businessOverviewSection',
        'datasetsOverviewSection',
        'teamSection',
        'taskSection',
        'sharedDashboardsSection',
        'aiInsightsSection',
        'trendsSection',
        'predictionsSection',
        'reportsSection'
    ];

    let scrollTimeout = null;
    window.addEventListener('scroll', function () {
        if (scrollTimeout) return;
        scrollTimeout = setTimeout(function () {
            scrollTimeout = null;
            const scrollPos = window.pageYOffset + 140;

            let currentSectionId = null;
            for (let i = 0; i < managerSectionIds.length; i++) {
                const el = document.getElementById(managerSectionIds[i]);
                if (el) {
                    const top = el.offsetTop;
                    const height = el.offsetHeight;
                    if (scrollPos >= top && scrollPos < top + height) {
                        currentSectionId = managerSectionIds[i];
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

    // Global State Bus Listener for Manager Dashboard
    if (window.DataNovaStateBus) {
        window.DataNovaStateBus.on('*', function (eventType) {
            if (eventType !== 'MUTATION_MANAGER_FETCH') {
                console.log("Manager Dashboard syncing with Global State Bus:", eventType);
                refreshTeamData();
            }
        });
    }

    // --- Add Team Member Modal Controller ---
    window.showAddMemberModal = function () {
        const modalEl = document.getElementById('dnAddTeamMemberModal');
        if (!modalEl) return;
        const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
        modalInstance.show();

        const userSelect = document.getElementById('addMemberUserSelect');
        if (userSelect) {
            fetch('/api/manager/available_users')
                .then(r => r.json())
                .then(res => {
                    if (res.success && Array.isArray(res.users) && res.users.length > 0) {
                        userSelect.innerHTML = '<option value="">-- Select Registered Active User --</option>' +
                            res.users.map(u => `<option value="${u.id}">${u.first_name} ${u.last_name || ''} (${u.email}) - ${(u.role || 'Analyst').toUpperCase()}</option>`).join('');
                    } else {
                        userSelect.innerHTML = '<option value="" disabled selected>No unassigned active users available. (Use Register New User below)</option>';
                    }
                })
                .catch(err => {
                    console.error("Error loading available users:", err);
                    if (userSelect.options.length <= 1) {
                        userSelect.innerHTML = '<option value="" disabled selected>Error loading users. Try again.</option>';
                    }
                });
        }
    };

    window.toggleNewMemberFields = function () {
        const newBlock = document.getElementById('newMemberFieldsBlock');
        const btn = document.getElementById('toggleNewUserFormBtn');
        if (newBlock) {
            newBlock.classList.toggle('d-none');
            if (btn) {
                btn.innerHTML = newBlock.classList.contains('d-none') ?
                    '<i class="bi bi-person-plus-fill me-1"></i>Or Register New User Account' :
                    '<i class="bi bi-x-circle me-1"></i>Cancel New User Form';
            }
        }
    };

    // --- Remove Team Member Function ---
    window.removeTeamMember = function (memberId, memberName) {
        if (!memberId) return;
        const nameStr = memberName ? `"${memberName}"` : `Member ID #${memberId}`;
        if (!confirm(`Are you sure you want to remove ${nameStr} from your team roster?`)) return;

        fetch('/api/manager/remove_team_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ member_id: memberId })
        })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    showToast(res.message || "Team member removed from roster.", "success");
                    refreshTeamData();
                } else {
                    showToast(res.message || "Failed to remove team member.", "danger");
                }
            })
            .catch(err => {
                console.error("Error removing team member:", err);
                showToast("Network error removing team member.", "danger");
            });
    };

    // --- Add Team Member Form Listener ---
    const addTeamMemberForm = document.getElementById('dnAddTeamMemberForm');
    if (addTeamMemberForm) {
        addTeamMemberForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const errorAlert = document.getElementById('addMemberErrorAlert');
            if (errorAlert) {
                errorAlert.classList.add('d-none');
                errorAlert.textContent = '';
            }

            const selectedUserId = document.getElementById('addMemberUserSelect') ? document.getElementById('addMemberUserSelect').value : '';
            const newBlock = document.getElementById('newMemberFieldsBlock');
            const isNewUserMode = newBlock && !newBlock.classList.contains('d-none');

            let payload = {};

            if (selectedUserId) {
                payload = { user_id: selectedUserId };
            } else if (isNewUserMode) {
                const fn = document.getElementById('addMemberFirstName').value.trim();
                const ln = document.getElementById('addMemberLastName').value.trim();
                const email = document.getElementById('addMemberEmail').value.trim();
                const password = document.getElementById('addMemberPassword').value;
                const role = document.getElementById('addMemberRole').value;

                if (!fn || !email || !password) {
                    if (errorAlert) {
                        errorAlert.textContent = "Please fill in First Name, Email, and Password for new user.";
                        errorAlert.classList.remove('d-none');
                    }
                    return;
                }
                payload = { first_name: fn, last_name: ln, email: email, password: password, role: role };
            } else {
                if (errorAlert) {
                    errorAlert.textContent = "Please select an active platform user from the dropdown list.";
                    errorAlert.classList.remove('d-none');
                }
                return;
            }

            const btn = document.getElementById('btnSubmitAddMember');
            if (btn) btn.disabled = true;

            fetch('/api/manager/add_team_member', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(res => {
                    if (btn) btn.disabled = false;
                    if (res.success) {
                        const modalEl = document.getElementById('dnAddTeamMemberModal');
                        if (modalEl) {
                            const inst = bootstrap.Modal.getInstance(modalEl);
                            if (inst) inst.hide();
                        }
                        showToast(res.message || "User added to team roster successfully!", "success");
                        addTeamMemberForm.reset();
                        refreshTeamData();
                    } else {
                        if (errorAlert) {
                            errorAlert.textContent = res.message || "Failed to add team member.";
                            errorAlert.classList.remove('d-none');
                        }
                    }
                })
                .catch(err => {
                    if (btn) btn.disabled = false;
                    console.error("Add team member error:", err);
                    showToast("Network error adding team member.", "danger");
                });
        });
    }

    /* ---------------------------------------------------------------------
       10. Manager Shared Dashboards & Collaborative Reviews
       ------------------------------------------------------------------- */
    const sharedDetailModalEl = document.getElementById('sharedDashboardDetailModal');
    let sharedDetailModalInstance = null;
    if (sharedDetailModalEl) {
        sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
    }

    function fetchManagerSharedDashboards() {
        const loadingEl = document.getElementById('managerSharedLoading');
        const container = document.getElementById('managerSharedCardsContainer');

        if (loadingEl) loadingEl.style.display = 'block';

        fetch('/api/shared_dashboards/list')
            .then(res => res.json())
            .then(data => {
                if (loadingEl) loadingEl.style.display = 'none';
                if (data.success && data.dashboards) {
                    renderManagerSharedDashboards(data.dashboards);
                } else {
                    if (container) {
                        container.innerHTML = `<div class="col-12"><div class="alert alert-warning">${escapeHtml(data.message || 'Could not load shared dashboards.')}</div></div>`;
                    }
                }
            })
            .catch(err => {
                if (loadingEl) loadingEl.style.display = 'none';
                console.error('Error fetching manager shared dashboards:', err);
            });
    }

    function renderManagerSharedDashboards(dashboards) {
        const container = document.getElementById('managerSharedCardsContainer');
        if (!container) return;

        if (!dashboards || dashboards.length === 0) {
            container.innerHTML = `
                <div class="col-12">
                    <div class="p-4 text-center text-secondary border rounded bg-body-tertiary">
                        <i class="bi bi-share fs-2 mb-2 d-block text-muted"></i>
                        <div class="fw-medium">No shared dashboards yet</div>
                        <small>Dashboards shared by analysts and team members will appear here for review and remarks.</small>
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
                statusBadge = '<span class="badge bg-warning text-dark"><i class="bi bi-arrow-counterclockwise me-1"></i>Reopened for Revision</span>';
            } else if (sd.status === 'Reviewed') {
                statusBadge = '<span class="badge bg-info text-white"><i class="bi bi-chat-left-text me-1"></i>Reviewed</span>';
            }

            const remarkHtml = sd.remark ? `
                <div class="small mt-2 p-2 rounded bg-warning-subtle text-warning-emphasis border border-warning-subtle">
                    <i class="bi bi-chat-left-quote-fill me-1"></i><strong>Your Feedback:</strong> ${escapeHtml(sd.remark)}
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
                    <div class="dn-kpi-card h-100 d-flex flex-column justify-content-between p-3 border rounded shadow-sm">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="fw-bold mb-0 text-truncate" title="${escapeHtml(sd.title)}">${escapeHtml(sd.title)}</h6>
                                ${statusBadge}
                            </div>
                            <div class="small text-secondary mb-1"><i class="bi bi-person me-1"></i>Shared by: <strong>${escapeHtml(sd.owner_name)}</strong> (${escapeHtml(sd.owner_role)})</div>
                            <div class="small text-secondary mb-2"><i class="bi bi-database me-1"></i>${escapeHtml(sd.dataset_name)} &bull; ${Number(sd.row_count || 0).toLocaleString()} rows</div>
                            
                            <!-- Recipient Users List -->
                            <div class="small mb-2 p-2 rounded bg-body-tertiary border">
                                <span class="text-secondary d-block fw-semibold mb-1" style="font-size:0.75rem;"><i class="bi bi-people-fill text-primary me-1"></i>Shared With:</span>
                                <div class="d-flex flex-wrap gap-1">${recipientsHtml}</div>
                            </div>

                            ${sd.description ? `<p class="small text-muted mb-2 text-truncate" style="max-height:40px;">${escapeHtml(sd.description)}</p>` : ''}
                            ${remarkHtml}
                        </div>
                        <div class="pt-3 mt-2 border-top d-flex justify-content-between align-items-center">
                            <small class="text-secondary">${escapeHtml(sd.created_at_str)}</small>
                            <button class="btn btn-sm dn-btn-primary btn-mgr-view-shared" data-shared-id="${sd.id}">
                                <i class="bi bi-eye me-1"></i> Review &amp; Remarks
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach Review Handlers
        container.querySelectorAll('.btn-mgr-view-shared').forEach(btn => {
            btn.addEventListener('click', function() {
                const sharedId = this.getAttribute('data-shared-id');
                if (sharedId) {
                    openManagerSharedDetail(sharedId);
                }
            });
        });
    }

    function openManagerSharedDetail(sharedId) {
        if (!sharedDetailModalInstance && sharedDetailModalEl) {
            sharedDetailModalInstance = new bootstrap.Modal(sharedDetailModalEl);
        }

        const activeIdInput = document.getElementById('activeSharedDashboardId');
        if (activeIdInput) activeIdInput.value = sharedId;

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
                    const remarkInput = document.getElementById('managerReviewRemarkInput');

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

                    if (remarkInput) {
                        remarkInput.value = sd.remark || '';
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
                                    <h2 class="accordion-header" id="mgrSdQaHead${idx}">
                                        <button class="accordion-button ${idx === 0 ? '' : 'collapsed'} py-2 px-3 fw-semibold small bg-body-tertiary" type="button" data-bs-toggle="collapse" data-bs-target="#mgrSdQaCollapse${idx}" aria-expanded="${idx === 0 ? 'true' : 'false'}" aria-controls="mgrSdQaCollapse${idx}">
                                            <i class="bi ${qa.icon || 'bi-patch-question-fill'} text-primary me-2"></i>
                                            <span class="badge bg-secondary-subtle text-secondary me-2 extra-small">${escapeHtml(qa.category || 'Analysis')}</span>
                                            <span>${escapeHtml(qa.question)}</span>
                                        </button>
                                    </h2>
                                    <div id="mgrSdQaCollapse${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" aria-labelledby="mgrSdQaHead${idx}" data-bs-parent="#sdQaAccordion">
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

                    // 7. Python Pipeline Code
                    const sdCodeContainer = document.getElementById('sdPipelineCodeContainer');
                    if (sdCodeContainer) {
                        sdCodeContainer.textContent = sd.pipeline_code || '# Pipeline code is generating for this shared dataset...';
                    }

                    // Copy code button in shared modal
                    const btnCopySdCode = document.getElementById('btnCopySdCodeSnippet');
                    if (btnCopySdCode && !btnCopySdCode._hasListener) {
                        btnCopySdCode._hasListener = true;
                        btnCopySdCode.addEventListener('click', function () {
                            const codeText = sdCodeContainer ? sdCodeContainer.textContent : '';
                            if (codeText) {
                                navigator.clipboard.writeText(codeText).then(() => {
                                    showToast('Pipeline code copied to clipboard!', 'success');
                                }).catch(() => {
                                    showToast('Could not copy code to clipboard.', 'warning');
                                });
                            }
                        });
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

    function submitManagerDashboardReview(action) {
        const activeIdInput = document.getElementById('activeSharedDashboardId');
        const sharedId = activeIdInput ? activeIdInput.value : null;
        const remarkInput = document.getElementById('managerReviewRemarkInput');
        const remark = remarkInput ? remarkInput.value.trim() : '';

        if (!sharedId) {
            showToast('No active dashboard selected.', 'danger');
            return;
        }

        if (action === 'reopen' && !remark) {
            showToast('Please provide revision instructions / remarks when reopening.', 'warning');
            if (remarkInput) remarkInput.focus();
            return;
        }

        const btn = action === 'reopen' ? document.getElementById('btnManagerActionReopen') :
                    action === 'approve' ? document.getElementById('btnManagerActionApprove') :
                    document.getElementById('btnManagerActionSaveRemark');
        if (btn) btn.disabled = true;

        fetch('/api/shared_dashboard/manager_review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                shared_id: sharedId,
                action: action,
                remark: remark
            })
        })
        .then(res => res.json())
        .then(data => {
            if (btn) btn.disabled = false;
            if (data.success) {
                showToast(data.message || 'Review recorded successfully!', 'success');
                fetchManagerSharedDashboards();
                if (sharedDetailModalInstance) {
                    sharedDetailModalInstance.hide();
                }
            } else {
                if (btn) btn.disabled = false;
                showToast(data.message || 'Failed to submit review.', 'danger');
            }
        })
        .catch(err => {
            if (btn) btn.disabled = false;
            console.error('Error submitting review:', err);
            showToast('Network error while saving review.', 'danger');
        });
    }

    const btnSaveRemark = document.getElementById('btnManagerActionSaveRemark');
    if (btnSaveRemark) {
        btnSaveRemark.addEventListener('click', () => submitManagerDashboardReview('remark'));
    }
    const btnReopen = document.getElementById('btnManagerActionReopen');
    if (btnReopen) {
        btnReopen.addEventListener('click', () => submitManagerDashboardReview('reopen'));
    }
    const btnApprove = document.getElementById('btnManagerActionApprove');
    if (btnApprove) {
        btnApprove.addEventListener('click', () => submitManagerDashboardReview('approve'));
    }

    const refreshManagerSharedBtn = document.getElementById('refreshManagerSharedBtn');
    if (refreshManagerSharedBtn) {
        refreshManagerSharedBtn.addEventListener('click', function() {
            fetchManagerSharedDashboards();
        });
    }

    // Auto-fetch manager shared dashboards on load
    fetchManagerSharedDashboards();

    /* =====================================================================
       PYTHON CODE STUDIO & JUPYTER NOTEBOOK (.ipynb) SUITE (MANAGER)
       =================================================================== */
    const codeStudioModalEl = document.getElementById('pythonCodeStudioModal');
    let codeStudioModalInstance = null;
    if (codeStudioModalEl) {
        codeStudioModalInstance = new bootstrap.Modal(codeStudioModalEl);
    }

    let autoGeneratedPipelineCode = '';
    const codeEditorEl = document.getElementById('pythonStudioCodeEditor');
    const lineNumbersEl = document.getElementById('pythonStudioLineNumbers');
    const datasetBadgeEl = document.getElementById('codeStudioDatasetBadge');
    const roleBadgeEl = document.getElementById('codeStudioRoleBadge');
    const terminalOutputEl = document.getElementById('studioTerminalOutput');
    const plotsContainerEl = document.getElementById('studioPlotsContainer');
    const plotsBadgeEl = document.getElementById('studioPlotsBadge');
    const previewContainerEl = document.getElementById('studioPreviewTableContainer');
    const dfShapeBadgeEl = document.getElementById('studioDfShapeBadge');
    const execStatusBannerEl = document.getElementById('studioExecutionStatusBanner');
    const execTimeBadgeEl = document.getElementById('studioExecTimeBadge');
    const btnRunCode = document.getElementById('btnRunStudioCode');
    const btnCopyCode = document.getElementById('btnCopyStudioCode');
    const btnResetCode = document.getElementById('btnResetStudioCode');
    const btnDownloadIpynb = document.getElementById('btnDownloadIpynbStudio');
    const btnDownloadPy = document.getElementById('btnDownloadPyStudio');
    const btnManagerOpenStudio = document.getElementById('btnManagerOpenCodeStudio');

    function updateManagerLineNumbers() {
        if (!codeEditorEl || !lineNumbersEl) return;
        const lines = (codeEditorEl.value || '').split('\n');
        const count = Math.max(1, lines.length);
        let numStr = '';
        for (let i = 1; i <= count; i++) {
            numStr += i + '\n';
        }
        lineNumbersEl.textContent = numStr;
        const lineBadge = document.getElementById('editorLineCountBadge');
        if (lineBadge) {
            lineBadge.textContent = `${count} line${count === 1 ? '' : 's'} | Ctrl+Enter to Run`;
        }
    }

    if (codeEditorEl) {
        codeEditorEl.addEventListener('input', updateManagerLineNumbers);
        codeEditorEl.addEventListener('scroll', function () {
            if (lineNumbersEl) lineNumbersEl.scrollTop = this.scrollTop;
        });
        codeEditorEl.addEventListener('keydown', function (e) {
            // Shortcut: Ctrl + Enter or Cmd + Enter to Run Code
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                executeManagerStudioCode();
                return;
            }
            // Tab key support: indent with 4 spaces
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.selectionStart;
                const end = this.selectionEnd;
                this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
                this.selectionStart = this.selectionEnd = start + 4;
                updateManagerLineNumbers();
            }
        });
    }

    function openManagerPythonCodeStudio(dsId) {
        const targetId = dsId || currentDatasetId;
        if (!targetId) {
            showToast('Please select or load an active dataset first to launch Python Code Studio.', 'warning');
            return;
        }

        if (!codeStudioModalInstance && codeStudioModalEl) {
            codeStudioModalInstance = new bootstrap.Modal(codeStudioModalEl);
        }

        if (datasetBadgeEl) datasetBadgeEl.textContent = 'Dataset ID: #' + targetId;
        if (codeEditorEl) {
            codeEditorEl.value = '# Fetching automated data science pipeline code...';
            updateManagerLineNumbers();
        }
        if (terminalOutputEl) terminalOutputEl.textContent = '# Ready for execution. Click "Run Code & Sync Vis" (or press Ctrl + Enter) to execute.';

        if (codeStudioModalInstance) {
            codeStudioModalInstance.show();
        }

        fetch(`/api/dataset/${targetId}/code`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.code) {
                    autoGeneratedPipelineCode = data.code;
                    if (codeEditorEl) {
                        codeEditorEl.value = data.code;
                        codeEditorEl.readOnly = !data.can_edit;
                        updateManagerLineNumbers();
                    }
                    if (datasetBadgeEl) datasetBadgeEl.textContent = `Dataset: ${data.dataset_name || '#' + targetId}`;
                    if (roleBadgeEl) {
                        roleBadgeEl.textContent = data.can_edit ? 'Manager Studio (Edit & Run)' : 'Viewer (Read-Only)';
                        roleBadgeEl.className = 'badge ' + (data.can_edit ? 'bg-primary-subtle text-primary border border-primary-subtle' : 'bg-secondary-subtle text-secondary border');
                    }
                    if (btnRunCode) btnRunCode.style.display = data.can_edit ? 'inline-block' : 'none';
                    if (btnResetCode) btnResetCode.style.display = data.can_edit ? 'inline-block' : 'none';
                } else {
                    if (codeEditorEl) {
                        codeEditorEl.value = '# Error generating pipeline code: ' + (data.message || 'Unknown error');
                        updateManagerLineNumbers();
                    }
                    showToast(data.message || 'Could not load pipeline code.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error fetching pipeline code:', err);
                if (codeEditorEl) {
                    codeEditorEl.value = '# Network error while fetching code.';
                    updateManagerLineNumbers();
                }
                showToast('Failed to load Python pipeline code.', 'danger');
            });
    }

    function executeManagerStudioCode() {
        const targetId = currentDatasetId;
        if (!targetId) {
            showToast('No active dataset found.', 'warning');
            return;
        }

        const codeContent = codeEditorEl ? codeEditorEl.value.trim() : '';
        if (!codeContent) {
            showToast('Code cannot be empty.', 'warning');
            return;
        }

        const startTime = Date.now();
        if (btnRunCode) {
            btnRunCode.disabled = true;
            btnRunCode.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Running...';
        }

        if (execStatusBannerEl) {
            execStatusBannerEl.className = 'alert alert-primary py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
            execStatusBannerEl.innerHTML = '<span><span class="spinner-border spinner-border-sm me-2" role="status"></span> Executing Python code in sandbox...</span><span class="badge bg-primary font-monospace">Running</span>';
        }

        fetch(`/api/dataset/${targetId}/execute_code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: codeContent })
        })
            .then(res => res.json())
            .then(data => {
                const duration = ((Date.now() - startTime) / 1000).toFixed(2);
                if (execTimeBadgeEl) execTimeBadgeEl.textContent = `${duration}s`;

                if (data.success) {
                    if (execStatusBannerEl) {
                        execStatusBannerEl.className = 'alert alert-success py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
                        execStatusBannerEl.innerHTML = `<span><i class="bi bi-check-circle-fill text-success me-1"></i> Execution Succeeded!</span><span class="badge bg-success-subtle text-success font-monospace">${duration}s</span>`;
                    }

                    if (terminalOutputEl) {
                        terminalOutputEl.textContent = data.stdout || '# Execution finished with no console output.';
                    }

                    if (plotsContainerEl) {
                        if (data.plots && data.plots.length > 0) {
                            if (plotsBadgeEl) {
                                plotsBadgeEl.textContent = data.plots.length;
                                plotsBadgeEl.style.display = 'inline-block';
                            }
                            plotsContainerEl.innerHTML = data.plots.map((p, i) => `
                                <div class="border rounded p-2 bg-body-tertiary text-center">
                                    <h6 class="small fw-semibold mb-2 text-primary">Figure ${i + 1}</h6>
                                    <img src="${p}" class="img-fluid rounded border bg-white shadow-sm" alt="Plot ${i + 1}" style="max-height:300px; width:100%; object-fit:contain;">
                                </div>
                            `).join('');
                        } else {
                            if (plotsBadgeEl) plotsBadgeEl.style.display = 'none';
                            plotsContainerEl.innerHTML = '<div class="text-center py-4 text-muted small"><i class="bi bi-image fs-2 d-block mb-1 opacity-50"></i> No figures generated by code execution.</div>';
                        }
                    }

                    if (previewContainerEl) {
                        previewContainerEl.innerHTML = data.preview_html || '<div class="p-3 text-muted">Preview not available.</div>';
                    }
                    if (dfShapeBadgeEl) {
                        dfShapeBadgeEl.textContent = `${Number(data.row_count || 0).toLocaleString()} rows x ${data.column_count || 0} cols`;
                    }

                    showToast('Python code executed and synchronized successfully!', 'success');
                    if (typeof refreshManagerCharts === 'function') refreshManagerCharts();
                } else {
                    if (execStatusBannerEl) {
                        execStatusBannerEl.className = 'alert alert-danger py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
                        execStatusBannerEl.innerHTML = `<span><i class="bi bi-x-circle-fill text-danger me-1"></i> Execution Failed</span><span class="badge bg-danger font-monospace">Error</span>`;
                    }

                    if (terminalOutputEl) {
                        terminalOutputEl.textContent = (data.stdout ? data.stdout + '\n\n' : '') + (data.error || 'Execution error.');
                    }
                    showToast('Code execution failed. Check console output for error details.', 'danger');
                }
            })
            .catch(err => {
                console.error('Error executing code:', err);
                if (execStatusBannerEl) {
                    execStatusBannerEl.className = 'alert alert-danger py-2 px-3 small mb-2 d-flex align-items-center justify-content-between';
                    execStatusBannerEl.innerHTML = `<span><i class="bi bi-wifi-off text-danger me-1"></i> Network Error</span><span class="badge bg-danger font-monospace">Failed</span>`;
                }
                showToast('Network error during code execution.', 'danger');
            })
            .finally(() => {
                if (btnRunCode) {
                    btnRunCode.disabled = false;
                    btnRunCode.innerHTML = '<i class="bi bi-play-fill me-1"></i> Run Code &amp; Sync Vis <kbd class="bg-white text-dark ms-1 px-1 py-0 rounded small fw-bold" style="font-size:0.68rem; opacity:0.9;">Ctrl+Enter</kbd>';
                }
            });
    }

    function triggerManagerDownloadNotebook(format = 'ipynb') {
        const targetId = currentDatasetId;
        if (!targetId) {
            showToast('Please select or load a dataset first.', 'warning');
            return;
        }
        window.location.href = `/api/dataset/${targetId}/download_notebook?format=${format}`;
        showToast(`Preparing ${format.toUpperCase()} download...`, 'info');
    }

    if (btnManagerOpenStudio) {
        btnManagerOpenStudio.addEventListener('click', () => openManagerPythonCodeStudio(currentDatasetId));
    }

    if (btnRunCode) {
        btnRunCode.addEventListener('click', executeManagerStudioCode);
    }

    if (btnCopyCode) {
        btnCopyCode.addEventListener('click', () => {
            const code = codeEditorEl ? codeEditorEl.value : '';
            if (code) {
                navigator.clipboard.writeText(code).then(() => {
                    showToast('Code copied to clipboard!', 'success');
                }).catch(() => {
                    showToast('Could not copy code.', 'warning');
                });
            }
        });
    }

    if (btnResetCode) {
        btnResetCode.addEventListener('click', () => {
            if (autoGeneratedPipelineCode && codeEditorEl) {
                codeEditorEl.value = autoGeneratedPipelineCode;
                updateManagerLineNumbers();
                showToast('Reset code to automated baseline pipeline.', 'info');
            }
        });
    }

    if (btnDownloadIpynb) {
        btnDownloadIpynb.addEventListener('click', (e) => {
            e.preventDefault();
            triggerManagerDownloadNotebook('ipynb');
        });
    }

    if (btnDownloadPy) {
        btnDownloadPy.addEventListener('click', (e) => {
            e.preventDefault();
            triggerManagerDownloadNotebook('py');
        });
    }
});