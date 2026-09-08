/* ==========================================================================
   DataNova — Common Dashboard Script
   Shared functionality for all role-based dashboards.
   - Theme (dark/light) persistence
   - Sidebar toggle (desktop collapse + mobile offcanvas)
   ========================================================================== */

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
            if (!icon) return;  // Safety check: skip if no icon found
            icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
        });
    }

    var savedTheme = null;
    try { savedTheme = window.localStorage.getItem(THEME_KEY); } catch (err) { /* storage unavailable */ }
    applyTheme(savedTheme === 'dark' ? 'dark' : 'light');

    themeToggleBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var isDark = root.getAttribute('data-theme') === 'dark';
            var next = isDark ? 'light' : 'dark';
            applyTheme(next);
            try { window.localStorage.setItem(THEME_KEY, next); } catch (err) { /* storage unavailable */ }
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
        appShell.classList.toggle('dn-sidebar-open');
        if (overlay) overlay.classList.toggle('is-visible', appShell.classList.contains('dn-sidebar-open'));
    }

    sidebarToggleBtns.forEach(function (btn) {
        btn.addEventListener('click', toggleSidebar);
    });

    if (overlay) {
        overlay.addEventListener('click', function () {
            if (appShell) appShell.classList.remove('dn-sidebar-open');
            overlay.classList.remove('is-visible');
        });
    }

    // Close mobile sidebar automatically when a nav link is tapped
    document.querySelectorAll('.dn-nav-link').forEach(function (link) {
        link.addEventListener('click', function () {
            if (window.innerWidth <= 991.98 && appShell && appShell.classList.contains('dn-sidebar-open')) {
                appShell.classList.remove('dn-sidebar-open');
                if (overlay) overlay.classList.remove('is-visible');
            }
        });
    });

    /* ---------------------------------------------------------------------
       3. Search box — demo-only, no real query execution
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
});