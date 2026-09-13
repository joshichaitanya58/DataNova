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
       3. Search box listener
       ------------------------------------------------------------------- */
    var searchInput = document.querySelector('.dn-topbar-search input');
    if (searchInput) {
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                searchInput.blur();
            }
        });
    }

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
});