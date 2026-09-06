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

            case 'view-business':
                e.preventDefault();
                scrollToSection('Revenue Trend');
                break;

            case 'view-datasets':
                e.preventDefault();
                showToast("Viewing manager dataset overview...", "info");
                scrollToSection('Category Performance');
                break;

            case 'view-team':
            case 'view-tasks':
            case 'view-shared':
                const targetId = action === 'view-team' ? 'teamSection' : (action === 'view-tasks' ? 'taskSection' : 'sharedDashboardsSection');
                const sec = document.getElementById(targetId);
                if (sec) sec.scrollIntoView({ behavior: 'smooth' });
                break;

            case 'compare-data':
                e.preventDefault();
                showCompareDatasetsModal();
                break;

            case 'view-reports':
                e.preventDefault();
                showToast("Opening Reports Repository...", "info");
                window.location.href = "/dashboard/admin/reports";
                break;

            case 'ai-insights':
                e.preventDefault();
                scrollToSection('AI Key Insights');
                break;

            case 'view-trends':
                e.preventDefault();
                scrollToSection('Trends');
                break;

            case 'view-predictions':
                e.preventDefault();
                scrollToSection('Prediction Preview');
                break;

            case 'help':
                e.preventDefault();
                showToast("Manager Help: Assign tasks to team members and monitor real-time completion rates.", "info");
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
                    const descContainer = document.getElementById('sharedDetailDescContainer');
                    const descText = document.getElementById('sharedDetailDescText');
                    const remarkBanner = document.getElementById('sharedDetailRemarkBanner');
                    const remarkText = document.getElementById('sharedDetailRemarkText');
                    const fileText = document.getElementById('sharedDetailDatasetFile');
                    const remarkInput = document.getElementById('managerReviewRemarkInput');

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

                    if (remarkInput) {
                        remarkInput.value = sd.remark || '';
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
                showToast(data.message || 'Review submitted successfully!', 'success');
                if (sharedDetailModalInstance) sharedDetailModalInstance.hide();
                fetchManagerSharedDashboards();
                if (window.DataNovaStateBus) {
                    if (typeof window.DataNovaStateBus.notify === 'function') {
                        window.DataNovaStateBus.notify('MUTATION_DASHBOARD_REVIEWED', { shared_id: sharedId, action: action });
                    }
                }
            } else {
                showToast(data.message || 'Failed to submit review.', 'danger');
            }
        })
        .catch(err => {
            if (btn) btn.disabled = false;
            console.error('Review submit error:', err);
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
});