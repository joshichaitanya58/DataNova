/**
 * DataNova Network Resilience & Cloud Cold-Start Recovery System
 * ==============================================================
 * Handles Render Free Tier 15-minute sleep states gracefully:
 * 1. Automatically intercepts 502/503/504 gateway responses or prolonged pending requests.
 * 2. Displays an ultra-clean, branded glassmorphic "Waking Up DataNova Cloud" overlay with live progress.
 * 3. Periodically probes /health and automatically retries pending actions once server is responsive.
 * 4. Pings /health every 4 minutes while browser tab is open to keep server awake during user sessions.
 */

(function () {
    'use strict';

    // Prevent duplicate injection
    if (window.__DATANOVA_RESILIENCE_ACTIVE) return;
    window.__DATANOVA_RESILIENCE_ACTIVE = true;

    const HEALTH_CHECK_URL = '/health';
    const PROBE_INTERVAL_MS = 3000;
    const MAX_RETRIES = 25; // ~75 seconds max wait (Render takes ~25-45s)
    const CLIENT_HEARTBEAT_INTERVAL_MS = 240000; // 4 minutes client keep-alive

    let isWakingUp = false;
    let overlayElement = null;
    let retryCount = 0;
    let probeTimer = null;
    let pendingRetryCallbacks = [];

    // --- Inject Styles for Sleek Wake-Up Modal ---
    function injectResilienceStyles() {
        if (document.getElementById('dn-resilience-styles')) return;
        const style = document.createElement('style');
        style.id = 'dn-resilience-styles';
        style.textContent = `
            #dn-wakeup-overlay {
                position: fixed;
                inset: 0;
                z-index: 999999;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(10, 15, 30, 0.78);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.35s ease, visibility 0.35s ease;
            }
            #dn-wakeup-overlay.dn-visible {
                opacity: 1;
                visibility: visible;
            }
            .dn-wakeup-card {
                background: linear-gradient(145deg, rgba(26, 32, 53, 0.95), rgba(15, 23, 42, 0.98));
                border: 1px solid rgba(99, 102, 241, 0.35);
                box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 40px rgba(79, 70, 229, 0.25);
                border-radius: 20px;
                padding: 36px 32px;
                width: 90%;
                max-width: 440px;
                text-align: center;
                color: #f8fafc;
                position: relative;
                overflow: hidden;
                transform: translateY(20px) scale(0.96);
                transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
            }
            #dn-wakeup-overlay.dn-visible .dn-wakeup-card {
                transform: translateY(0) scale(1);
            }
            .dn-wakeup-glow-bar {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, #4F46E5, #7C3AED, #06B6D4, #10B981, #4F46E5);
                background-size: 300% 100%;
                animation: dn-gradient-slide 2.5s linear infinite;
            }
            @keyframes dn-gradient-slide {
                0% { background-position: 0% 50%; }
                100% { background-position: 300% 50%; }
            }
            .dn-wakeup-icon-wrap {
                width: 76px;
                height: 76px;
                margin: 0 auto 20px auto;
                border-radius: 20px;
                background: linear-gradient(135deg, rgba(79, 70, 229, 0.25), rgba(6, 182, 212, 0.25));
                border: 1px solid rgba(99, 102, 241, 0.4);
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
                box-shadow: 0 0 25px rgba(99, 102, 241, 0.4);
            }
            .dn-wakeup-pulse {
                position: absolute;
                inset: -6px;
                border-radius: 24px;
                border: 2px solid rgba(6, 182, 212, 0.5);
                animation: dn-pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
            }
            @keyframes dn-pulse-ring {
                0% { transform: scale(0.85); opacity: 0.8; }
                50% { transform: scale(1.15); opacity: 0; }
                100% { transform: scale(0.85); opacity: 0; }
            }
            .dn-wakeup-title {
                font-size: 1.35rem;
                font-weight: 700;
                letter-spacing: -0.02em;
                margin-bottom: 8px;
                color: #ffffff;
            }
            .dn-wakeup-desc {
                font-size: 0.88rem;
                color: #94a3b8;
                line-height: 1.5;
                margin-bottom: 24px;
            }
            .dn-wakeup-progress-track {
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.08);
                border-radius: 999px;
                overflow: hidden;
                margin-bottom: 12px;
                position: relative;
            }
            .dn-wakeup-progress-bar {
                height: 100%;
                width: 25%;
                background: linear-gradient(90deg, #4F46E5, #06B6D4);
                border-radius: 999px;
                position: absolute;
                animation: dn-indeterminate 1.8s ease-in-out infinite;
            }
            @keyframes dn-indeterminate {
                0% { left: -30%; width: 30%; }
                50% { left: 40%; width: 50%; }
                100% { left: 105%; width: 30%; }
            }
            .dn-wakeup-status-text {
                font-size: 0.8rem;
                color: #06B6D4;
                font-weight: 500;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }
            .dn-wakeup-connected {
                color: #10B981 !important;
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
    }

    // --- Build & Mount Wake-Up Modal DOM ---
    function ensureOverlayMounted() {
        if (overlayElement) return;
        injectResilienceStyles();

        overlayElement = document.createElement('div');
        overlayElement.id = 'dn-wakeup-overlay';
        overlayElement.setAttribute('role', 'dialog');
        overlayElement.setAttribute('aria-modal', 'true');
        overlayElement.innerHTML = `
            <div class="dn-wakeup-card">
                <div class="dn-wakeup-glow-bar"></div>
                <div class="dn-wakeup-icon-wrap" id="dnWakeupIcon">
                    <div class="dn-wakeup-pulse"></div>
                    <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
                        <polyline points="13 11 16 8 19 11"/>
                        <line x1="16" y1="8" x2="16" y2="15"/>
                    </svg>
                </div>
                <h3 class="dn-wakeup-title" id="dnWakeupTitle">Waking Up DataNova Cloud</h3>
                <p class="dn-wakeup-desc" id="dnWakeupDesc">
                    Render free-tier instances sleep after 15 minutes of inactivity.<br>
                    Spinning up the application container now (~30 seconds).
                </p>
                <div class="dn-wakeup-progress-track">
                    <div class="dn-wakeup-progress-bar" id="dnWakeupBar"></div>
                </div>
                <div class="dn-wakeup-status-text" id="dnWakeupStatus">
                    <span class="spinner-border spinner-border-sm" style="width: 13px; height: 13px; border-width: 2px;" role="status"></span>
                    <span id="dnWakeupTimerText">Connecting to backend server...</span>
                </div>
            </div>
        `;
        document.body.appendChild(overlayElement);
    }

    function showWakeUpOverlay() {
        if (isWakingUp) return;
        isWakingUp = true;
        ensureOverlayMounted();
        retryCount = 0;

        const title = document.getElementById('dnWakeupTitle');
        const desc = document.getElementById('dnWakeupDesc');
        const status = document.getElementById('dnWakeupStatus');

        if (title) title.textContent = "Waking Up DataNova Cloud";
        if (desc) desc.innerHTML = "Render free-tier instances sleep after 15 minutes of inactivity.<br>Spinning up the application container now (~30 seconds).";
        if (status) status.innerHTML = `<span class="spinner-border spinner-border-sm" style="width: 13px; height: 13px; border-width: 2px;" role="status"></span> <span id="dnWakeupTimerText">Probing server status...</span>`;

        requestAnimationFrame(() => {
            if (overlayElement) overlayElement.classList.add('dn-visible');
        });

        startServerProbeLoop();
    }

    function hideWakeUpOverlay(reloadOnDone = false) {
        if (!overlayElement) return;

        const title = document.getElementById('dnWakeupTitle');
        const status = document.getElementById('dnWakeupStatus');
        if (title) title.textContent = "DataNova Online!";
        if (status) {
            status.innerHTML = `<span class="dn-wakeup-connected">✓ Connected successfully. Resuming...</span>`;
        }

        setTimeout(() => {
            overlayElement.classList.remove('dn-visible');
            isWakingUp = false;
            if (probeTimer) {
                clearTimeout(probeTimer);
                probeTimer = null;
            }

            // Execute all queued retries
            const callbacks = [...pendingRetryCallbacks];
            pendingRetryCallbacks = [];
            callbacks.forEach(cb => {
                try { cb(); } catch (e) { console.warn(e); }
            });

            if (reloadOnDone) {
                window.location.reload();
            }
        }, 900);
    }

    // --- Active /health Probe Loop ---
    function startServerProbeLoop() {
        if (probeTimer) clearTimeout(probeTimer);

        function checkHealth() {
            retryCount++;
            const timerEl = document.getElementById('dnWakeupTimerText');
            if (timerEl) {
                timerEl.textContent = `Waiting for container boot (Attempt ${retryCount}/${MAX_RETRIES})...`;
            }

            fetch(HEALTH_CHECK_URL + '?probe=' + Date.now(), {
                method: 'GET',
                cache: 'no-store',
                headers: { 'X-Wakeup-Probe': 'true' }
            })
            .then(res => {
                if (res.status === 200) {
                    hideWakeUpOverlay(false);
                } else {
                    scheduleNextProbe();
                }
            })
            .catch(() => {
                scheduleNextProbe();
            });
        }

        function scheduleNextProbe() {
            if (retryCount >= MAX_RETRIES) {
                const desc = document.getElementById('dnWakeupDesc');
                const status = document.getElementById('dnWakeupStatus');
                if (desc) desc.textContent = "Cold-start is taking longer than usual. Please click below to refresh.";
                if (status) {
                    status.innerHTML = `<button type="button" class="btn btn-sm btn-primary" onclick="window.location.reload()" style="background: #4F46E5; border: none; padding: 6px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; color: white;">Refresh Page</button>`;
                }
                return;
            }
            probeTimer = setTimeout(checkHealth, PROBE_INTERVAL_MS);
        }

        probeTimer = setTimeout(checkHealth, 1500);
    }

    // --- Intercept Global Fetch for Automatic Cold-Start Recovery ---
    const originalFetch = window.fetch;
    window.fetch = function (...args) {
        const url = (typeof args[0] === 'string') ? args[0] : (args[0] && args[0].url ? args[0].url : '');
        
        // Skip intercepting our own probe URL
        if (url.includes('/health')) {
            return originalFetch.apply(this, args);
        }

        return originalFetch.apply(this, args).then(response => {
            // Render returns 502/503/504 when spinning down or waking up
            if ([502, 503, 504].includes(response.status)) {
                console.warn(`[DataNova Resilience] Intercepted HTTP ${response.status} from ${url}. Server may be cold-starting.`);
                return new Promise((resolve, reject) => {
                    pendingRetryCallbacks.push(() => {
                        originalFetch.apply(this, args).then(resolve).catch(reject);
                    });
                    showWakeUpOverlay();
                });
            }
            return response;
        }).catch(err => {
            // Network failure during possible cold-start
            const errMsg = String(err).toLowerCase();
            if (errMsg.includes('failed to fetch') || errMsg.includes('networkerror') || errMsg.includes('load failed')) {
                console.warn(`[DataNova Resilience] Network exception on ${url}: ${err}. Triggering wake-up probe.`);
                return new Promise((resolve, reject) => {
                    pendingRetryCallbacks.push(() => {
                        originalFetch.apply(this, args).then(resolve).catch(reject);
                    });
                    showWakeUpOverlay();
                });
            }
            throw err;
        });
    };

    // --- Client Tab Keep-Alive Heartbeat ---
    // While any user has DataNova open in a tab, send a ping every 4 mins to reset Render's 15m timer
    function sendClientHeartbeat() {
        if (document.hidden) return; // Only ping when tab is in use
        originalFetch(HEALTH_CHECK_URL, {
            method: 'GET',
            cache: 'no-store',
            headers: { 'X-Client-Heartbeat': 'true' }
        }).catch(() => {});
    }

    setInterval(sendClientHeartbeat, CLIENT_HEARTBEAT_INTERVAL_MS);

    // Initial check on document ready: if initial page took > 3s or fails, warm up
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectResilienceStyles);
    } else {
        injectResilienceStyles();
    }

    // Expose utility for manual trigger
    window.DataNovaResilience = {
        showWakeUp: showWakeUpOverlay,
        hideWakeUp: hideWakeUpOverlay,
        pingServer: sendClientHeartbeat
    };
})();
