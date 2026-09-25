/**
 * Centralised frontend configuration, API access and session handling.
 *
 * Phase 1 of the hardening work:
 *  - one configurable API base URL instead of ~35 hard-coded hosts;
 *  - real authentication: the JWT returned by /api/auth/login is stored and
 *    sent as `Authorization: Bearer <token>`;
 *  - automatic handling of an expired/invalid session (401) instead of silently
 *    rendering an empty page;
 *  - HTML escaping helpers so user-supplied values can never be injected as
 *    markup through innerHTML.
 *
 * Load order: this file must be included BEFORE js/app.js.
 */
(function (global) {
    'use strict';

    // ---------------------------------------------------------------- config
    // Resolve the API base once. Precedence:
    //   1. <body data-api-base="..."> or window.APP_CONFIG_API_BASE (deployment)
    //   2. localStorage override (useful when testing against another machine)
    //   3. same-origin when the frontend is served by the API itself
    //   4. http://localhost:8000 (local development default)
    function resolveApiBase() {
        var configured = global.APP_CONFIG_API_BASE;
        if (!configured && document.body) {
            configured = document.body.getAttribute('data-api-base');
        }
        if (!configured) {
            try {
                configured = global.localStorage.getItem('smartfarm_api_base');
            } catch (storageError) {
                configured = null;
            }
        }
        if (configured) {
            return String(configured).replace(/\/+$/, '');
        }
        if (global.location && global.location.port && global.location.port !== '5500') {
            return global.location.origin;
        }
        return 'http://localhost:8000';
    }

    var API_BASE = resolveApiBase();

    /** Build an absolute API URL from a path such as '/api/sessions'. */
    function apiUrl(path) {
        if (!path) return API_BASE;
        if (/^https?:\/\//i.test(path)) return path;
        return API_BASE + (path.charAt(0) === '/' ? path : '/' + path);
    }

    // ---------------------------------------------------------------- session
    var TOKEN_KEY = 'smartfarm_token';
    var USER_KEY = 'smartfarm_user';

    function getToken() {
        try {
            return global.localStorage.getItem(TOKEN_KEY);
        } catch (storageError) {
            return null;
        }
    }

    function setSession(token, user) {
        try {
            if (token) global.localStorage.setItem(TOKEN_KEY, token);
            if (user) global.localStorage.setItem(USER_KEY, JSON.stringify(user));
        } catch (storageError) {
            /* private browsing: the session simply does not persist */
        }
    }

    function getUser() {
        try {
            return JSON.parse(global.localStorage.getItem(USER_KEY) || 'null');
        } catch (storageError) {
            return null;
        }
    }

    function clearSession() {
        try {
            global.localStorage.removeItem(TOKEN_KEY);
            global.localStorage.removeItem(USER_KEY);
        } catch (storageError) {
            /* nothing to clear */
        }
    }

    function isAuthenticated() {
        return Boolean(getToken());
    }

    // ---------------------------------------------------------------- escaping
    var HTML_ESCAPES = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };

    /** Escape a value before interpolating it into an innerHTML template. */
    function escapeHtml(value) {
        if (value === null || value === undefined) return '';
        return String(value).replace(/[&<>"']/g, function (character) {
            return HTML_ESCAPES[character];
        });
    }

    /**
     * Build a DOM element with text content set safely.
     * Preferred over innerHTML whenever the value originates from the API.
     */
    function setText(element, value) {
        if (element) element.textContent = value === null || value === undefined ? '' : String(value);
        return element;
    }

    function formatCurrency(value) {
        var number = Number(value);
        if (!isFinite(number)) return '-';
        return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function formatNumber(value, fallback) {
        var number = Number(value);
        if (!isFinite(number)) return fallback === undefined ? '-' : fallback;
        return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    // ---------------------------------------------------------------- fetch
    var nativeFetch = global.fetch.bind(global);
    var sessionExpiryNotified = false;

    function notifySessionExpired() {
        if (sessionExpiryNotified) return;
        sessionExpiryNotified = true;
        clearSession();
        if (typeof global.showAuthView === 'function') {
            global.showAuthView('login');
        }
        if (global.alert) {
            global.alert('Your session has expired. Please sign in again.');
        }
        sessionExpiryNotified = false;
    }

    /**
     * Every request made by the SPA goes through here: the Bearer token is
     * attached centrally and a 401 ends the session instead of leaving the UI in
     * a half-loaded state. The Version-1 `X-User-Id` header is no longer sent -
     * it was a client-asserted identity that any caller could forge.
     */
    function apiFetch(resource, config) {
        var options = config || {};
        var token = getToken();
        if (token) {
            options.headers = options.headers || {};
            if (options.headers instanceof Headers) {
                options.headers.set('Authorization', 'Bearer ' + token);
            } else {
                options.headers['Authorization'] = 'Bearer ' + token;
            }
        }
        return nativeFetch(resource, options).then(function (response) {
            if (response.status === 401 && token) {
                notifySessionExpired();
            }
            return response;
        });
    }

    /**
     * Read a JSON response, turning an API error into a thrown Error carrying
     * the server's `detail` message.
     */
    function readJson(response) {
        return response.text().then(function (body) {
            var data = null;
            if (body) {
                try {
                    data = JSON.parse(body);
                } catch (parseError) {
                    data = null;
                }
            }
            if (!response.ok) {
                var detail = (data && (data.detail || data.message)) || ('Request failed (' + response.status + ')');
                if (typeof detail !== 'string') detail = JSON.stringify(detail);
                var error = new Error(detail);
                error.status = response.status;
                error.payload = data;
                throw error;
            }
            return data;
        });
    }

    // Expose the helpers. `fetch` is replaced so existing call sites in app.js
    // automatically become authenticated without touching all of them.
    global.APP_CONFIG = {
        apiBase: API_BASE,
        setApiBase: function (value) {
            try {
                global.localStorage.setItem('smartfarm_api_base', value);
            } catch (storageError) {
                /* ignore */
            }
            API_BASE = String(value).replace(/\/+$/, '');
            global.APP_CONFIG.apiBase = API_BASE;
        }
    };
    global.apiUrl = apiUrl;
    global.apiFetch = apiFetch;
    // Unauthenticated transport, used by the login / register / OTP forms so a
    // stale token can never be attached to a credential request.
    global.rawFetch = nativeFetch;
    global.readJson = readJson;
    global.getToken = getToken;
    global.getStoredUser = getUser;
    global.setSession = setSession;
    global.clearSession = clearSession;
    global.isAuthenticated = isAuthenticated;
    global.escapeHtml = escapeHtml;
    global.setText = setText;
    global.formatCurrency = formatCurrency;
    global.formatNumber = formatNumber;
    global.fetch = apiFetch;
})(window);
