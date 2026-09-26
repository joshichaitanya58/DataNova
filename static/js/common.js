/* ==========================================================================
   DataNova — Common Dashboard Script & Unified Global State Bus
   Single Source of Truth connecting Admin, Manager, Analyst, and Viewer.
   - Theme (dark/light) persistence
   - Sidebar toggle (desktop collapse + mobile offcanvas)
   - Cross-Dashboard State Bus Event Emitter & BroadcastChannel Sync
   ========================================================================== */

(function (window) {
    'use strict';

    class StateBus {
        constructor() {
            this.listeners = {};
            this.channelName = 'datanova_global_state_bus';
            this.channel = null;

            if (typeof BroadcastChannel !== 'undefined') {
                try {
                    this.channel = new BroadcastChannel(this.channelName);
                    this.channel.onmessage = (event) => {
                        if (event && event.data && event.data.type) {
                            this.emitLocal(event.data.type, event.data.payload);
                        }
                    };
                } catch (e) {
                    console.log("BroadcastChannel init warning: ", e);
                }
            }

            window.addEventListener('storage', (e) => {
                if (e.key === 'datanova_mutation_signal' && e.newValue) {
                    try {
                        const parsed = JSON.parse(e.newValue);
                        if (parsed && parsed.type) {
                            this.emitLocal(parsed.type, parsed.payload);
                        }
                    } catch (err) { }
                }
            });
        }

        on(eventType, callback) {
            if (!this.listeners[eventType]) {
                this.listeners[eventType] = [];
            }
            this.listeners[eventType].push(callback);
        }

        off(eventType, callback) {
            if (!this.listeners[eventType]) return;
            this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback);
        }

        emitLocal(eventType, payload) {
            if (this.listeners[eventType]) {
                this.listeners[eventType].forEach(cb => cb(payload));
            }
            if (this.listeners['*']) {
                this.listeners['*'].forEach(cb => cb(eventType, payload));
            }
        }

        notify(eventType, payload = {}) {
            this.emitLocal(eventType, payload);

            if (this.channel) {
                try {
                    this.channel.postMessage({ type: eventType, payload: payload });
                } catch (e) { }
            }

            try {
                window.localStorage.setItem('datanova_mutation_signal', JSON.stringify({
                    type: eventType,
                    payload: payload,
                    ts: Date.now()
                }));
            } catch (e) { }
        }

        emit(eventType, payload = {}) {
            this.notify(eventType, payload);
        }

        fetchGlobalState() {
            return fetch('/api/system/global_state')
                .then(res => res.json())
                .then(resData => resData.success ? resData.state : null)
                .catch(err => null);
        }
    }

    window.DataNovaStateBus = new StateBus();

})(window);

