/**
 * DataNova Developer Dashboard
 * Tabs, API-key management, endpoint catalog, multi-language / SDK snippet generator.
 *
 * Endpoint paths and SDK calls below mirror datanova_sdk/client.py (v1.1.0).
 */
'use strict';

document.addEventListener('DOMContentLoaded', () => {
    // ------------------------------------------------------------------
    // State & tiny DOM helpers
    // ------------------------------------------------------------------
    const state = {
        apiKey: document.getElementById('rawApiKeyVal')?.value || '',
        keyVisible: false,
        lang: 'python',
        endpoint: null
    };

    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
    const byId = (id) => document.getElementById(id);

    function escapeHtml(value) {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function showModal(el) {
        if (el) bootstrap.Modal.getOrCreateInstance(el).show();
    }

    function hideModal(el) {
        if (el) bootstrap.Modal.getOrCreateInstance(el).hide();
    }

    // Non-blocking notifications (replaces alert())
    function showToast(message, type = 'success') {
        let container = byId('dnToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'dnToastContainer';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0`;
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML =
            '<div class="d-flex"><div class="toast-body"></div>' +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';
        $('.toast-body', toastEl).textContent = message;
        container.appendChild(toastEl);
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
        bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 4000 }).show();
    }

    // JSON fetch wrapper: same-origin cookies, optional CSRF token, uniform error handling
    async function apiFetch(url, { method = 'GET', body } = {}) {
        const headers = { Accept: 'application/json' };
        const csrf = $('meta[name="csrf-token"]')?.content;
        if (csrf) headers['X-CSRFToken'] = csrf;

        const options = { method, headers, credentials: 'same-origin' };
        if (body !== undefined) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        let data = null;
        try {
            data = await response.json();
        } catch (_) { /* non-JSON error page */ }

        if (!response.ok || (data && data.success === false)) {
            const err = new Error((data && (data.message || data.error)) || `Request failed (HTTP ${response.status})`);
            err.status = response.status;
            err.data = data;
            throw err;
        }
        return data || {};
    }

    // ------------------------------------------------------------------
    // Clipboard (works on HTTP too, and de-dupes the "Copied!" flash)
    // ------------------------------------------------------------------
    function legacyCopy(text) {
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.cssText = 'position:fixed;top:-1000px;opacity:0';
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand('copy');
        area.remove();
        if (!ok) throw new Error('execCommand copy failed');
    }

    async function copyText(text, btn) {
        if (!text) return;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                legacyCopy(text);
            }
        } catch (err) {
            console.error('Copy failed:', err);
            showToast('Could not copy to clipboard.', 'danger');
            return;
        }
        if (btn) {
            if (!btn.dataset.origHtml) btn.dataset.origHtml = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check2"></i> Copied!';
            setTimeout(() => {
                btn.innerHTML = btn.dataset.origHtml;
                delete btn.dataset.origHtml;
            }, 2000);
        }
    }

    // Preferred: <button data-copy-target="#selector">. Delegated, no inline JS needed.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-copy-target]');
        if (!btn) return;
        const target = $(btn.dataset.copyTarget);
        if (target) copyText(target.textContent.trim(), btn);
    });

    // Backwards-compatible entry point for any remaining inline onclick="copyCodeSnippet('#id')"
    window.copyCodeSnippet = function (selector, btn) {
        const el = $(selector);
        const button = btn || (window.event && window.event.currentTarget) || null;
        if (el) copyText(el.textContent.trim(), button);
    };

    // ------------------------------------------------------------------
    // Tabs
    // ------------------------------------------------------------------
    window.switchDevTab = function (targetTabId) {
        const pane = $(targetTabId);
        if (!pane) return;

        $$('#devTabContent > .tab-pane').forEach((p) => p.classList.remove('show', 'active'));
        pane.classList.add('show', 'active');

        $$('#devMainTabNav .nav-link').forEach((b) => b.classList.remove('active'));
        byId(`${targetTabId.slice(1)}-btn`)?.classList.add('active');

        $$('.dn-sidebar-scroll .dn-nav-link').forEach((link) => {
            link.classList.toggle('active', link.getAttribute('data-target') === targetTabId);
        });

        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    $$('.dn-sidebar-scroll .dn-nav-link[data-target]').forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            switchDevTab(link.getAttribute('data-target'));
        });
    });

    // SDK example sub-tabs
    window.switchSdkSubTab = function (tabId, btnEl) {
        const container = byId('tabQuickstart');
        if (!container) return;
        $$('#sdkExampleTabs .nav-link', container).forEach((b) => b.classList.remove('active'));
        btnEl?.classList.add('active');
        $$('#sdkExampleTabContent > .tab-pane', container).forEach((p) => p.classList.remove('show', 'active'));
        byId(tabId)?.classList.add('show', 'active');
    };

    // Expand / collapse long code box
    window.toggleCodeSnippetExpand = function (boxId, btnId) {
        const box = byId(boxId);
        const btn = byId(btnId);
        if (!box) return;
        const expanded = box.classList.toggle('is-expanded');
        if (btn) {
            btn.innerHTML = expanded
                ? '<i class="bi bi-chevron-up me-1"></i> Show Less (Collapse)'
                : '<i class="bi bi-chevron-down me-1"></i> More (Show All Methods)';
        }
    };

    // ------------------------------------------------------------------
    // Topbar search (endpoint list + API logs)
    // ------------------------------------------------------------------
    byId('devTopbarSearchInput')?.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        $$('#endpointsListGroup .endpoint-select-btn').forEach((btn) => {
            btn.style.display = !query || btn.textContent.toLowerCase().includes(query) ? '' : 'none';
        });
        $$('#apiLogsTableBody tr').forEach((row) => {
            row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
        });
    });

    // ------------------------------------------------------------------
    // Primary API key: reveal / copy / regenerate
    // ------------------------------------------------------------------
    const maskedKeyInput = byId('maskedApiKeyInput');
    const toggleKeyBtn = byId('toggleApiKeyVisibilityBtn');

    function updateApiKeyDisplay() {
        if (maskedKeyInput) {
            maskedKeyInput.value = state.apiKey;
            maskedKeyInput.type = state.keyVisible ? 'text' : 'password';
        }
        if (toggleKeyBtn) {
            toggleKeyBtn.innerHTML = state.keyVisible
                ? '<i class="bi bi-eye-slash-fill"></i>'
                : '<i class="bi bi-eye-fill"></i>';
        }
    }

    toggleKeyBtn?.addEventListener('click', () => {
        state.keyVisible = !state.keyVisible;
        updateApiKeyDisplay();
    });

    byId('copyApiKeyBtn')?.addEventListener('click', (e) => copyText(state.apiKey, e.currentTarget));

    byId('regenerateApiKeyBtn')?.addEventListener('click', async () => {
        if (!confirm('Regenerate your primary API key? Applications using the old key will stop working immediately.')) return;
        try {
            const data = await apiFetch('/api/developer/api_key/generate', { method: 'POST', body: {} });
            const newKey = data.raw_key || data.api_key || data.secret_key;
            if (!newKey) throw new Error('Server did not return a new key.');
            state.apiKey = newKey;
            const rawInput = byId('rawApiKeyVal');
            if (rawInput) rawInput.value = newKey;
            updateApiKeyDisplay();
            showToast('New API key generated. Reloading...');
            setTimeout(() => location.reload(), 1200);
        } catch (err) {
            console.error('Regenerate key error:', err);
            showToast(err.message || 'Failed to regenerate API key.', 'danger');
        }
    });

    // Send Live Test API Call
    byId('btnSendTestApiCall')?.addEventListener('click', async () => {
        const btn = byId('btnSendTestApiCall');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Testing...';
        }
        const startTime = performance.now();
        try {
            const response = await fetch('/api/v1/health', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-API-Key': state.apiKey
                }
            });
            const latency = Math.round(performance.now() - startTime);
            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                showToast(`✓ Test Request Succeeded! HTTP ${response.status} (${latency} ms). Telemetry logged.`, 'success');
                setTimeout(() => location.reload(), 1200);
            } else {
                showToast(`Test call failed: ${data.message || response.statusText}`, 'danger');
            }
        } catch (err) {
            console.error('Test API call error:', err);
            showToast(`Failed to connect to API: ${err.message}`, 'danger');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Send Test Request';
            }
        }
    });

    // ------------------------------------------------------------------
    // Scoped API keys: list / create / revoke
    // ------------------------------------------------------------------
    function renderKeysTable(keys) {
        const tbody = byId('developerApiKeysTableBody');
        const count = byId('totalApiKeysCountVal');
        if (count) count.textContent = keys.length;
        if (!tbody) return;

        if (keys.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No API keys generated yet.</td></tr>';
            return;
        }

        tbody.innerHTML = keys.map((k) => {
            const status = String(k.status || 'active');
            const isActive = status === 'active';
            const env = String(k.environment || 'live');
            const scopes = Array.isArray(k.scopes) ? k.scopes : [];
            return `
            <tr>
                <td class="fw-bold">${escapeHtml(k.key_name || 'API Key')}</td>
                <td><span class="badge ${env === 'live' ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning'} border px-2 py-1 text-uppercase">${escapeHtml(env)}</span></td>
                <td class="font-monospace text-primary">${escapeHtml(k.masked_key || 'dn_live_...')}</td>
                <td><span class="small text-secondary" title="${escapeHtml(scopes.join(', '))}">${scopes.length} Scopes</span></td>
                <td><span class="badge ${isActive ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'}">${escapeHtml(status.charAt(0).toUpperCase() + status.slice(1))}</span></td>
                <td class="small text-secondary">${escapeHtml(k.last_used_at || 'Never')}</td>
                <td class="small text-secondary">${escapeHtml(k.created_at || 'Recent')}</td>
                <td>${isActive
                    ? `<button type="button" class="btn btn-outline-danger btn-sm px-2 py-0 js-revoke-key" data-key-id="${escapeHtml(k.id)}" title="Revoke Key"><i class="bi bi-x-circle"></i> Revoke</button>`
                    : '<span class="text-muted small">Revoked</span>'}</td>
            </tr>`;
        }).join('');
    }

    async function fetchDeveloperKeys() {
        try {
            const data = await apiFetch('/api/developer/keys');
            if (Array.isArray(data.keys)) renderKeysTable(data.keys);
        } catch (err) {
            console.error('Error fetching API keys:', err);
        }
    }

    window.revokeKeyAction = async function (keyId) {
        if (!confirm('Revoke this API key? It will be deactivated immediately.')) return;
        try {
            await apiFetch(`/api/developer/keys/${encodeURIComponent(keyId)}/revoke`, { method: 'POST' });
            showToast('API key revoked.');
            fetchDeveloperKeys();
        } catch (err) {
            console.error('Revoke key error:', err);
            showToast(err.message || 'Failed to revoke API key.', 'danger');
        }
    };

    byId('developerApiKeysTableBody')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.js-revoke-key');
        if (btn) revokeKeyAction(btn.dataset.keyId);
    });

    const submitCreateKeyBtn = byId('submitCreateKeyBtn');
    submitCreateKeyBtn?.addEventListener('click', async () => {
        const nameInput = byId('newKeyNameInput');
        const name = nameInput ? nameInput.value.trim() : '';
        const environment = $('input[name="newKeyEnv"]:checked')?.value || 'live';
        const scopes = $$('.scope-chk:checked').map((c) => c.value);

        if (!name) {
            showToast('Please enter a name or description for the API key.', 'warning');
            nameInput?.focus();
            return;
        }

        submitCreateKeyBtn.disabled = true;
        submitCreateKeyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Generating...';

        try {
            const data = await apiFetch('/api/developer/keys', { method: 'POST', body: { name, environment, scopes } });
            const generatedKey = data.raw_key || data.api_key || data.secret_key;
            if (!generatedKey) throw new Error('Server did not return the new key.');

            // NOTE: a scoped key is shown once in the modal below. It must NOT replace the
            // primary key held in state / rawApiKeyVal (that would silently change every snippet).
            if (nameInput) nameInput.value = '';
            fetchDeveloperKeys();
            hideModal(byId('createApiKeyModal'));

            const rawBox = byId('modalRawKeyBox');
            if (rawBox) rawBox.textContent = generatedKey;
            showModal(byId('newKeyCreatedModal'));
        } catch (err) {
            console.error('Create key error:', err);
            showToast(err.message || 'Failed to create API key.', 'danger');
        } finally {
            submitCreateKeyBtn.disabled = false;
            submitCreateKeyBtn.innerHTML = 'Generate Key';
        }
    });

    byId('copyNewRawKeyBtn')?.addEventListener('click', (e) => {
        copyText(byId('modalRawKeyBox')?.textContent?.trim() || '', e.currentTarget);
    });

    // ------------------------------------------------------------------
    // API log inspector
    // ------------------------------------------------------------------
    window.inspectLogDetail = function (log) {
        const set = (id, text) => { const el = byId(id); if (el) el.textContent = text; };

        set('modalLogReqId', log.request_id || 'req_...');
        set('modalLogEndpoint', `${log.method || 'GET'} ${log.endpoint || '/api/v1/'}`);
        set('modalLogLatency', `${log.response_time_ms || 0} ms`);
        set('modalLogDetailJson', JSON.stringify(log, null, 2));

        const statusEl = byId('modalLogStatus');
        if (statusEl) {
            const code = Number(log.status_code) || 200;
            const text = String(log.status || 'success');
            statusEl.textContent = `${code} ${text.toUpperCase()}`;
            statusEl.className = `badge ${code < 400 && text !== 'failure' ? 'bg-success' : 'bg-danger'} px-3 py-1 font-monospace`;
        }
        showModal(byId('inspectLogModal'));
    };

    window.inspectLogBtnClick = function (btnEl) {
        if (!btnEl) return;
        try {
            window.inspectLogDetail(JSON.parse(btnEl.getAttribute('data-log')));
        } catch (err) {
            console.error('Error inspecting log detail payload:', err);
            showToast('Could not open log details.', 'danger');
        }
    };

    // ------------------------------------------------------------------
    // Endpoint catalog (kept in sync with datanova_sdk/client.py)
    // `sdk` is the body of the SDK example; `multipart` marks file uploads.
    // ------------------------------------------------------------------
    const endpointsData = [
        {
            id: 'v1_upload_dataset', name: 'Upload Dataset (CSV, Excel, JSON)', category: 'Datasets',
            method: 'POST', path: '/api/v1/datasets/upload',
            description: 'Uploads a CSV, Excel, or JSON dataset as multipart/form-data, detects columns and data types, stores it securely, and returns metadata.',
            multipart: { field: 'file', filename: 'sales_2026.csv', mime: 'text/csv' },
            sample_payload: {},
            sdk: 'result = client.upload_dataset("sales_2026.csv")',
            sample_response: { success: true, request_id: 'req_9a82b1c4', dataset_id: 101, filename: 'sales_2026.csv', rows: 5000, columns: 12, status: 'processed' }
        },
        {
            id: 'v1_list_datasets', name: 'List Datasets', category: 'Datasets',
            method: 'GET', path: '/api/v1/datasets',
            description: 'Lists all uploaded datasets for the authenticated account with column counts and file sizes.',
            sample_payload: {},
            sdk: 'result = client.list_datasets()',
            sample_response: { success: true, request_id: 'req_7f31a00e', count: 1, datasets: [{ id: 101, filename: 'sales_2026.csv', rows: 5000, columns: 12, created_at: '2026-09-27 12:00:00' }] }
        },
        {
            id: 'v1_dataset_preview', name: 'Dataset Schema & Sample Preview', category: 'Datasets',
            method: 'GET', path: '/api/v1/datasets/101/preview',
            description: 'Inspect row count, column data types, missing-value statistics, and top sample records without downloading the full file.',
            sample_payload: {},
            sdk: 'result = client.preview_dataset(dataset_id=101)',
            sample_response: { success: true, request_id: 'req_18f4a2b9', dataset_id: 101, rows: 5000, columns: 12, schema: [{ name: 'Revenue', data_type: 'float64', missing_count: 15, unique_count: 4200 }], sample_rows: [{ Revenue: 1500.5, Units: 10 }] }
        },
        {
            id: 'v1_eda_analysis', name: 'Automated EDA Analysis', category: 'Analytics & EDA',
            method: 'POST', path: '/api/v1/analysis/eda',
            description: 'Computes statistical summaries, missing values, duplicates, distributions, outliers, and the correlation matrix.',
            sample_payload: { dataset_id: 101, target_column: 'Revenue' },
            sdk: 'result = client.run_eda(dataset_id=101, target_column="Revenue")',
            sample_response: { success: true, request_id: 'req_c839f211', dataset_id: 101, summary: { rows: 5000, columns: 12, quality_score: 92.5 }, missing_values: { Revenue: 15 }, duplicates: 4, correlation: { Revenue: { Units: 0.87 } } }
        },
        {
            id: 'v1_clean_dataset', name: 'Data Cleaning & Preprocessing', category: 'Analytics & EDA',
            method: 'POST', path: '/api/v1/analysis/clean',
            description: 'Handles missing values, duplicate rows, data types, and outliers. The original dataset stays immutable.',
            sample_payload: { dataset_id: 101, strategies: { Revenue: 'median' }, remove_duplicates: true },
            sdk: 'result = client.clean_dataset(\n    dataset_id=101,\n    strategies={"Revenue": "median"},\n    remove_duplicates=True,\n)',
            sample_response: { success: true, request_id: 'req_37a911eb', dataset_id: 102, original_dataset_id: 101, operations: [{ column: 'Revenue', operation: 'missing_value_imputation', method: 'median', affected_rows: 15 }], cleaned_rows: 4996, removed_duplicates: 4, imputed_nulls: 15 }
        },
        {
            id: 'v1_visualizations', name: 'Automatic Graph Recommendations', category: 'Visualizations',
            method: 'POST', path: '/api/v1/analysis/visualizations',
            description: 'Determines and generates visualization payloads (histogram, box plot, bar chart, heatmap).',
            sample_payload: { dataset_id: 101, chart_types: ['histogram', 'heatmap'] },
            sdk: 'result = client.generate_visualizations(\n    dataset_id=101,\n    chart_types=["histogram", "heatmap"],\n)',
            sample_response: { success: true, request_id: 'req_b281f9a0', dataset_id: 101, charts: [{ chart_id: 'chart_001', type: 'histogram', title: 'Sales Distribution', data: {} }] }
        },
        {
            id: 'v1_auto_pipeline', name: 'Complete Auto Analysis Pipeline', category: 'Analytics & EDA',
            method: 'POST', path: '/api/v1/analysis/auto',
            description: 'One call for the whole pipeline: validation, cleaning, EDA, visualizations, insights, and ML recommendations.',
            sample_payload: { dataset_id: 101, enable_ai: true },
            sdk: 'result = client.run_auto_analysis(dataset_id=101, enable_ai=True)',
            sample_response: { success: true, request_id: 'req_ee819f2a', analysis_id: 'an_101', dataset_id: 101, status: 'completed', eda: { rows: 5000, columns: 12 }, insights: [{ title: 'Strong Correlation Detected' }], ml_recommendations: [{ model: 'RandomForestRegressor' }] }
        },
        {
            id: 'v1_analysis_report', name: 'Analysis Report', category: 'Analytics & EDA',
            method: 'GET', path: '/api/v1/analysis/an_101/report',
            description: 'Fetches the generated executive report data for an analysis run.',
            sample_payload: {},
            sdk: 'result = client.get_analysis_report(analysis_id="an_101")',
            sample_response: { success: true, request_id: 'req_4c1d0e77', analysis_id: 'an_101', report: { title: 'Sales 2026 Analysis', sections: [] } }
        },
        {
            id: 'v1_analysis_code', name: 'Generated Python Code', category: 'Analytics & EDA',
            method: 'GET', path: '/api/v1/analysis/an_101/code',
            description: 'Fetches the auto-generated Python script that reproduces an analysis run.',
            sample_payload: {},
            sdk: 'result = client.get_analysis_code(analysis_id="an_101")\nprint(result["code"])',
            sample_response: { success: true, request_id: 'req_91ab33d2', analysis_id: 'an_101', code: 'import pandas as pd\n# ...' }
        },
        {
            id: 'v1_ask', name: 'Ask AI a Question', category: 'AI',
            method: 'POST', path: '/api/v1/ask',
            description: 'Asks a natural-language question about your data, optionally scoped to one dataset.',
            sample_payload: { query: 'What is the total revenue trend?', dataset_id: 101 },
            sdk: 'result = client.ask_question(\n    query="What is the total revenue trend?",\n    dataset_id=101,\n)',
            sample_response: { success: true, request_id: 'req_2d7e5a10', answer: 'Revenue grew steadily quarter over quarter.', insights: [] }
        },
        {
            id: 'v1_ml_classification', name: 'ML Classification Training', category: 'Machine Learning',
            method: 'POST', path: '/api/v1/ml/classification',
            description: 'Trains supervised classification models (RandomForestClassifier, LogisticRegression) with accuracy / F1 metrics.',
            sample_payload: { dataset_id: 101, target_column: 'IsHighValue', algorithm: 'RandomForest' },
            sdk: 'result = client.train_classification(\n    dataset_id=101,\n    target_column="IsHighValue",\n    algorithm="RandomForest",\n)',
            sample_response: { success: true, request_id: 'req_5510ab9c', model_id: 'model_101_classification', model_name: 'RandomForestClassifier', metrics: { accuracy: 0.945, f1_score: 0.941 }, feature_importance: { Price: 0.58, Qty: 0.42 } }
        },
        {
            id: 'v1_ml_regression', name: 'ML Regression Training', category: 'Machine Learning',
            method: 'POST', path: '/api/v1/ml/regression',
            description: 'Trains supervised regression models (RandomForestRegressor, LinearRegression) with R2, RMSE, and MAE metrics.',
            sample_payload: { dataset_id: 101, target_column: 'Revenue', algorithm: 'RandomForest' },
            sdk: 'result = client.train_regression(\n    dataset_id=101,\n    target_column="Revenue",\n    algorithm="RandomForest",\n)',
            sample_response: { success: true, request_id: 'req_87b1c3e0', model_id: 'model_101_regression', model_name: 'RandomForestRegressor', metrics: { r2_score: 0.912, rmse: 18.4, mae: 12.1 }, feature_importance: { Units: 0.65, Price: 0.35 } }
        },
        {
            id: 'v1_pipeline_execute', name: 'Execute Async Pipeline', category: 'Pipelines',
            method: 'POST', path: '/api/v1/pipeline/execute',
            description: 'Dispatches an asynchronous multi-step pipeline job and returns a task_id to poll.',
            sample_payload: { dataset_id: 101, steps: [{ step: 'clean' }, { step: 'eda' }] },
            sdk: 'result = client.execute_pipeline(\n    dataset_id=101,\n    steps=[{"step": "clean"}, {"step": "eda"}],\n)\ntask_id = result["task_id"]',
            sample_response: { success: true, request_id: 'req_6e0c19b4', task_id: 'task_9f2c1a', status: 'queued' }
        },
        {
            id: 'v1_pipeline_status', name: 'Pipeline Task Status', category: 'Pipelines',
            method: 'GET', path: '/api/v1/pipeline/status/task_9f2c1a',
            description: 'Returns the status and results of an asynchronous pipeline task.',
            sample_payload: {},
            sdk: 'result = client.get_pipeline_status(task_id="task_9f2c1a")',
            sample_response: { success: true, request_id: 'req_a03f77c5', task_id: 'task_9f2c1a', status: 'completed', results: {} }
        },
        {
            id: 'v1_system_health', name: 'System Health & Operational Status', category: 'System',
            method: 'GET', path: '/api/v1/health',
            description: 'Returns operational status of the API gateway, database connector, analysis engine, and ML pipeline.',
            sample_payload: {},
            sdk: 'result = client.health()',
            sample_response: { status: 'operational', version: 'v1', timestamp: '2026-09-27T18:00:00Z', services: { api_gateway: 'operational', database: 'operational', analysis_engine: 'operational', ml_pipeline: 'operational' } }
        }
    ];

    // ------------------------------------------------------------------
    // Snippet generator (Python SDK, Python, JS, cURL, Node.js, PHP, Java)
    // ------------------------------------------------------------------
    // JSON -> valid Python literal (true/false/null are NOT valid Python)
    function toPython(value, indent = 0) {
        const pad = ' '.repeat(indent);
        const inner = ' '.repeat(indent + 4);
        if (value === null || value === undefined) return 'None';
        if (typeof value === 'boolean') return value ? 'True' : 'False';
        if (typeof value === 'number') return String(value);
        if (typeof value === 'string') return JSON.stringify(value);
        if (Array.isArray(value)) {
            if (value.length === 0) return '[]';
            return `[\n${value.map((v) => inner + toPython(v, indent + 4)).join(',\n')}\n${pad}]`;
        }
        const entries = Object.entries(value);
        if (entries.length === 0) return '{}';
        return `{\n${entries.map(([k, v]) => `${inner}${JSON.stringify(k)}: ${toPython(v, indent + 4)}`).join(',\n')}\n${pad}}`;
    }

    const shellQuote = (s) => s.replace(/'/g, "'\\''");
    const phpQuote = (s) => s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const javaQuote = (s) => s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

    const generators = {
        sdk(ep, ctx) {
            const body = ep.sdk.split('\n').map((l) => `        ${l}`).join('\n');
            return `from datanova_sdk import DataNovaClient, DataNovaAPIError

try:
    with DataNovaClient(api_key="${ctx.key}", base_url="${ctx.baseUrl}") as client:
${body}
        print(result)
except DataNovaAPIError as exc:
    print(f"[{exc.status_code}] {exc.message}")`;
        },

        python(ep, ctx) {
            const head = `import requests\n\nurl = "${ctx.url}"\nheaders = {"X-API-Key": "${ctx.key}"}\n`;
            if (ep.multipart) {
                return `${head}
with open("${ep.multipart.filename}", "rb") as f:
    response = requests.post(url, files={"${ep.multipart.field}": f}, headers=headers, timeout=60)

response.raise_for_status()
print(response.json())`;
            }
            if (ep.method === 'POST') {
                return `${head}payload = ${toPython(ep.sample_payload)}

response = requests.post(url, json=payload, headers=headers, timeout=60)
response.raise_for_status()
print(response.json())`;
            }
            return `${head}
response = requests.get(url, headers=headers, timeout=60)
response.raise_for_status()
print(response.json())`;
        },

        javascript(ep, ctx) {
            let init;
            if (ep.multipart) {
                init = `{\n    method: "POST",\n    headers: { "X-API-Key": apiKey },\n    body: formData   // FormData with the file; the browser sets the multipart boundary\n}`;
            } else if (ep.method === 'POST') {
                init = `{\n    method: "POST",\n    headers: { "X-API-Key": apiKey, "Content-Type": "application/json" },\n    body: JSON.stringify(${JSON.stringify(ep.sample_payload)})\n}`;
            } else {
                init = `{\n    method: "GET",\n    headers: { "X-API-Key": apiKey }\n}`;
            }
            const pre = ep.multipart
                ? `const formData = new FormData();\nformData.append("${ep.multipart.field}", fileInput.files[0]); // <input type="file" id="fileInput">\n\n`
                : '';
            return `const apiKey = "${ctx.key}";\n${pre}const response = await fetch("${ctx.url}", ${init});
if (!response.ok) throw new Error(\`HTTP \${response.status}\`);
console.log("DataNova API Result:", await response.json());`;
        },

        curl(ep, ctx) {
            const base = `curl -X ${ep.method} "${ctx.url}" \\\n  -H "X-API-Key: ${ctx.key}"`;
            if (ep.multipart) return `${base} \\\n  -F "${ep.multipart.field}=@${ep.multipart.filename}"`;
            if (ep.method === 'POST') {
                return `${base} \\\n  -H "Content-Type: application/json" \\\n  -d '${shellQuote(JSON.stringify(ep.sample_payload))}'`;
            }
            return base;
        },

        nodejs(ep, ctx) {
            if (ep.multipart) {
                return `const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('${ep.multipart.field}', fs.createReadStream('${ep.multipart.filename}'));

axios.post('${ctx.url}', form, {
    headers: { ...form.getHeaders(), 'X-API-Key': '${ctx.key}' }
})
    .then((res) => console.log(res.status, res.data))
    .catch((err) => console.error(err.response ? err.response.data : err.message));`;
            }
            const data = ep.method === 'POST' ? `${JSON.stringify(ep.sample_payload, null, 2)}, ` : '';
            return `const axios = require('axios');

axios.${ep.method.toLowerCase()}('${ctx.url}', ${data}{
    headers: { 'X-API-Key': '${ctx.key}' }
})
    .then((res) => console.log(res.status, res.data))
    .catch((err) => console.error(err.response ? err.response.data : err.message));`;
        },

        php(ep, ctx) {
            let opts = '';
            if (ep.multipart) {
                opts = `curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, ['${ep.multipart.field}' => new CURLFile('${ep.multipart.filename}', '${ep.multipart.mime}')]);
`;
            } else if (ep.method === 'POST') {
                opts = `curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, '${phpQuote(JSON.stringify(ep.sample_payload))}');
`;
            }
            const headers = ep.multipart
                ? `["X-API-Key: {$apiKey}"]`
                : `[\n    "X-API-Key: {$apiKey}",\n    "Content-Type: application/json"\n]`;
            return `<?php
$url = "${ctx.url}";
$apiKey = "${ctx.key}";

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ${headers});
${opts}
$response = curl_exec($ch);
curl_close($ch);

print_r(json_decode($response, true));`;
        },

        java(ep, ctx) {
            const common = String.raw`import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;`;

            if (ep.multipart) {
                return String.raw`${common}
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class DataNovaUpload {
    public static void main(String[] args) throws Exception {
        Path file = Path.of("${ep.multipart.filename}");
        String boundary = "----DataNova" + System.currentTimeMillis();
        byte[] head = ("--" + boundary + "\r\n"
            + "Content-Disposition: form-data; name=\"${ep.multipart.field}\"; filename=\"" + file.getFileName() + "\"\r\n"
            + "Content-Type: ${ep.multipart.mime}\r\n\r\n").getBytes();
        byte[] tail = ("\r\n--" + boundary + "--\r\n").getBytes();

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("${ctx.url}"))
            .header("X-API-Key", "${ctx.key}")
            .header("Content-Type", "multipart/form-data; boundary=" + boundary)
            .POST(HttpRequest.BodyPublishers.ofByteArrays(List.of(head, Files.readAllBytes(file), tail)))
            .build();

        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println(response.statusCode() + " " + response.body());
    }
}`;
            }

            const verb = ep.method === 'POST'
                ? `.header("Content-Type", "application/json")\n            .POST(HttpRequest.BodyPublishers.ofString("${javaQuote(JSON.stringify(ep.sample_payload))}"))`
                : '.GET()';
            return String.raw`${common}

public class DataNovaExample {
    public static void main(String[] args) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("${ctx.url}"))
            .header("X-API-Key", "${ctx.key}")
            ${verb}
            .build();

        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println(response.statusCode() + " " + response.body());
    }
}`;
        }
    };

    function setBoxText(boxId, text) {
        const box = byId(boxId);
        if (!box) return;
        (box.querySelector('code') || box).textContent = text;
    }

    function renderCodeForEndpoint(ep, lang) {
        if (!ep) {
            setBoxText('generatedCodeBox', '// No code sample is available for this endpoint yet.');
            setBoxText('sampleResponseJsonBox', '{}');
            return;
        }
        const baseUrl = window.location.origin;
        const ctx = {
            baseUrl,
            url: `${baseUrl}${ep.path}`,
            key: state.apiKey || 'dn_live_YOUR_API_KEY'
        };
        const generate = generators[lang] || generators.python;
        setBoxText('generatedCodeBox', generate(ep, ctx));
        setBoxText('sampleResponseJsonBox', JSON.stringify(ep.sample_response, null, 2));
    }

    // Resolve by id first, then by the path shown on the button (handles id drift with the Jinja list)
    function findEndpoint(epId, btnEl) {
        const byIdMatch = endpointsData.find((e) => e.id === epId);
        if (byIdMatch) return byIdMatch;
        const shownPath = btnEl?.querySelector('.font-monospace')?.textContent.trim();
        const byPath = shownPath && endpointsData.find((e) => e.path === shownPath);
        if (!byPath) console.warn(`No sample data for endpoint "${epId}" (${shownPath || 'unknown path'}).`);
        return byPath || null;
    }

    window.selectEndpointItem = function (epId, btnEl) {
        $$('#endpointsListGroup .endpoint-select-btn').forEach((b) => b.classList.remove('active'));
        btnEl?.classList.add('active');

        const ep = findEndpoint(epId, btnEl);
        state.endpoint = ep;

        const name = byId('selectedEpName');
        const badge = byId('selectedEpBadge');
        const desc = byId('selectedEpDesc');

        if (ep) {
            if (name) name.textContent = ep.name;
            if (desc) desc.textContent = ep.description;
            if (badge) {
                badge.textContent = ep.method;
                badge.className = `badge ${ep.method === 'GET' ? 'bg-success' : 'bg-primary'} px-3 py-1 font-monospace`;
            }
        } else {
            if (name) name.textContent = btnEl?.querySelector('.fw-bold')?.textContent || 'Endpoint';
            if (desc) desc.textContent = 'Detailed documentation for this endpoint is not available yet.';
        }
        renderCodeForEndpoint(ep, state.lang);
    };

    window.changeCodeLang = function (lang, tabEl) {
        state.lang = lang;
        $$('#codeLangTabs .nav-link').forEach((l) => l.classList.remove('active'));
        tabEl?.classList.add('active');
        renderCodeForEndpoint(state.endpoint, state.lang);
    };

    // The anchor tabs use href="#"; never let them jump the page.
    byId('codeLangTabs')?.addEventListener('click', (e) => {
        if (e.target.closest('a[href="#"]')) e.preventDefault();
    });

    // ------------------------------------------------------------------
    // Init
    // ------------------------------------------------------------------
    updateApiKeyDisplay();

    const firstBtn = $('#endpointsListGroup .endpoint-select-btn');
    if (firstBtn && typeof selectEndpointItem === 'function') {
        const initialId = firstBtn.dataset.epId || endpointsData[0]?.id;
        selectEndpointItem(initialId, firstBtn);
    }
});