document.addEventListener('DOMContentLoaded', function () {

    /* ---------------------------------------------------------------------
       1. Theme (dark/light) — persisted in localStorage
       ------------------------------------------------------------------- */
    var THEME_KEY = 'datanova-theme';
    var root = document.documentElement;
    var themeToggleBtns = document.querySelectorAll('.dn-theme-toggle');

    function applyTheme(theme) {
        if (theme === 'dark') {
            root.setAttribute('data-theme', 'dark');
        } else {
            root.removeAttribute('data-theme');
        }
        themeToggleBtns.forEach(function (btn) {
            var icon = btn.querySelector('i');
            if (!icon) return;
            icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
        });
    }

    var savedTheme = null;
    try { savedTheme = window.localStorage.getItem(THEME_KEY); } catch (err) { }
    applyTheme(savedTheme === 'dark' ? 'dark' : 'light');

    themeToggleBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var isDark = root.getAttribute('data-theme') === 'dark';
            var next = isDark ? 'light' : 'dark';
            applyTheme(next);
            try { window.localStorage.setItem(THEME_KEY, next); } catch (err) { }
        });
    });

    /* ---------------------------------------------------------------------
       2. Sidebar toggle (desktop collapse + mobile offcanvas)
       ------------------------------------------------------------------- */
    var appShell = document.querySelector('.dn-app');
    var sidebarToggleBtns = document.querySelectorAll('.dn-sidebar-toggle-btn');
    var overlay = document.querySelector('.dn-sidebar-overlay');

    function toggleSidebar() {
        if (!appShell) return;
        if (window.innerWidth <= 991.98) {
            var isOpen = appShell.classList.toggle('dn-sidebar-open');
            if (overlay) overlay.classList.toggle('is-visible', isOpen);
        } else {
            appShell.classList.toggle('dn-sidebar-collapsed');
        }

        setTimeout(function () {
            window.dispatchEvent(new Event('resize'));
        }, 300);
    }

    sidebarToggleBtns.forEach(function (btn) {
        btn.addEventListener('click', toggleSidebar);
    });

    if (overlay) {
        overlay.addEventListener('click', function () {
            if (appShell) {
                appShell.classList.remove('dn-sidebar-open');
                appShell.classList.remove('dn-sidebar-collapsed');
            }
            overlay.classList.remove('is-visible');
        });
    }

    document.querySelectorAll('.dn-nav-link').forEach(function (link) {
        link.addEventListener('click', function () {
            if (window.innerWidth <= 991.98 && appShell && appShell.classList.contains('dn-sidebar-open')) {
                appShell.classList.remove('dn-sidebar-open');
                if (overlay) overlay.classList.remove('is-visible');
            }
        });
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth > 991.98 && appShell && appShell.classList.contains('dn-sidebar-open')) {
            appShell.classList.remove('dn-sidebar-open');
            if (overlay) overlay.classList.remove('is-visible');
        }
    });

    /* ---------------------------------------------------------------------
       3. Unified DataNova Global Search Engine (Admin, Analyst, Manager, Viewer)
       ------------------------------------------------------------------- */
    function initDataNovaGlobalSearch() {
        var searchContainer = document.querySelector('.dn-topbar-search');
        if (!searchContainer) return;

        var searchInput = searchContainer.querySelector('input');
        if (!searchInput) return;

        var clearBtn = searchContainer.querySelector('.dn-search-clear-btn');
        var dropdown = searchContainer.querySelector('.dn-search-dropdown');
        var countBadge = searchContainer.querySelector('[id*="MatchCount"]') || searchContainer.querySelector('.badge');
        var dropdownContent = searchContainer.querySelector('[id*="DropdownContent"]') || (dropdown ? dropdown.querySelector('.p-2:last-child') : null);

        // Auto-create dropdown & clear button if not already in DOM
        if (!clearBtn) {
            clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.className = 'dn-search-clear-btn d-none';
            clearBtn.title = 'Clear search';
            clearBtn.innerHTML = '<i class="bi bi-x-circle-fill"></i>';
            searchContainer.appendChild(clearBtn);
        }

        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className = 'dn-search-dropdown d-none';
            dropdown.innerHTML = `
                <div class="p-2 border-bottom d-flex justify-content-between align-items-center bg-body-tertiary">
                    <small class="fw-bold text-secondary text-uppercase" style="font-size: 0.68rem; letter-spacing: 0.05em;">
                        <i class="bi bi-funnel-fill text-primary me-1"></i> Live Search Results
                    </small>
                    <span class="badge bg-primary" style="font-size: 0.68rem;">0 matches</span>
                </div>
                <div class="p-2" style="max-height: 380px; overflow-y: auto;"></div>
            `;
            searchContainer.appendChild(dropdown);
            countBadge = dropdown.querySelector('.badge');
            dropdownContent = dropdown.querySelector('.p-2:last-child');
        }

        var activeIndex = -1;

        function escapeRegExp(str) {
            return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }

        function highlightMatch(text, query) {
            if (!query) return escapeHtml(text);
            var q = query.trim();
            if (!q) return escapeHtml(text);
            var regex = new RegExp('(' + escapeRegExp(q) + ')', 'gi');
            return escapeHtml(text).replace(regex, '<mark class="px-1 py-0 rounded bg-warning text-dark fw-bold">$1</mark>');
        }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        // --- Collect Searchable Items from the current Dashboard DOM ---
        function collectSearchIndex() {
            var items = [];

            // 1. Navigation & Sidebar Links
            document.querySelectorAll('.dn-sidebar .dn-nav-link').forEach(function (link) {
                var text = (link.textContent || '').replace(/\s+/g, ' ').trim();
                var href = link.getAttribute('href') || '';
                var targetModal = link.getAttribute('data-bs-target') || '';
                var action = link.getAttribute('data-action') || '';
                var iconEl = link.querySelector('i');
                var icon = iconEl ? iconEl.className : 'bi bi-compass';

                if (text && (href || targetModal || action)) {
                    items.push({
                        category: 'Navigation & Sections',
                        title: text,
                        subtitle: 'Sidebar Quick Jump',
                        icon: icon,
                        type: 'Nav',
                        badgeClass: 'bg-primary-subtle text-primary',
                        action: function () {
                            if (targetModal) {
                                var modalEl = document.querySelector(targetModal);
                                if (modalEl && window.bootstrap) {
                                    bootstrap.Modal.getOrCreateInstance(modalEl).show();
                                    return;
                                }
                            }
                            if (href && href.startsWith('#') && href.length > 1) {
                                var targetEl = document.querySelector(href);
                                if (targetEl) {
                                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    flashHighlight(targetEl);
                                }
                            }
                            link.click();
                        }
                    });
                }
            });

            // 2. Main Dashboard Panels & Section Titles
            document.querySelectorAll('.dn-panel, .dn-page-header, [id$="Section"], [id$="Panel"], [id^="step-"]').forEach(function (panel) {
                var id = panel.id;
                var titleEl = panel.querySelector('.dn-panel-title, .dn-page-title, h1, h2, h3, h4');
                var title = titleEl ? titleEl.textContent.replace(/\s+/g, ' ').trim() : '';
                var subEl = panel.querySelector('.dn-panel-sub, .dn-page-sub, p');
                var sub = subEl ? subEl.textContent.replace(/\s+/g, ' ').trim() : '';
                var iconEl = panel.querySelector('.dn-panel-title i, .dn-eyebrow i, .dn-kpi-icon i');
                var icon = iconEl ? iconEl.className : 'bi bi-grid-fill';

                if (title && id) {
                    // Check if not already added in nav
                    var exists = items.some(function (it) { return it.title.toLowerCase() === title.toLowerCase(); });
                    if (!exists) {
                        items.push({
                            category: 'Navigation & Sections',
                            title: title,
                            subtitle: sub ? sub.substring(0, 70) + '...' : 'Dashboard Section',
                            icon: icon,
                            type: 'Section',
                            badgeClass: 'bg-secondary-subtle text-secondary',
                            action: function () {
                                panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                flashHighlight(panel);
                            }
                        });
                    }
                }
            });

            // 3. Tasks & Workload (Manager, Analyst, Viewer)
            document.querySelectorAll('#managerTaskTableBody tr[data-task-id], #viewerAssignedTasksTableBody tr[data-task-id], #assignedTasksList .card, #assignedTasksTableBody tr').forEach(function (el) {
                var text = (el.textContent || '').replace(/\s+/g, ' ').trim();
                var titleEl = el.querySelector('.fw-semibold, h6, .dn-task-title');
                var title = titleEl ? titleEl.textContent.trim() : text.substring(0, 40);
                var statusBadge = el.querySelector('.badge');
                var status = statusBadge ? statusBadge.textContent.trim() : 'Task';

                if (title) {
                    items.push({
                        category: 'Tasks & Workload',
                        title: title,
                        subtitle: text.substring(0, 80) + '...',
                        icon: 'bi bi-check2-square text-success',
                        type: status,
                        badgeClass: 'bg-success-subtle text-success',
                        action: function () {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            flashHighlight(el);
                        }
                    });
                }
            });

            // 4. Team Members & Platform Users (Manager, Admin)
            document.querySelectorAll('#managerTeamTableBody tr[data-member-id], #availableUsersTableBody tr[data-user-id], #adminRecentUsersTable tbody tr:not(.dn-no-results-row)').forEach(function (el) {
                var text = (el.textContent || '').replace(/\s+/g, ' ').trim();
                var nameEl = el.querySelector('.fw-semibold, td:first-child');
                var name = nameEl ? nameEl.textContent.trim() : text.substring(0, 30);
                var emailEl = el.querySelector('.small, td:nth-child(2)');
                var email = emailEl ? emailEl.textContent.trim() : '';
                var roleBadge = el.querySelector('.dn-role-badge, .badge');
                var role = roleBadge ? roleBadge.textContent.trim() : 'User';

                if (name) {
                    items.push({
                        category: 'Team & Users',
                        title: name,
                        subtitle: email ? email : text.substring(0, 60),
                        icon: 'bi bi-person-circle text-primary',
                        type: role,
                        badgeClass: 'bg-primary-subtle text-primary',
                        action: function () {
                            // If in tab pane, switch to it
                            var tabPane = el.closest('.tab-pane');
                            if (tabPane && tabPane.id) {
                                var tabBtn = document.querySelector('[data-bs-target="#' + tabPane.id + '"]');
                                if (tabBtn) tabBtn.click();
                            }
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            flashHighlight(el);
                        }
                    });
                }
            });

            // 5. Datasets & Files
            document.querySelectorAll('#adminRecentDatasetsTable tbody tr:not(.dn-no-results-row), #previousDatasetsTableBody tr, #datasetsOverviewSection .card, .dn-dataset-card').forEach(function (el) {
                var text = (el.textContent || '').replace(/\s+/g, ' ').trim();
                var nameEl = el.querySelector('.fw-semibold, .card-title, td:first-child');
                var name = nameEl ? nameEl.textContent.trim() : text.substring(0, 40);

                if (name) {
                    items.push({
                        category: 'Datasets & Files',
                        title: name,
                        subtitle: text.substring(0, 70),
                        icon: 'bi bi-database text-info',
                        type: 'Dataset',
                        badgeClass: 'bg-info-subtle text-info',
                        action: function () {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            flashHighlight(el);
                            var viewBtn = el.querySelector('button, a');
                            if (viewBtn && (viewBtn.textContent.includes('Load') || viewBtn.textContent.includes('View'))) {
                                viewBtn.click();
                            }
                        }
                    });
                }
            });

            // 6. Reports & Executive Summaries (Viewer, Manager, Admin)
            document.querySelectorAll('#viewerReportsTableBody tr, #reportsSection table tbody tr, #adminReportsTable tbody tr').forEach(function (el) {
                var text = (el.textContent || '').replace(/\s+/g, ' ').trim();
                var nameEl = el.querySelector('td:first-child, .fw-semibold');
                var name = nameEl ? nameEl.textContent.trim() : text.substring(0, 40);

                if (name) {
                    items.push({
                        category: 'Reports & Summaries',
                        title: name,
                        subtitle: text.substring(0, 70),
                        icon: 'bi bi-file-earmark-text text-warning',
                        type: 'Report',
                        badgeClass: 'bg-warning-subtle text-warning',
                        action: function () {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            flashHighlight(el);
                        }
                    });
                }
            });

            // 7. Interactive Action Shortcuts & Modals
            var actionShortcuts = [
                { title: 'Upload New Dataset', sub: 'CSV, Excel, JSON or SQLite file', icon: 'bi bi-cloud-arrow-up text-primary', selector: '#navUploadDataset, [data-action="upload-dataset"], #btnBrowseFiles' },
                { title: 'Assign New Task', sub: 'Delegate workload to analysts or viewers', icon: 'bi bi-plus-circle-fill text-success', selector: '[data-action="assign-task"], #btnOpenAssignTaskModal' },
                { title: 'Add / Invite Team Member', sub: 'Manage user access and roles', icon: 'bi bi-person-plus-fill text-info', selector: '[data-action="add-member"], [data-action="add-team-member"], #btnAddTeamMember' },
                { title: 'Compare Datasets', sub: 'Side-by-side metric comparison', icon: 'bi bi-columns-gap text-purple', selector: '[data-action="compare-data"], #navCompareDatasets' },
                { title: 'Ask DataNova AI Assistant', sub: 'Instant NLP query over active dataset', icon: 'bi bi-stars text-warning', selector: '#navAskYourData, .dn-open-ask-modal, [data-action="ask-ai"]' },
                { title: 'Data Cleaning & Transformation', sub: 'Handle missing values, duplicates, types', icon: 'bi bi-shield-check text-primary', selector: '#navDataCleaning, [data-action="data-cleaning"]' },
                { title: 'Statistical & Visual EDA', sub: 'Distributions, correlations, charts', icon: 'bi bi-bar-chart-line-fill text-info', selector: '#navStatisticalEDA, #navVisualizations' },
                { title: 'Export Full Analytical Report', sub: 'Download automated PDF or HTML dossier', icon: 'bi bi-file-earmark-pdf-fill text-danger', selector: '#dnExportReportBtn, [data-action="export-report"]' },
                { title: 'User Profile & Settings', sub: 'Update name, email, avatar & preferences', icon: 'bi bi-person-gear text-secondary', selector: '#navAnalystProfile, #navAnalystSettings, [data-bs-target="#userProfileModal"], [data-bs-target="#adminUserProfileModal"], [data-bs-target="#managerUserProfileModal"], [data-bs-target="#viewerUserProfileModal"]' }
            ];

            actionShortcuts.forEach(function (act) {
                var el = document.querySelector(act.selector);
                if (el) {
                    items.push({
                        category: 'Quick Actions & Tools',
                        title: act.title,
                        subtitle: act.sub,
                        icon: act.icon,
                        type: 'Action',
                        badgeClass: 'bg-dark-subtle text-dark border',
                        action: function () {
                            el.click();
                        }
                    });
                }
            });

            return items;
        }

        function flashHighlight(el) {
            if (!el) return;
            el.classList.remove('dn-search-highlight-target');
            // trigger reflow
            void el.offsetWidth;
            el.classList.add('dn-search-highlight-target');
            setTimeout(function () {
                el.classList.remove('dn-search-highlight-target');
            }, 2500);
        }

        // --- Execute Global Search ---
        function executeGlobalSearch(query) {
            var rawQuery = (query || '').trim();
            var lowerQuery = rawQuery.toLowerCase();
            activeIndex = -1;

            if (clearBtn) {
                clearBtn.classList.toggle('d-none', !rawQuery);
            }

            if (!rawQuery) {
                if (dropdown) dropdown.classList.add('d-none');
                return;
            }

            var allItems = collectSearchIndex();
            var matchedItems = allItems.filter(function (item) {
                var text = (item.title + ' ' + (item.subtitle || '') + ' ' + (item.category || '')).toLowerCase();
                return text.includes(lowerQuery);
            });

            // Group by category
            var grouped = {};
            matchedItems.forEach(function (item) {
                if (!grouped[item.category]) grouped[item.category] = [];
                grouped[item.category].push(item);
            });

            var totalCount = matchedItems.length;
            if (countBadge) {
                countBadge.textContent = totalCount + ' ' + (totalCount === 1 ? 'match' : 'matches');
            }

            if (totalCount === 0) {
                if (dropdownContent) {
                    dropdownContent.innerHTML = `
                        <div class="p-3 text-center text-secondary small">
                            <i class="bi bi-search me-1 fs-5 d-block mb-1 text-muted"></i>
                            No matching items found for "<strong>${escapeHtml(rawQuery)}</strong>"
                        </div>
                    `;
                }
                if (dropdown) dropdown.classList.remove('d-none');
                return;
            }

            var html = '';
            var itemIdx = 0;
            Object.keys(grouped).forEach(function (cat) {
                html += '<div class="dn-search-cat-header"><i class="bi bi-folder2-open me-1"></i> ' + escapeHtml(cat) + ' (' + grouped[cat].length + ')</div>';
                grouped[cat].forEach(function (item) {
                    html += `
                        <div class="dn-search-result-item" data-search-idx="${itemIdx}">
                            <div class="d-flex align-items-center gap-2 overflow-hidden text-truncate">
                                <i class="${item.icon || 'bi bi-arrow-right-short'} fs-6 flex-shrink-0"></i>
                                <div class="text-truncate">
                                    <div class="fw-semibold text-truncate">${highlightMatch(item.title, rawQuery)}</div>
                                    <div class="small text-muted text-truncate" style="font-size:0.75rem;">${highlightMatch(item.subtitle, rawQuery)}</div>
                                </div>
                            </div>
                            <span class="badge ${item.badgeClass || 'bg-light text-dark'} small flex-shrink-0" style="font-size: 0.68rem;">${item.type}</span>
                        </div>
                    `;
                    itemIdx++;
                });
            });

            if (dropdownContent) {
                dropdownContent.innerHTML = html;

                // Attach click listeners to rendered result items
                dropdownContent.querySelectorAll('.dn-search-result-item').forEach(function (itemEl, idx) {
                    itemEl.addEventListener('click', function (e) {
                        e.preventDefault();
                        var target = matchedItems[idx];
                        if (target && target.action) {
                            if (dropdown) dropdown.classList.add('d-none');
                            target.action();
                        }
                    });
                });
            }

            if (dropdown) dropdown.classList.remove('d-none');
        }

        // --- Event Listeners ---
        searchInput.addEventListener('input', function (e) {
            executeGlobalSearch(e.target.value);
        });

        searchInput.addEventListener('focus', function () {
            if (searchInput.value.trim()) {
                executeGlobalSearch(searchInput.value);
            }
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                searchInput.value = '';
                searchInput.focus();
                executeGlobalSearch('');
            });
        }

        // Keyboard Navigation (ArrowUp, ArrowDown, Enter, Escape)
        searchInput.addEventListener('keydown', function (e) {
            var resultItems = dropdownContent ? dropdownContent.querySelectorAll('.dn-search-result-item') : [];

            if (e.key === 'Escape') {
                searchInput.value = '';
                executeGlobalSearch('');
                if (dropdown) dropdown.classList.add('d-none');
                searchInput.blur();
            } else if (e.key === 'ArrowDown') {
                if (resultItems.length > 0) {
                    e.preventDefault();
                    activeIndex = (activeIndex + 1) % resultItems.length;
                    updateActiveItem(resultItems);
                }
            } else if (e.key === 'ArrowUp') {
                if (resultItems.length > 0) {
                    e.preventDefault();
                    activeIndex = (activeIndex - 1 + resultItems.length) % resultItems.length;
                    updateActiveItem(resultItems);
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (resultItems.length > 0) {
                    var targetIdx = activeIndex >= 0 ? activeIndex : 0;
                    if (resultItems[targetIdx]) {
                        resultItems[targetIdx].click();
                    }
                }
            }
        });

        function updateActiveItem(items) {
            items.forEach(function (el, idx) {
                if (idx === activeIndex) {
                    el.classList.add('is-active');
                    el.scrollIntoView({ block: 'nearest' });
                } else {
                    el.classList.remove('is-active');
                }
            });
        }

        // Global Keyboard Shortcut: "/" or "Ctrl+K" / "Cmd+K" to focus topbar search
        document.addEventListener('keydown', function (e) {
            var activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
            var isInput = (activeTag === 'input' || activeTag === 'textarea' || document.activeElement.isContentEditable);

            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            } else if (e.key === '/' && !isInput) {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function (e) {
            if (dropdown && !e.target.closest('.dn-topbar-search')) {
                dropdown.classList.add('d-none');
            }
        });
    }

    initDataNovaGlobalSearch();

    /* ---------------------------------------------------------------------
       4. Unified User Profile Modal Handler (Admin, Manager, Analyst, Viewer)
       ------------------------------------------------------------------- */
    var profileModals = document.querySelectorAll('#userProfileModal, #adminUserProfileModal, #managerUserProfileModal, #analystProfileModal, #viewerUserProfileModal');
    profileModals.forEach(function (modalEl) {
        modalEl.addEventListener('show.bs.modal', function () {
            fetch('/api/user/profile')
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res && res.success && res.profile) {
                        var p = res.profile;
                        var fn = modalEl.querySelector('.userProfileFirstName') || document.getElementById('userProfileFirstName');
                        var ln = modalEl.querySelector('.userProfileLastName') || document.getElementById('userProfileLastName');
                        var em = modalEl.querySelector('.userProfileEmail') || document.getElementById('userProfileEmail');
                        var org = modalEl.querySelector('.userProfileOrganization') || document.getElementById('userProfileOrganization');
                        var ph = modalEl.querySelector('.userProfilePhone') || document.getElementById('userProfilePhone');
                        var bio = modalEl.querySelector('.userProfileBio') || document.getElementById('userProfileBio');

                        if (fn) fn.value = p.first_name || '';
                        if (ln) ln.value = p.last_name || '';
                        if (em) em.value = p.email || '';
                        if (org) org.value = p.organization || 'General';
                        if (ph) ph.value = p.phone || '';
                        if (bio) bio.value = p.bio || '';
                    }
                })
                .catch(function (err) {
                    console.log("Error loading profile details:", err);
                });
        });
    });

    var profileForms = document.querySelectorAll('.dnUserProfileForm, #dnUserProfileForm');
    profileForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var modalEl = form.closest('.modal');
            var fnInput = form.querySelector('.userProfileFirstName') || document.getElementById('userProfileFirstName');
            var lnInput = form.querySelector('.userProfileLastName') || document.getElementById('userProfileLastName');
            var phInput = form.querySelector('.userProfilePhone') || document.getElementById('userProfilePhone');
            var bioInput = form.querySelector('.userProfileBio') || document.getElementById('userProfileBio');
            var errAlert = form.querySelector('.userProfileErrorAlert') || (modalEl ? modalEl.querySelector('.alert-danger') : null);

            var firstName = (fnInput ? fnInput.value : '').trim();
            var lastName = (lnInput ? lnInput.value : '').trim();
            var phone = (phInput ? phInput.value : '').trim();
            var bio = (bioInput ? bioInput.value : '').trim();

            if (!firstName) {
                if (errAlert) {
                    errAlert.textContent = "First name is required.";
                    errAlert.classList.remove('d-none');
                }
                return;
            }

            if (errAlert) errAlert.classList.add('d-none');

            var btnSubmit = form.querySelector('.btnSubmitUserProfile') || form.querySelector('button[type="submit"]');
            var spinner = form.querySelector('.userProfileSpinner') || (btnSubmit ? btnSubmit.querySelector('.spinner-border') : null);
            var icon = form.querySelector('.userProfileSaveIcon') || (btnSubmit ? btnSubmit.querySelector('i') : null);

            if (btnSubmit) btnSubmit.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (icon) icon.classList.add('d-none');

            fetch('/api/user/profile/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    phone: phone,
                    bio: bio
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (icon) icon.classList.remove('d-none');

                    if (res && res.success) {
                        if (modalEl && typeof bootstrap !== 'undefined') {
                            var inst = bootstrap.Modal.getInstance(modalEl);
                            if (inst) inst.hide();
                        }

                        var toastFn = window.showToast || function (m) {
                            alert(m);
                        };
                        toastFn(res.message || "Profile updated successfully!", "success");

                        // Update page display name
                        var fullNameDisplays = document.querySelectorAll('.userProfileFullNameDisplay, #userProfileFullNameDisplay');
                        fullNameDisplays.forEach(function (el) {
                            el.textContent = firstName + ' ' + lastName;
                        });

                        // Update avatar badges initials
                        var init1 = firstName ? firstName[0].toUpperCase() : 'U';
                        var init2 = lastName ? lastName[0].toUpperCase() : '';
                        var initials = init1 + init2;

                        var avatarBadges = document.querySelectorAll('.userProfileAvatarBadge, #userProfileAvatarBadge, .dn-user-trigger .dn-avatar, .dn-avatar-user');
                        avatarBadges.forEach(function (el) {
                            el.textContent = initials;
                        });

                        // Update topbar trigger name if present
                        var topbarName = document.querySelector('.dn-user-trigger-name, .dn-topbar-user .fw-semibold');
                        if (topbarName) {
                            topbarName.textContent = firstName + ' ' + lastName;
                        }
                    } else {
                        if (errAlert) {
                            errAlert.textContent = (res && res.message) ? res.message : "Failed to update profile.";
                            errAlert.classList.remove('d-none');
                        }
                    }
                })
                .catch(function (err) {
                    console.log("Error updating profile:", err);
                    if (btnSubmit) btnSubmit.disabled = false;
                    if (spinner) spinner.classList.add('d-none');
                    if (icon) icon.classList.remove('d-none');
                    if (errAlert) {
                        errAlert.textContent = "Server connection error while updating profile.";
                        errAlert.classList.remove('d-none');
                    }
                });
        });
    });

    /* ---------------------------------------------------------------------
       8. Real-Time Live State Synchronization (Zero-Reload Heartbeat)
       ------------------------------------------------------------------- */
    (function initRealTimeSync() {
        let lastSyncState = {
            unreadCount: null,
            tasksVersion: null,
            teamVersion: null,
            dashboardsVersion: null,
            latestNotifId: null
        };

        function pollLiveSync() {
            if (document.hidden) return; // Skip polling when browser tab is inactive
            fetch('/api/system/live_sync', { credentials: 'same-origin' })
                .then(r => {
                    if (r.status === 401 || r.status === 403) return null;
                    return r.json();
                })
                .then(data => {
                    if (!data || !data.success) return;

                    // 1. Check Unread Notifications Count & Dropdown
                    if (lastSyncState.unreadCount !== null && data.unread_notifications_count !== lastSyncState.unreadCount) {
                        const notifBadges = document.querySelectorAll('#notificationBadge, .dn-notification-badge, .badge-notification-count');
                        notifBadges.forEach(badge => {
                            if (data.unread_notifications_count > 0) {
                                badge.textContent = data.unread_notifications_count;
                                badge.classList.remove('d-none');
                                badge.style.display = '';
                            } else {
                                badge.classList.add('d-none');
                                badge.style.display = 'none';
                            }
                        });
                    }

                    // 2. Check for New Toast Notifications
                    if (data.latest_notifications && data.latest_notifications.length > 0) {
                        const topNotif = data.latest_notifications[0];
                        if (lastSyncState.latestNotifId !== null && topNotif.id !== lastSyncState.latestNotifId && !topNotif.is_read) {
                            if (window.showToast) {
                                window.showToast(`🔔 ${topNotif.title}: ${topNotif.message}`, 'info');
                            }
                        }
                        lastSyncState.latestNotifId = topNotif.id;
                    }

                    // 3. Check Tasks Version Mutation (e.g. Manager assigns task or status changes)
                    if (lastSyncState.tasksVersion !== null && data.tasks_version !== lastSyncState.tasksVersion) {
                        console.log('🔄 Real-time sync: Tasks updated in background. Dispatching StateBus signal.');
                        if (window.DataNovaStateBus) {
                            window.DataNovaStateBus.notify('MUTATION_TASK_UPDATE', { ts: Date.now() });
                            window.DataNovaStateBus.notify('MUTATION_TASK_ASSIGNED', { ts: Date.now() });
                        }
                    }

                    // 4. Check Team Version Mutation
                    if (lastSyncState.teamVersion !== null && data.team_version !== lastSyncState.teamVersion) {
                        console.log('🔄 Real-time sync: Team updated in background.');
                        if (window.DataNovaStateBus) {
                            window.DataNovaStateBus.notify('MUTATION_TEAM_UPDATE', { ts: Date.now() });
                        }
                    }

                    // 5. Check Dashboards Version Mutation
                    if (lastSyncState.dashboardsVersion !== null && data.dashboards_version !== lastSyncState.dashboardsVersion) {
                        console.log('🔄 Real-time sync: Dashboards updated in background.');
                        if (window.DataNovaStateBus) {
                            window.DataNovaStateBus.notify('MUTATION_DASHBOARD_SHARED', { ts: Date.now() });
                        }
                    }

                    // Save snapshot
                    lastSyncState.unreadCount = data.unread_notifications_count;
                    lastSyncState.tasksVersion = data.tasks_version;
                    lastSyncState.teamVersion = data.team_version;
                    lastSyncState.dashboardsVersion = data.dashboards_version;
                })
                .catch(err => {
                    // Suppress network jitter errors
                });
        }

        // Run initial check and set periodic heartbeat (every 15s)
        pollLiveSync();
        setInterval(pollLiveSync, 15000);
    })();
});