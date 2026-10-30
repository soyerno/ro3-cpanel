/**
 * RO3 Control Panel - White-Label Administration Client
 * Vanilla JavaScript SPA with zero external dependencies
 */

(function () {
  'use strict';

  // Application State
  var state = {
    authenticated: false,
    adminUser: null,
    branding: {
      server_title: 'RO3 Control Panel',
      server_subtitle: 'Ragnarok Online 3 Management',
      logo_text: 'RO3'
    },
    stats: null,
    // false when RO3Emu has no account_ban table (an older server cannot enforce a ban).
    bansSupported: true,
    accounts: [],
    filteredAccounts: [],
    auditLogs: [],
    rankingType: 'level',
    rankingPage: 1,
    rankingTotal: 0,
    rankingLimit: 20,
    activeTab: 'accounts',
    searchQuery: '',
    statusFilter: 'all',
    sortBy: 'created_desc',
    accountsPage: 1,
    accountsPages: 1,
    accountsTotal: 0,
    selectedAccount: null,
    economy: {
      account: '',
      character: '',
      from: '',
      to: '',
      page: 1,
      pageSize: 50,
      pages: 1
    },
    guildQuery: '',
    auditPage: 1,
    auditPages: 1,
    auditTotal: 0,
    guildsPage: 1,
    guildsPages: 1,
    guildsTotal: 0,
    auctionView: 'lots',
    auctionsPage: 1,
    auctionsPages: 1,
    auctionsTotal: 0,
    market: {
      status: 'active',
      query: '',
      page: 1,
      pages: 1,
      total: 0,
      request: 0
    },
    // Account management screen (hash route #/accounts/<name>[/<tab>]).
    accountScreen: {
      open: false,
      name: '',
      tab: 'characters',
      data: null,
      status: 'idle',
      request: 0,
      notesBaseline: '',
      listScroll: 0,
      saving: false
    },
    // Shared account vault shown in the account screen's Vault tab (read-only).
    vault: {
      account: '',
      page: 1,
      pages: 1,
      loaded: false,
      request: 0,
      status: 'idle',
      requestedPage: 1,
      data: null,
      vip: null,
      message: ''
    }
  };

  // DOM Elements
  var els = {
    loginScreen: document.getElementById('login-screen'),
    loginForm: document.getElementById('login-form'),
    loginUser: document.getElementById('login-user'),
    loginPass: document.getElementById('login-pass'),
    loginError: document.getElementById('login-error'),
    loginSubmit: document.getElementById('login-submit'),

    appHeader: document.getElementById('app-header'),
    subnav: document.getElementById('app-subnav'),
    appShell: document.getElementById('app-shell'),
    sidebarOpen: document.getElementById('sidebar-open'),
    sidebarClose: document.getElementById('sidebar-close'),
    sidebarCollapse: document.getElementById('sidebar-collapse'),
    sidebarBackdrop: document.getElementById('sidebar-backdrop'),
    mainContent: document.getElementById('main-content'),
    adminName: document.getElementById('admin-name'),
    btnLogout: document.getElementById('btn-logout'),

    // Branding targets
    brandTitles: document.querySelectorAll('[data-brand-title]'),
    brandSubtitles: document.querySelectorAll('[data-brand-subtitle]'),
    brandLogos: document.querySelectorAll('[data-brand-logo]'),

    serverStatusDot: document.getElementById('server-status-dot'),
    serverStatusText: document.getElementById('server-status-text'),
    serverOnlineCount: document.getElementById('server-online-count'),

    statAccounts: document.getElementById('stat-accounts'),
    statChars: document.getElementById('stat-chars'),
    statOnline: document.getElementById('stat-online'),
    statBanned: document.getElementById('stat-banned'),
    tabAccountsCount: document.getElementById('tab-accounts-count'),

    // RO3Emu diagnostics (dashboard)
    metricsPanel: document.getElementById('metrics-panel'),
    metricsUnavailable: document.getElementById('metrics-unavailable'),
    metricsGrid: document.getElementById('metrics-grid'),
    metricsCaptured: document.getElementById('metrics-captured'),
    metricUptime: document.getElementById('metric-uptime'),
    metricConnections: document.getElementById('metric-connections'),
    metricInWorld: document.getElementById('metric-in-world'),
    metricMemory: document.getElementById('metric-memory'),
    metricDb: document.getElementById('metric-db'),
    metricErrors: document.getElementById('metric-errors'),
    onlineUnavailable: document.getElementById('online-unavailable'),
    onlineTableWrap: document.getElementById('online-table-wrap'),
    onlineTbody: document.getElementById('online-tbody'),
    onlineIpTh: document.getElementById('online-ip-th'),
    onlineCountLabel: document.getElementById('online-count-label'),

    searchInput: document.getElementById('search-input'),
    statusSelect: document.getElementById('status-select'),
    sortSelect: document.getElementById('sort-select'),
    accountsTbody: document.getElementById('accounts-tbody'),
    accountsPager: document.getElementById('accounts-pager'),
    pagerPrev: document.getElementById('pager-prev'),
    pagerNext: document.getElementById('pager-next'),
    pagerInfo: document.getElementById('pager-info'),

    tabViewDashboard: document.getElementById('tab-view-dashboard'),
    tabViewAccounts: document.getElementById('tab-view-accounts'),
    tabViewAudit: document.getElementById('tab-view-audit'),
    auditTbody: document.getElementById('audit-tbody'),
    auditPager: document.getElementById('audit-pager'),
    auditPagerPrev: document.getElementById('audit-pager-prev'),
    auditPagerNext: document.getElementById('audit-pager-next'),
    auditPagerInfo: document.getElementById('audit-pager-info'),
    tabViewEconomy: document.getElementById('tab-view-economy'),
    economyForm: document.getElementById('economy-filter-form'),
    economyAccount: document.getElementById('economy-account'),
    economyCharacter: document.getElementById('economy-character'),
    economyFrom: document.getElementById('economy-from'),
    economyTo: document.getElementById('economy-to'),
    economyTbody: document.getElementById('economy-tbody'),
    economyUnavailable: document.getElementById('economy-unavailable'),
    economyPrev: document.getElementById('economy-prev'),
    economyNext: document.getElementById('economy-next'),
    economyPageInfo: document.getElementById('economy-page-info'),
    tabViewRankings: document.getElementById('tab-view-rankings'),
    rankingTypeSelect: document.getElementById('ranking-type-select'),
    rankingPrev: document.getElementById('ranking-prev'),
    rankingNext: document.getElementById('ranking-next'),
    rankingPageLabel: document.getElementById('ranking-page-label'),
    rankingsThead: document.getElementById('rankings-thead'),
    rankingsTbody: document.getElementById('rankings-tbody'),

    tabViewGuilds: document.getElementById('tab-view-guilds'),
    guildSearchInput: document.getElementById('guild-search-input'),
    guildsUnavailable: document.getElementById('guilds-unavailable'),
    guildsTbody: document.getElementById('guilds-tbody'),
    guildsPager: document.getElementById('guilds-pager'),
    guildsPagerPrev: document.getElementById('guilds-pager-prev'),
    guildsPagerNext: document.getElementById('guilds-pager-next'),
    guildsPagerInfo: document.getElementById('guilds-pager-info'),
    modalGuild: document.getElementById('modal-guild'),

    tabViewAuctions: document.getElementById('tab-view-auctions'),
    auctionViewSelect: document.getElementById('auction-view-select'),
    auctionsUnavailable: document.getElementById('auctions-unavailable'),
    auctionsThead: document.getElementById('auctions-thead'),
    auctionsTbody: document.getElementById('auctions-tbody'),
    auctionsPager: document.getElementById('auctions-pager'),
    auctionsPagerPrev: document.getElementById('auctions-pager-prev'),
    auctionsPagerNext: document.getElementById('auctions-pager-next'),
    auctionsPagerInfo: document.getElementById('auctions-pager-info'),

    tabViewGiftCodes: document.getElementById('tab-view-giftcodes'),
    giftCodesTbody: document.getElementById('giftcodes-tbody'),
    giftCodesTableWrap: document.getElementById('giftcodes-table-wrap'),
    giftCodesUnavailable: document.getElementById('giftcodes-unavailable'),
    btnNewGiftCode: document.getElementById('btn-new-giftcode'),
    modalGiftCode: document.getElementById('modal-giftcode'),
    giftCodeItems: document.getElementById('giftcode-items'),
    giftCodeError: document.getElementById('giftcode-error'),

    tabViewMarket: document.getElementById('tab-view-market'),
    marketForm: document.getElementById('market-filter-form'),
    marketStatusSelect: document.getElementById('market-status-select'),
    marketSearchInput: document.getElementById('market-search-input'),
    marketUnavailable: document.getElementById('market-unavailable'),
    marketSummary: document.getElementById('market-summary'),
    marketTableWrap: document.getElementById('market-table-wrap'),
    marketTbody: document.getElementById('market-tbody'),
    marketPager: document.getElementById('market-pager'),
    marketPagerPrev: document.getElementById('market-pager-prev'),
    marketPagerNext: document.getElementById('market-pager-next'),
    marketPagerInfo: document.getElementById('market-pager-info'),

    // Account management screen
    accountScreen: document.getElementById('account-screen'),
    accountTitle: document.getElementById('account-title'),
    accountBreadcrumbCurrent: document.getElementById('account-breadcrumb-current'),
    accountBadges: document.getElementById('account-badges'),
    accountRegistered: document.getElementById('account-registered'),
    accountSessions: document.getElementById('account-sessions'),
    accountStatusText: document.getElementById('account-status-text'),
    accountState: document.getElementById('account-state'),
    accountBody: document.getElementById('account-body'),
    accountSummary: document.getElementById('account-summary'),
    accountNotes: document.getElementById('account-notes'),
    accountNotesStatus: document.getElementById('account-notes-status'),
    accountSaveNotes: document.getElementById('account-save-notes'),
    accountTabButtons: document.querySelectorAll('.account-tab'),
    accountCharacters: document.getElementById('account-characters'),
    accountGmSlot: document.getElementById('account-gm-slot'),
    accountVault: document.getElementById('account-vault-content'),
    accountAccessText: document.getElementById('account-access-text'),
    accountSessionsText: document.getElementById('account-sessions-text'),
    accountBtnPassword: document.getElementById('account-btn-password'),
    accountBtnBan: document.getElementById('account-btn-ban'),
    accountBtnUnban: document.getElementById('account-btn-unban'),
    accountBtnDelete: document.getElementById('account-btn-delete'),
    accountDangerZone: document.getElementById('account-danger-zone'),

    // Modals
    modalPassword: document.getElementById('modal-password'),
    modalCreate: document.getElementById('modal-create'),
    modalBan: document.getElementById('modal-ban'),
    modalDelete: document.getElementById('modal-delete'),
    modalConfirm: document.getElementById('modal-confirm'),
    formConfirm: document.getElementById('form-confirm'),
    confirmTitle: document.getElementById('confirm-modal-title'),
    confirmMessage: document.getElementById('confirm-message'),
    confirmTypedGroup: document.getElementById('confirm-typed-group'),
    confirmTypedLabel: document.getElementById('confirm-typed-label'),
    confirmTypedInput: document.getElementById('confirm-typed-input'),
    confirmSubmit: document.getElementById('confirm-submit'),
    confirmCancel: document.getElementById('confirm-cancel'),

    toasts: document.getElementById('toast-container')
  };

  // --- i18n ---
  // The English text is the key; public/locales/es.json maps it to Spanish.
  // Missing keys, a failed dictionary fetch or an unknown language all fall back to English.
  var LANG_STORAGE_KEY = 'panel_lang';
  var LOCALE_URL = '/locales/es.json';
  var i18n = { lang: 'en', es: {}, stored: false };

  function isSupportedLang(lang) {
    return lang === 'en' || lang === 'es';
  }

  function readStoredLang() {
    try {
      var value = globalThis.localStorage.getItem(LANG_STORAGE_KEY);
      return isSupportedLang(value) ? value : null;
    } catch (e) {
      return null;
    }
  }

  function storeLang(lang) {
    i18n.stored = true;
    try {
      globalThis.localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch (e) {
      // Storage can be unavailable (private mode); the choice then lasts for this page only.
    }
  }

  function t(key, params) {
    var text = key;
    if (i18n.lang === 'es' && Object.prototype.hasOwnProperty.call(i18n.es, key)) {
      var translated = i18n.es[key];
      if (typeof translated === 'string' && translated) text = translated;
    }
    if (!params) return text;
    return text.replace(/\{(\w+)\}/g, function (match, name) {
      return Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match;
    });
  }

  function applyI18n(root) {
    root = root || document;
    document.documentElement.lang = i18n.lang;
    root.querySelectorAll('[data-i18n]').forEach(function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    ['placeholder', 'title', 'aria-label'].forEach(function (attr) {
      root.querySelectorAll('[data-i18n-' + attr + ']').forEach(function (el) {
        el.setAttribute(attr, t(el.getAttribute('data-i18n-' + attr)));
      });
    });
    // Labels that depend on the sidebar state are not static text, so they are set again here.
    if (root === document) refreshSidebarLabels();
  }

  function updateLangButtons() {
    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      var active = btn.getAttribute('data-lang') === i18n.lang;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  // Re-translate the static DOM and reload the active view so server-provided labels follow the language.
  function relocalize() {
    applyI18n(document);
    updateLangButtons();
    if (state.authenticated) {
      updateStatsUI();
      switchTab(state.activeTab);
      // The open account follows the language too (server labels are localized); notes in progress are kept.
      if (isAccountScreenOpen()) loadAccountScreen(state.accountScreen.name, true);
    }
  }

  function setLanguage(lang, persist) {
    i18n.lang = isSupportedLang(lang) ? lang : 'en';
    if (persist) storeLang(i18n.lang);
    relocalize();
  }

  function loadLocale() {
    return fetch(LOCALE_URL, { credentials: 'same-origin', headers: { 'X-Panel-Lang': i18n.lang } })
      .then(function (res) {
        return res.ok ? res.json() : {};
      })
      .then(function (dict) {
        if (dict && typeof dict === 'object' && !Array.isArray(dict)) i18n.es = dict;
        if (i18n.lang === 'es') relocalize();
      })
      .catch(function () {
        // English keeps working without the dictionary.
      });
  }

  function handleLangClick() {
    var lang = this.getAttribute('data-lang');
    if (!isSupportedLang(lang)) return;
    if (lang === i18n.lang) {
      storeLang(lang);
      return;
    }
    setLanguage(lang, true);
  }

  // --- UI helpers (accessibility, loading and error states) ---
  // The pure helpers sit between the markers below; tests/test_admin_polish_ui.py runs them with node.
  // ui-helpers:begin
  // Row buttons are named "<visible text>: <account>" so a screen reader list is not ten identical "Manage".
  function actionLabel(text, account) {
    return account ? text + ': ' + account : text;
  }

  // Only errors interrupt a screen reader; every other toast waits for its turn.
  function toastRole(type) {
    return type === 'error' ? 'alert' : 'status';
  }

  // Tab / Shift+Tab inside a dialog: the control to focus, or null when the browser may decide.
  function focusTrapTarget(focusables, active, backwards) {
    if (!focusables.length) return null;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (focusables.indexOf(active) === -1) return backwards ? last : first;
    if (backwards && active === first) return last;
    if (!backwards && active === last) return first;
    return null;
  }
  // ui-helpers:end

  // aria-busy follows the requests that fill a region; overlapping requests keep it busy until the last one ends.
  var busyCounts = new WeakMap();

  function trackBusy(el, promise) {
    if (!el) return promise;
    busyCounts.set(el, (busyCounts.get(el) || 0) + 1);
    el.setAttribute('aria-busy', 'true');
    var done = function () {
      var left = Math.max(0, (busyCounts.get(el) || 1) - 1);
      busyCounts.set(el, left);
      if (!left) el.setAttribute('aria-busy', 'false');
    };
    promise.then(done, done);
    return promise;
  }

  // A button that sends a request is locked (and shows a spinner) until the request ends.
  function setSubmitting(btn, busy) {
    if (!btn) return;
    btn.disabled = busy;
    btn.classList.toggle('is-loading', busy);
    btn.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  function submitButtonOf(e) {
    var form = e && e.target && e.target.closest ? e.target.closest('form') : null;
    return form ? form.querySelector('button[type="submit"]') : null;
  }

  // A failed load never leaves "Loading..." behind: the row says what happened and offers a retry.
  function errorRowHtml(colspan, message, retryKey) {
    return '<tr><td colspan="' + colspan + '" class="table-state"><div class="table-error" role="alert"><p>' + escapeHtml(message) + '</p>' +
      '<button type="button" class="btn btn-secondary btn-sm" data-retry="' + escapeHtml(retryKey) + '">' + escapeHtml(t('Retry')) + '</button></div></td></tr>';
  }

  // --- Toast Notifications ---
  function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.setAttribute('role', toastRole(type));
    toast.innerHTML = '<span>' + escapeHtml(message) + '</span>';
    els.toasts.appendChild(toast);
    // Errors stay longer so they can be read.
    setTimeout(function () {
      toast.classList.add('is-leaving');
      setTimeout(function () { toast.remove(); }, 300);
    }, type === 'error' ? 8000 : 4000);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return Number(num).toLocaleString(i18n.lang);
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleString(i18n.lang, {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (e) {
      return isoStr;
    }
  }

  // --- API Helper ---
  function apiFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.credentials = 'include';
    options.headers['X-Panel-Lang'] = i18n.lang;
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    return fetch(url, options).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error(data && data.error ? data.error : 'HTTP ' + res.status);
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  // --- Branding Loader ---
  function loadBranding() {
    apiFetch('/api/admin/config')
      .then(function (cfg) {
        if (cfg) {
          state.branding = cfg;
          applyBranding();
          if (!i18n.stored && isSupportedLang(cfg.default_language) && cfg.default_language !== i18n.lang) {
            setLanguage(cfg.default_language, false);
          }
        }
      })
      .catch(function () {
        // Fallback to default
        applyBranding();
      });
  }

  function applyBranding() {
    document.title = state.branding.server_title + ' - Admin CPanel';

    els.brandTitles.forEach(function (el) {
      el.textContent = state.branding.server_title;
    });
    els.brandSubtitles.forEach(function (el) {
      el.textContent = state.branding.server_subtitle;
    });
    els.brandLogos.forEach(function (el) {
      if (state.branding.logo_image_url) {
        var alt = state.branding.logo_text || 'Logo';
        el.innerHTML = '<img src="' + escapeHtml(state.branding.logo_image_url) + '" alt="' + escapeHtml(alt) + '" class="brand-logo-img">';
      } else {
        el.textContent = state.branding.logo_text;
      }
    });
  }

  // --- Authentication ---
  function checkSession() {
    apiFetch('/api/admin/session')
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          setAuthenticated(data.user);
        } else {
          setUnauthenticated();
        }
      })
      .catch(function () {
        setUnauthenticated();
      });
  }

  function setAuthenticated(user) {
    state.authenticated = true;
    state.adminUser = user;
    if (els.adminName) els.adminName.textContent = user;
    if (els.loginScreen) els.loginScreen.hidden = true;
    if (els.appHeader) els.appHeader.hidden = false;
    if (els.subnav) els.subnav.hidden = false;
    if (els.mainContent) els.mainContent.hidden = false;

    loadStats();
    loadAccounts();
    // A deep link (#/accounts/<name>) opens its account once the session is known.
    handleRouteChange();
  }

  function setUnauthenticated() {
    closeSidebarDrawer(false);
    state.authenticated = false;
    state.adminUser = null;
    resetAccountScreen(true);
    renderAccountsViews();
    if (els.loginScreen) els.loginScreen.hidden = false;
    if (els.appHeader) els.appHeader.hidden = true;
    if (els.subnav) els.subnav.hidden = true;
    if (els.mainContent) els.mainContent.hidden = true;
    if (els.loginError) els.loginError.hidden = true;
  }

  var loginLockoutTimer = null;
  var isLoginSubmitting = false;

  function startLoginLockout(seconds) {
    if (loginLockoutTimer) clearInterval(loginLockoutTimer);
    var remaining = Math.max(1, Math.ceil(seconds));
    if (els.loginSubmit) {
      els.loginSubmit.disabled = true;
      els.loginSubmit.textContent = t('Temporarily banned ({seconds}s)', { seconds: remaining });
    }
    loginLockoutTimer = setInterval(function () {
      remaining--;
      if (remaining <= 0) {
        clearInterval(loginLockoutTimer);
        loginLockoutTimer = null;
        if (els.loginSubmit) {
          els.loginSubmit.disabled = false;
          els.loginSubmit.textContent = t('Access Panel');
        }
        if (els.loginError) {
          els.loginError.hidden = true;
        }
      } else {
        if (els.loginSubmit) {
          els.loginSubmit.textContent = t('Temporarily banned ({seconds}s)', { seconds: remaining });
        }
      }
    }, 1000);
  }

  function derivePbkdf2Hash(password, saltHex, iterations) {
    if (!window.crypto || !window.crypto.subtle) return Promise.reject(new Error('WebCrypto unavailable'));
    var enc = new TextEncoder();
    return window.crypto.subtle.importKey(
      'raw',
      enc.encode(password),
      { name: 'PBKDF2' },
      false,
      ['deriveBits']
    ).then(function (keyMaterial) {
      var saltBytes = new Uint8Array(saltHex.match(/.{1,2}/g).map(function (b) { return parseInt(b, 16); }));
      return window.crypto.subtle.deriveBits(
        {
          name: 'PBKDF2',
          salt: saltBytes,
          iterations: iterations || 100000,
          hash: 'SHA-256'
        },
        keyMaterial,
        256
      );
    }).then(function (bits) {
      return Array.from(new Uint8Array(bits)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    });
  }

  function handleLogin(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (isLoginSubmitting || loginLockoutTimer) return;
    var user = (els.loginUser.value || '').trim();
    var pass = els.loginPass.value || '';

    if (!user || !pass) {
      showLoginError(t('Please enter username and password.'));
      return;
    }

    if (user.length > 32) {
      showLoginError(t('Username must not exceed 32 characters.'));
      return;
    }

    if (pass.length > 128) {
      showLoginError(t('Password must not exceed 128 characters.'));
      return;
    }

    isLoginSubmitting = true;
    els.loginSubmit.disabled = true;
    els.loginSubmit.textContent = t('Verifying...');
    if (els.loginError) els.loginError.hidden = true;

    // Zero-plaintext authentication: derive PBKDF2 hash directly in browser with salt from server
    apiFetch('/api/admin/auth/salt?username=' + encodeURIComponent(user))
      .then(function (saltData) {
        if (saltData && saltData.salt) {
          return derivePbkdf2Hash(pass, saltData.salt, saltData.iterations)
            .then(function (hashHex) {
              return { username: user, password_hash: hashHex };
            })
            .catch(function () {
              return { username: user, password: pass };
            });
        }
        return { username: user, password: pass };
      })
      .catch(function () {
        return { username: user, password: pass };
      })
      .then(function (payload) {
        return apiFetch('/api/admin/login', {
          method: 'POST',
          body: payload
        });
      })
      .then(function (data) {
        if (loginLockoutTimer) {
          clearInterval(loginLockoutTimer);
          loginLockoutTimer = null;
        }
        showToast(t('Welcome, {user} (Administrator)', { user: data.user }), 'success');
        els.loginPass.value = '';
        setAuthenticated(data.user);
      })
      .catch(function (err) {
        showLoginError(err.message || t('Invalid credentials'));
        if (err.status === 429 || (err.data && (err.data.temporary_ban || err.data.retry_after))) {
          var wait = (err.data && err.data.retry_after) ? parseInt(err.data.retry_after, 10) : 60;
          startLoginLockout(wait);
        }
      })
      .finally(function () {
        isLoginSubmitting = false;
        if (!loginLockoutTimer) {
          els.loginSubmit.disabled = false;
          els.loginSubmit.textContent = t('Access Panel');
        }
      });
  }

  function showLoginError(msg) {
    if (!els.loginError) return;
    els.loginError.textContent = msg;
    els.loginError.hidden = false;
  }

  function handleLogout() {
    if (!confirm(t('Do you want to end the administration session?'))) return;
    apiFetch('/api/admin/logout', { method: 'POST' })
      .finally(function () {
        showToast(t('Session closed successfully'), 'info');
        setUnauthenticated();
      });
  }

  // --- Stats & Accounts ---
  function loadStats() {
    apiFetch('/api/admin/stats')
      .then(function (data) {
        state.stats = data;
        updateStatsUI();
      })
      .catch(function (err) {
        showToast(t('Error loading statistics: {message}', { message: err.message }), 'error');
      });
  }

  function updateStatsUI() {
    if (!state.stats) return;
    var s = state.stats;

    if (els.serverStatusDot) {
      els.serverStatusDot.className = 'status-dot ' + (s.server.online ? 'online' : '');
    }
    if (els.serverStatusText) {
      els.serverStatusText.textContent = s.server.online ? t('Online') : t('Offline');
    }
    if (els.serverOnlineCount) {
      els.serverOnlineCount.textContent = s.server.players_online;
    }

    if (els.statAccounts) els.statAccounts.textContent = formatNumber(s.counts.accounts);
    if (els.statChars) els.statChars.textContent = formatNumber(s.counts.characters);
    if (els.statOnline) els.statOnline.textContent = formatNumber(s.server.players_online);
    if (els.statBanned) {
      els.statBanned.textContent = formatNumber(s.counts.banned);
      els.statBanned.title = s.bans_supported === false ? t('Update RO3Emu: this server does not support account bans') : '';
    }
    if (els.tabAccountsCount) els.tabAccountsCount.textContent = s.counts.accounts;
  }

  // --- RO3Emu diagnostics (optional: loopback-only endpoints) ---
  function isNum(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function formatDuration(seconds) {
    if (!isNum(seconds)) return '—';
    var total = Math.floor(seconds);
    var d = Math.floor(total / 86400);
    var h = Math.floor((total % 86400) / 3600);
    var m = Math.floor((total % 3600) / 60);
    if (d > 0) return d + 'd ' + h + 'h';
    if (h > 0) return h + 'h ' + m + 'm';
    return m + 'm ' + (total % 60) + 's';
  }

  function formatBytes(bytes) {
    if (!isNum(bytes)) return '—';
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var value = bytes;
    var i = 0;
    while (value >= 1024 && i < units.length - 1) {
      value = value / 1024;
      i++;
    }
    return (i === 0 ? String(value) : value.toFixed(1)) + ' ' + units[i];
  }

  function formatMetric(v) {
    return isNum(v) ? formatNumber(v) : '—';
  }

  function setUnavailable(el, reason) {
    if (!el) return;
    el.textContent = reason ? t('Not available: {reason}', { reason: reason }) : t('Not available');
    el.hidden = false;
  }

  function loadServerMetrics() {
    apiFetch('/api/admin/metrics')
      .then(function (data) {
        renderServerMetrics(data);
      })
      .catch(function (err) {
        renderServerMetrics({ available: false, reason: err.message });
      });
  }

  function renderServerMetrics(data) {
    if (!els.metricsPanel) return;
    if (!data || !data.available || !data.metrics) {
      if (els.metricsGrid) els.metricsGrid.hidden = true;
      if (els.metricsCaptured) els.metricsCaptured.textContent = '';
      setUnavailable(els.metricsUnavailable, data && data.reason);
      return;
    }
    var m = data.metrics;
    var sessions = m.sessions || {};
    var db = m.database || {};
    var runtime = m.runtime || {};
    var errors = m.errors || {};

    if (els.metricsUnavailable) els.metricsUnavailable.hidden = true;
    if (els.metricsGrid) els.metricsGrid.hidden = false;
    if (els.metricUptime) els.metricUptime.textContent = formatDuration(m.uptime_seconds);
    if (els.metricConnections) els.metricConnections.textContent = formatMetric(m.connections);
    if (els.metricInWorld) els.metricInWorld.textContent = formatMetric(sessions.in_world);
    if (els.metricMemory) els.metricMemory.textContent = formatBytes(runtime.working_set_bytes);
    if (els.metricDb) els.metricDb.textContent = formatMetric(db.statements) + ' / ' + formatMetric(db.commits);
    if (els.metricErrors) els.metricErrors.textContent = formatMetric(errors.exceptions) + ' / ' + formatMetric(errors.error_logs);
    if (els.metricsCaptured) {
      els.metricsCaptured.textContent = m.captured_utc ? t('Captured: {date}', { date: formatDate(m.captured_utc) }) : '';
    }
  }

  function loadOnlinePlayers() {
    apiFetch('/api/admin/online')
      .then(function (data) {
        renderOnlinePlayers(data);
      })
      .catch(function (err) {
        renderOnlinePlayers({ available: false, reason: err.message });
      });
  }

  function renderOnlinePlayers(data) {
    if (!els.onlineTbody) return;
    if (!data || !data.available) {
      if (els.onlineTableWrap) els.onlineTableWrap.hidden = true;
      if (els.onlineCountLabel) els.onlineCountLabel.textContent = '';
      setUnavailable(els.onlineUnavailable, data && data.reason);
      return;
    }
    var players = data.players || [];
    var showIps = data.show_ips === true;
    var cols = showIps ? 5 : 4;

    if (els.onlineUnavailable) els.onlineUnavailable.hidden = true;
    if (els.onlineTableWrap) els.onlineTableWrap.hidden = false;
    if (els.onlineIpTh) els.onlineIpTh.hidden = !showIps;
    if (els.onlineCountLabel) els.onlineCountLabel.textContent = t('{count} sessions', { count: players.length });

    if (players.length === 0) {
      els.onlineTbody.innerHTML = emptyRow(cols, t('No players connected.'));
      return;
    }

    els.onlineTbody.innerHTML = players.map(function (p) {
      var pos = (isNum(p.x) && isNum(p.z)) ? String(p.x) + ', ' + String(p.z) : '—';
      var row = '<tr>' +
        '<td>' + accountLinkHtml(p.account) + '</td>' +
        '<td>' + (p.character ? accountLinkHtml(p.account, p.character) : '<span class="text-muted">' + escapeHtml(t('No character')) + '</span>') + '</td>' +
        '<td>' + (p.scene_name ? escapeHtml(p.scene_name) : '—') + '</td>' +
        '<td>' + escapeHtml(pos) + '</td>';
      if (showIps) row += '<td>' + (p.remote ? escapeHtml(p.remote) : '—') + '</td>';
      return row + '</tr>';
    }).join('');
  }

  function loadAccounts() {
    var params = new URLSearchParams();
    if (state.searchQuery) params.set('q', state.searchQuery);
    if (state.statusFilter) params.set('status', state.statusFilter);
    if (state.sortBy) params.set('sort', state.sortBy);
    params.set('page', String(state.accountsPage));

    var request = apiFetch('/api/admin/accounts?' + params.toString());
    trackBusy(els.accountsTbody, request);
    request
      .then(function (data) {
        var pages = data.pages || 1;
        // The current page can disappear (e.g. after deleting its last account): jump to the last one.
        if (state.accountsPage > pages) {
          state.accountsPage = pages;
          loadAccounts();
          return;
        }
        state.accounts = data.accounts || [];
        state.bansSupported = data.bans_supported !== false;
        state.accountsPages = pages;
        state.accountsTotal = data.total || 0;
        renderAccountsTable();
        renderAccountsPager();
      })
      .catch(function (err) {
        var message = t('Error loading accounts: {message}', { message: err.message });
        if (els.accountsTbody) els.accountsTbody.innerHTML = errorRowHtml(6, message, 'accounts');
        showToast(message, 'error');
      });
  }

  function resetAccountsPage() {
    state.accountsPage = 1;
  }

  function goToAccountsPage(page) {
    if (page < 1 || page > state.accountsPages || page === state.accountsPage) return;
    state.accountsPage = page;
    loadAccounts();
  }

  function renderAccountsPager() {
    if (!els.accountsPager) return;
    els.accountsPager.hidden = state.accountsTotal === 0;
    if (els.pagerInfo) {
      els.pagerInfo.textContent = t('Page {page} of {pages} ({total} accounts)', {
        page: state.accountsPage,
        pages: state.accountsPages,
        total: formatNumber(state.accountsTotal)
      });
    }
    if (els.pagerPrev) els.pagerPrev.disabled = state.accountsPage <= 1;
    if (els.pagerNext) els.pagerNext.disabled = state.accountsPage >= state.accountsPages;
  }

  function renderAccountsTable() {
    if (!els.accountsTbody) return;
    var list = state.accounts;

    if (!list.length) {
      els.accountsTbody.innerHTML = emptyRow(6, t('No accounts found matching the search criteria.'));
      return;
    }

    var html = '';
    list.forEach(function (acc) {
      var badgeHtml = '';
      if (acc.is_admin) {
        badgeHtml = '<span class="badge badge-admin">★ GM Admin</span>';
      } else if (acc.is_banned) {
        var banTitle = acc.banned_until ? acc.ban_reason + ' · ' + t('Suspended until {until}', { until: acc.banned_until }) : acc.ban_reason;
        badgeHtml = '<span class="badge badge-banned" title="' + escapeHtml(banTitle) + '">' + escapeHtml(t('✕ Banned')) + '</span>';
      } else {
        badgeHtml = '<span class="badge badge-active">' + escapeHtml(t('✓ Active')) + '</span>';
      }

      var charsHtml = '';
      if (acc.characters && acc.characters.length > 0) {
        charsHtml = '<div class="char-chips-container">';
        acc.characters.forEach(function (c) {
          charsHtml += '<span class="char-chip">' +
            '<strong>' + accountLinkHtml(acc.name, c.name) + '</strong> ' +
            '<span class="char-class">' + escapeHtml(c.career_name) + '</span> ' +
            '<span class="char-lv">Lv.' + c.level + '/' + c.job_level + '</span>' +
            '</span>';
        });
        charsHtml += '</div>';
      } else {
        charsHtml = '<span class="cell-none">' + escapeHtml(t('No characters')) + '</span>';
      }

      // data-label feeds the stacked card layout of narrow screens; the aria-labels name each button after its account.
      html += '<tr data-account="' + escapeHtml(acc.name) + '">' +
        '<td data-label="' + escapeHtml(t('Account')) + '"><strong class="account-name">' + accountLinkHtml(acc.name) + '</strong></td>' +
        '<td data-label="' + escapeHtml(t('Status')) + '">' + badgeHtml + '</td>' +
        '<td data-label="' + escapeHtml(t('Associated Characters')) + '">' + charsHtml + '</td>' +
        '<td class="cell-meta" data-label="' + escapeHtml(t('Registration Date')) + '">' + formatDate(acc.created_utc) + '</td>' +
        '<td class="cell-meta" data-label="' + escapeHtml(t('Last Login')) + '">' + formatDate(acc.last_login) + '</td>' +
        '<td data-label="' + escapeHtml(t('Actions')) + '">' +
          '<div class="row-actions">' +
            '<button class="btn btn-secondary btn-sm btn-view-detail" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Manage account, characters and security')) + '" aria-label="' + escapeHtml(actionLabel(t('Manage'), acc.name)) + '">' + escapeHtml(t('Manage')) + '</button>' +
            '<button class="btn btn-secondary btn-sm btn-change-pw" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Change password')) + '" aria-label="' + escapeHtml(actionLabel(t('Pass'), acc.name)) + '">' + escapeHtml(t('Pass')) + '</button>' +
            (acc.is_admin ? '' : (acc.is_banned ?
              '<button class="btn btn-secondary btn-sm btn-unban" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Remove suspension')) + '" aria-label="' + escapeHtml(actionLabel(t('Unban'), acc.name)) + '">' + escapeHtml(t('Unban')) + '</button>' :
              '<button class="btn btn-danger btn-sm btn-ban" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Suspend account')) + '" aria-label="' + escapeHtml(actionLabel(t('Ban'), acc.name)) + '">' + escapeHtml(t('Ban')) + '</button>'
            )) +
            (acc.is_admin ? '' : '<button class="btn btn-danger btn-sm btn-delete" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Delete account')) + '" aria-label="' + escapeHtml(actionLabel(t('Delete account'), acc.name)) + '">✕</button>') +
          '</div>' +
        '</td>' +
      '</tr>';
    });

    els.accountsTbody.innerHTML = html;
  }

  // --- Modals ---
  var modalReturnFocus = new WeakMap();
  // Open modals, the last one is on top: it owns the keyboard (Tab stays inside it, Escape closes it).
  var modalStack = [];
  var FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function modalFocusables(modalEl) {
    return Array.prototype.filter.call(modalEl.querySelectorAll(FOCUSABLE_SELECTOR), function (el) {
      return !el.hidden && el.getClientRects().length > 0;
    });
  }

  // While a modal is open the page behind it cannot be reached by Tab, click or screen reader.
  // Toasts stay live so a result is still announced.
  function setBackgroundInert(inert) {
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el.classList.contains('modal-backdrop') || el.id === 'toast-container' || el.tagName === 'SCRIPT') return;
      el.inert = inert;
    });
  }

  function openModal(modalEl) {
    if (!modalEl) return;
    modalReturnFocus.set(modalEl, document.activeElement);
    modalEl.hidden = false;
    if (modalStack.indexOf(modalEl) === -1) modalStack.push(modalEl);
    setBackgroundInert(true);
    // First field when there is one, otherwise the dialog itself so a screen reader starts at its title.
    var field = modalEl.querySelector('input:not([type="hidden"]), select, textarea');
    var target = field || modalEl.querySelector('.modal-dialog');
    if (target) target.focus();
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    if (modalEl === els.modalConfirm) settleConfirm(false);
    modalEl.hidden = true;
    var open = modalStack.indexOf(modalEl);
    if (open !== -1) modalStack.splice(open, 1);
    if (!modalStack.length) setBackgroundInert(false);
    // Hand focus back to the control that opened the modal (a hidden control ignores the call).
    var opener = modalReturnFocus.get(modalEl);
    modalReturnFocus.delete(modalEl);
    if (opener && opener.isConnected && typeof opener.focus === 'function') opener.focus();
  }

  function handleModalKeydown(e) {
    var top = modalStack[modalStack.length - 1];
    if (!top || top.hidden) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal(modalStack[modalStack.length - 1]);
      return;
    }
    if (e.key !== 'Tab') return;
    var focusables = modalFocusables(top);
    var target = focusTrapTarget(focusables, document.activeElement, e.shiftKey);
    if (target) {
      e.preventDefault();
      target.focus();
    } else if (!focusables.length) {
      e.preventDefault();
      var dialog = top.querySelector('.modal-dialog');
      if (dialog) dialog.focus();
    }
  }

  // --- Account management screen (route #/accounts/<name>[/<tab>]) ---
  var ACCOUNT_TABS = ['characters', 'vault', 'security'];

  function parseAccountRoute(hash) {
    var none = { name: null, tab: 'characters' };
    var match = /^#\/accounts\/([^/]+)(?:\/([^/]+))?\/?$/.exec(hash || '');
    if (!match) return none;
    var name;
    try {
      name = decodeURIComponent(match[1]);
    } catch (e) {
      return none;
    }
    return { name: name, tab: ACCOUNT_TABS.indexOf(match[2]) === -1 ? 'characters' : match[2] };
  }

  function accountRouteHash(name, tab) {
    return '#/accounts/' + encodeURIComponent(name) + (tab && tab !== 'characters' ? '/' + tab : '');
  }

  function isAccountScreenOpen() {
    return state.accountScreen.open;
  }

  function navigateToAccount(name) {
    var target = accountRouteHash(name);
    if (globalThis.location.hash === target) {
      handleRouteChange();
      return;
    }
    globalThis.location.hash = accountRouteHash(name);
  }

  function goToAccountList() {
    if (globalThis.location.hash === '#/accounts') {
      handleRouteChange();
      return;
    }
    globalThis.location.hash = '#/accounts';
  }

  function accountNotesDirty() {
    return state.accountScreen.open && els.accountNotes.value !== state.accountScreen.notesBaseline;
  }

  function confirmDiscardNotes() {
    if (!accountNotesDirty()) return true;
    return confirm(t('You have unsaved notes. Leave without saving?'));
  }

  // Put the URL back when the admin keeps the account after a leave-without-saving warning.
  function restoreAccountHash() {
    var screen = state.accountScreen;
    globalThis.history.replaceState(null, '', accountRouteHash(screen.name, screen.tab));
  }

  function handleRouteChange() {
    if (!state.authenticated) return;
    var screen = state.accountScreen;
    var route = parseAccountRoute(globalThis.location.hash);
    if (route.name === null) {
      if (!screen.open) return;
      if (!confirmDiscardNotes()) {
        restoreAccountHash();
        return;
      }
      closeAccountScreen();
      return;
    }
    if (screen.open && screen.name === route.name) {
      if (route.tab !== screen.tab) setAccountTab(route.tab, { updateUrl: false });
      return;
    }
    if (screen.open && !confirmDiscardNotes()) {
      restoreAccountHash();
      return;
    }
    openAccountScreen(route.name, route.tab);
  }

  // The list and the screen share the Accounts tab: only one of them is visible at a time.
  function renderAccountsViews() {
    var onAccounts = state.activeTab === 'accounts';
    var open = onAccounts && state.accountScreen.open;
    if (els.tabViewAccounts) els.tabViewAccounts.hidden = !onAccounts || open;
    if (els.accountScreen) els.accountScreen.hidden = !open;
  }

  function openAccountScreen(name, tab) {
    var screen = state.accountScreen;
    if (!screen.open) screen.listScroll = globalThis.scrollY || 0;
    screen.open = true;
    screen.name = name;
    screen.data = null;
    screen.status = 'loading';
    screen.notesBaseline = '';
    els.accountNotes.value = '';
    setNotesStatus('', '');
    resetAccountVault(name);
    resetGmPanel();
    renderAccountHeader(null, name);
    if (state.activeTab === 'accounts') {
      renderAccountsViews();
    } else {
      switchTab('accounts');
    }
    setAccountTab(tab, { updateUrl: false });
    globalThis.scrollTo(0, 0);
    els.accountTitle.focus({ preventScroll: true });
    loadAccountScreen(name, false);
  }

  // Back to the list: nothing is refetched, so the filters, page and scroll position of the list survive.
  function closeAccountScreen() {
    var screen = state.accountScreen;
    var name = screen.name;
    screen.open = false;
    screen.request += 1;
    screen.status = 'idle';
    screen.data = null;
    resetAccountVault('');
    renderAccountsViews();
    globalThis.scrollTo(0, screen.listScroll);
    focusAccountOpener(name);
  }

  // Leaving through another top tab or a logout: drop the screen state (and, when asked, the account URL).
  function resetAccountScreen(keepUrl) {
    var screen = state.accountScreen;
    screen.open = false;
    screen.request += 1;
    screen.status = 'idle';
    screen.data = null;
    resetAccountVault('');
    if (!keepUrl && parseAccountRoute(globalThis.location.hash).name !== null) {
      globalThis.history.replaceState(null, '', globalThis.location.pathname + globalThis.location.search);
    }
  }

  function focusAccountOpener(name) {
    var target = null;
    if (els.accountsTbody) {
      els.accountsTbody.querySelectorAll('.btn-view-detail').forEach(function (btn) {
        if (btn.getAttribute('data-account') === name) target = btn;
      });
    }
    if (!target) target = els.searchInput;
    if (target && typeof target.focus === 'function') target.focus({ preventScroll: true });
  }

  function handleAccountEscape(e) {
    if (e.key !== 'Escape' || e.defaultPrevented || !state.accountScreen.open) return;
    var active = document.activeElement;
    var tag = active && active.tagName ? active.tagName.toUpperCase() : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (active && active.isContentEditable)) return;
    if (document.querySelector('.modal-backdrop:not([hidden])')) return;
    goToAccountList();
  }

  function setAccountTab(tab, opts) {
    opts = opts || {};
    var screen = state.accountScreen;
    if (ACCOUNT_TABS.indexOf(tab) === -1) tab = 'characters';
    screen.tab = tab;
    els.accountTabButtons.forEach(function (button) {
      var active = button.getAttribute('data-account-tab') === tab;
      button.setAttribute('aria-selected', active ? 'true' : 'false');
      button.setAttribute('tabindex', active ? '0' : '-1');
      var panel = document.getElementById(button.getAttribute('aria-controls'));
      if (panel) panel.hidden = !active;
      if (active && opts.focus) button.focus();
    });
    if (screen.open && opts.updateUrl !== false) {
      globalThis.history.replaceState(null, '', accountRouteHash(screen.name, tab));
    }
    // The vault starts loading once its account is known; opening the tab only has to render or retry it.
    if (tab === 'vault' && screen.data && state.vault.status === 'idle') loadAccountVault(1);
  }

  function handleAccountTabKeydown(e) {
    var tabs = Array.prototype.slice.call(els.accountTabButtons);
    var index = tabs.indexOf(e.target.closest('[role="tab"]'));
    if (index === -1) return;
    var next;
    if (e.key === 'ArrowRight') {
      next = (index + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      next = (index - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      next = 0;
    } else if (e.key === 'End') {
      next = tabs.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    setAccountTab(tabs[next].getAttribute('data-account-tab'), { focus: true });
  }

  function skeletonHtml(lines) {
    var html = '<div class="skeleton-group" aria-busy="true"><span class="sr-only" role="status">' + escapeHtml(t('Loading...')) + '</span>';
    for (var i = 0; i < lines; i++) html += '<div class="skeleton skeleton-line" aria-hidden="true"></div>';
    return html + '</div>';
  }

  function retryStateHtml(message, kind) {
    return '<div class="account-inline-error" role="alert"><p>' + escapeHtml(message) + '</p>' +
      '<button type="button" class="btn btn-secondary" data-retry="' + escapeHtml(kind) + '">' + escapeHtml(t('Retry')) + '</button></div>';
  }

  function loadAccountScreen(name, preserveNotes) {
    var screen = state.accountScreen;
    var requestId = screen.request + 1;
    screen.request = requestId;
    screen.status = 'loading';
    renderAccountLoading();
    return apiFetch('/api/admin/accounts/' + encodeURIComponent(name))
      .then(function (acc) {
        if (requestId !== screen.request) return;
        screen.status = 'ready';
        screen.data = acc;
        state.selectedAccount = acc;
        state.bansSupported = acc.bans_supported !== false;
        renderAccountScreen(acc, preserveNotes);
        loadAccountVault(state.vault.loaded ? state.vault.page : 1);
      })
      .catch(function (err) {
        if (requestId !== screen.request) return;
        screen.status = 'error';
        if (err.status === 404) {
          renderAccountNotFound(name);
        } else {
          renderAccountError(t('Error loading account: {message}', { message: err.message }));
        }
      });
  }

  function renderAccountLoading() {
    els.accountState.hidden = true;
    els.accountBody.hidden = false;
    els.accountBadges.innerHTML = '<span class="skeleton skeleton-badge" aria-hidden="true"></span>';
    els.accountRegistered.textContent = '—';
    els.accountSessions.textContent = '—';
    els.accountStatusText.textContent = '—';
    els.accountSummary.innerHTML = skeletonHtml(3);
    els.accountCharacters.innerHTML = skeletonHtml(5);
    els.accountNotes.disabled = true;
    els.accountSaveNotes.disabled = true;
  }

  function renderAccountNotFound(name) {
    els.accountBody.hidden = true;
    els.accountBadges.innerHTML = '';
    els.accountState.innerHTML = '<p>' + escapeHtml(t('Account "{name}" was not found.', { name: name })) + '</p>' +
      '<a class="btn btn-secondary" href="#/accounts">' + escapeHtml(t('Back to accounts')) + '</a>';
    els.accountState.hidden = false;
  }

  function renderAccountError(message) {
    els.accountBody.hidden = true;
    els.accountBadges.innerHTML = '';
    els.accountState.innerHTML = retryStateHtml(message, 'account');
    els.accountState.hidden = false;
  }

  function accountStatusLabel(acc) {
    if (!acc.is_banned) return t('Active');
    var info = { reason: acc.ban_reason || '—', until: formatDate(acc.banned_until) };
    return acc.banned_until ? t('Banned until {until} ({reason})', info) : t('Banned ({reason})', info);
  }

  function renderAccountHeader(acc, routeName) {
    var name = acc ? acc.name : routeName;
    els.accountTitle.textContent = name;
    els.accountBreadcrumbCurrent.textContent = name;
    els.accountRegistered.textContent = acc ? formatDate(acc.created_utc) : '—';
    els.accountSessions.textContent = acc ? t('{count} sessions', { count: acc.tokens_count }) : '—';
    els.accountStatusText.textContent = acc ? accountStatusLabel(acc) : '—';
    renderAccountBadges();
  }

  // Every badge carries text, so state never depends on colour alone.
  function renderAccountBadges() {
    var acc = state.accountScreen.data;
    if (!acc) return;
    var html = '<span class="badge ' + (acc.is_banned ? 'badge-banned' : 'badge-active') + '">' + escapeHtml(accountStatusLabel(acc)) + '</span>';
    if (acc.is_admin) html += ' <span class="badge badge-admin">' + escapeHtml(t('Administrator')) + '</span>';
    var vip = state.vault.vip;
    if (vip && (vip.source === 'gm' || vip.source === 'vip' || vip.source === 'note')) html += ' ' + vaultVipBadge(vip);
    els.accountBadges.innerHTML = html;
  }

  function renderAccountSummary(acc) {
    var chars = acc.characters || [];
    var highest = 0;
    var zeny = 0;
    chars.forEach(function (c) {
      highest = Math.max(highest, Number(c.level) || 0);
      zeny += Number(c.currency && c.currency.zeny) || 0;
    });
    var rows = [
      [t('Characters'), formatNumber(chars.length)],
      [t('Highest level'), chars.length ? formatNumber(highest) : '—'],
      [t('Total Zeny'), formatNumber(zeny)]
    ];
    els.accountSummary.innerHTML = rows.map(function (row) {
      return '<div class="account-summary-row"><dt>' + escapeHtml(row[0]) + '</dt><dd>' + row[1] + '</dd></div>';
    }).join('');
  }

  function renderCharacterCard(c, acc) {
    var roleId = escapeHtml(String(c.id));
    return '<article class="char-card-detail">' +
      '<div class="char-card-header">' +
        '<div class="char-card-name">' +
          '<h3 class="char-title">' + escapeHtml(c.name) + '</h3> ' +
          '<span class="badge badge-admin">' + escapeHtml(c.career_name) + '</span>' +
        '</div>' +
        '<div class="char-card-level">' + escapeHtml(t('Level {level} / Job {job}', { level: c.level, job: c.job_level })) + '</div>' +
      '</div>' +
      '<div class="char-card-body">' +
        '<div class="char-card-main">' +
          '<dl class="char-facts">' +
            '<div><dt>' + escapeHtml(t('Location:')) + '</dt><dd>' + escapeHtml(c.scene_name) + ' (' + cellValue(c.pos.x) + ', ' + cellValue(c.pos.z) + ')</dd></div>' +
            '<div><dt>' + escapeHtml(t('Last login:')) + '</dt><dd>' + formatDate(c.last_login) + '</dd></div>' +
          '</dl>' +
          renderCharacterCurrencies(c) +
        '</div>' +
        renderCharacterStats(c.stats || {}) +
      '</div>' +
      '<div class="char-card-actions">' +
        '<button type="button" class="btn btn-secondary btn-sm btn-view-inventory" data-role-id="' + roleId + '" aria-expanded="false" aria-controls="char-inventory-' + roleId + '" title="' + escapeHtml(t('View character items')) + '">' + escapeHtml(t('View inventory')) + '</button>' +
        '<button type="button" class="btn btn-secondary btn-sm btn-view-mail" data-role-id="' + roleId + '" aria-expanded="false" aria-controls="char-mail-' + roleId + '" title="' + escapeHtml(t('View character mail (read-only)')) + '">' + escapeHtml(t('View mail')) + '</button>' +
        // The server refuses characters of administrator accounts, so the button is not offered for them.
        (acc && acc.is_admin ? '' : '<button type="button" class="btn btn-danger btn-sm btn-delete-character" data-role-id="' + roleId + '" data-role-name="' + escapeHtml(c.name) + '" data-account="' + escapeHtml(acc ? acc.name : '') + '">' + escapeHtml(t('Delete character')) + '</button>') +
      '</div>' +
      '<div class="char-inventory" id="char-inventory-' + roleId + '" hidden></div>' +
      '<div class="char-mail-panel" id="char-mail-' + roleId + '" hidden></div>' +
    '</article>';
  }

  function renderAccountCharacters(acc) {
    var chars = acc.characters || [];
    if (!chars.length) {
      els.accountCharacters.innerHTML = '<p class="account-empty">' + escapeHtml(t('This account has no characters yet.')) + '</p>';
      return;
    }
    els.accountCharacters.innerHTML = chars.map(function (c) { return renderCharacterCard(c, acc); }).join('');
  }

  // Ban, unban and delete are hidden for administrator accounts, exactly as in the list.
  function renderAccountSecurity(acc) {
    var admin = !!acc.is_admin;
    var banned = !!acc.is_banned;
    var text;
    if (admin) {
      text = t('Suspend and delete actions are not available for administrator accounts.');
    } else if (banned) {
      text = accountStatusLabel(acc);
      if (acc.banned_at) text += ' · ' + t('Suspended on {date}', { date: formatDate(acc.banned_at) });
    } else if (acc.bans_supported === false) {
      text = t('Update RO3Emu: this server does not support account bans');
    } else {
      text = t('This account can sign in.');
    }
    els.accountAccessText.textContent = text;
    els.accountSessionsText.textContent = t('{count} sessions', { count: acc.tokens_count });
    els.accountBtnBan.hidden = admin || banned;
    els.accountBtnUnban.hidden = admin || !banned;
    els.accountDangerZone.hidden = admin;
  }

  function renderAccountScreen(acc, preserveNotes) {
    els.accountState.hidden = true;
    els.accountBody.hidden = false;
    renderAccountHeader(acc, acc.name);
    renderAccountSummary(acc);
    renderAccountCharacters(acc);
    renderAccountSecurity(acc);
    if (!preserveNotes) els.accountNotes.value = acc.notes || '';
    state.accountScreen.notesBaseline = String(acc.notes || '').replace(/\r\n?/g, '\n');
    els.accountNotes.disabled = false;
    els.accountSaveNotes.disabled = state.accountScreen.saving;
    handleNotesInput();
  }

  // After a change made through a modal: reload the open account so every panel shows the new state.
  function refreshOpenAccount(name) {
    var screen = state.accountScreen;
    var open = screen.open && (screen.name === name || (screen.data && screen.data.name === name));
    if (open) loadAccountScreen(screen.name, true);
  }

  function setNotesStatus(message, kind) {
    els.accountNotesStatus.textContent = message;
    els.accountNotesStatus.className = 'account-status-text' + (kind ? ' ' + kind : '');
  }

  function handleNotesInput() {
    var dirty = accountNotesDirty();
    setNotesStatus(dirty ? t('You have unsaved changes') : '', dirty ? 'warning' : '');
  }

  function handleSaveNotes() {
    var screen = state.accountScreen;
    if (!screen.data || screen.saving) return;
    var accountName = screen.data.name;
    var notes = (els.accountNotes.value || '').trim();
    var btn = els.accountSaveNotes;
    screen.saving = true;
    btn.disabled = true;
    btn.classList.add('is-loading');
    btn.textContent = t('Saving…');
    setNotesStatus(t('Saving…'), '');
    apiFetch('/api/admin/accounts/save-notes', {
      method: 'POST',
      body: { username: accountName, notes: notes }
    })
      .then(function () {
        showToast(t('Notes updated successfully'), 'success');
        if (!screen.data || screen.data.name !== accountName) return;
        screen.data.notes = notes;
        screen.notesBaseline = notes;
        if ((els.accountNotes.value || '').trim() === notes) els.accountNotes.value = notes;
        setNotesStatus(t('Notes updated successfully'), 'success');
      })
      .catch(function (err) {
        var message = t('Error saving notes: {message}', { message: err.message });
        showToast(message, 'error');
        setNotesStatus(message, 'error');
      })
      .finally(function () {
        screen.saving = false;
        btn.disabled = !screen.data;
        btn.classList.remove('is-loading');
        btn.textContent = t('Save Notes');
      });
  }

  // --- Character Mail (read-only) ---
  var MAIL_PAGE_SIZE = 10;

  function renderMailAttachments(m) {
    var parts = [];
    (m.attachments || []).forEach(function (a) {
      parts.push(itemChipHtml(a, ' <span class="item-qty">x' + escapeHtml(String(a.count)) + '</span>'));
    });
    (m.items || []).forEach(function (it) {
      parts.push(itemChipHtml(it, ' <span class="item-qty">x' + escapeHtml(String(it.stack)) + '</span>'));
    });
    (m.currency || []).forEach(function (cur) {
      parts.push('<ul class="char-currencies char-currencies--inline">' + currencyRowHtml(cur.entry, cur, cur.amount) + '</ul>');
    });
    return parts.length ? '<span class="item-chip-list item-chip-list--inline">' + parts.join('') + '</span>' : escapeHtml(t('No attachments'));
  }

  function renderCharacterMail(panel, roleId, data) {
    if (!data.decodable) {
      panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(data.message || t('The mailbox could not be decoded.')) + '</p>';
      return;
    }
    if (!data.mails.length) {
      panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(data.total ? t('There are no mails on this page.') : t('The mailbox is empty.')) + '</p>';
      return;
    }
    var html = '<ul class="char-mail-list">';
    data.mails.forEach(function (m) {
      var subject = m.title || m.abstract || t('Template {id}', { id: m.template_id });
      html += '<li class="char-mail-item">' +
        '<div class="char-mail-head">' +
          '<strong>' + escapeHtml(subject) + '</strong>' +
          '<span class="badge ' + (m.read ? 'badge-active' : 'badge-admin') + '">' + escapeHtml(m.read ? t('Read') : t('Unread')) + '</span>' +
          (m.claimed ? ' <span class="badge badge-active">' + escapeHtml(t('Claimed')) + '</span>' : '') +
        '</div>' +
        '<div class="char-mail-meta">' + escapeHtml(t('From: {sender} · {date}', { sender: m.sender || '—', date: formatDate(m.created_at) })) +
          (m.remove_at ? ' · ' + escapeHtml(t('Expires: {date}', { date: formatDate(m.remove_at) })) : '') + '</div>' +
        (m.content ? '<div class="char-mail-body">' + escapeHtml(m.content) + '</div>' : '') +
        '<div class="char-mail-meta">' + escapeHtml(t('Attachments ({count}):', { count: m.attachment_count })) + ' ' + renderMailAttachments(m) + '</div>' +
      '</li>';
    });
    html += '</ul>';
    html += '<div class="pager">' +
      '<button type="button" class="btn btn-secondary btn-sm btn-mail-page" data-role-id="' + escapeHtml(String(roleId)) + '" data-page="' + escapeHtml(String(data.page - 1)) + '"' + (data.page <= 1 ? ' disabled' : '') + '>' + escapeHtml(t('Previous')) + '</button>' +
      '<span class="pager-info">' + escapeHtml(t('Page {page} of {pages} · {total} mails', { page: data.page, pages: data.pages, total: data.total })) + '</span>' +
      '<button type="button" class="btn btn-secondary btn-sm btn-mail-page" data-role-id="' + escapeHtml(String(roleId)) + '" data-page="' + escapeHtml(String(data.page + 1)) + '"' + (data.page >= data.pages ? ' disabled' : '') + '>' + escapeHtml(t('Next')) + '</button>' +
    '</div>';
    panel.innerHTML = html;
  }

  function loadCharacterMail(roleId, page) {
    var panel = document.getElementById('char-mail-' + roleId);
    if (!panel) return;
    panel.hidden = false;
    panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(t('Loading mail...')) + '</p>';
    apiFetch('/api/admin/characters/' + encodeURIComponent(roleId) + '/mail?page=' + encodeURIComponent(page) + '&page_size=' + MAIL_PAGE_SIZE)
      .then(function (data) {
        renderCharacterMail(panel, roleId, data);
      })
      .catch(function (err) {
        panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(t('Error loading mail: {message}', { message: err.message })) + '</p>' +
          '<button type="button" class="btn btn-secondary btn-sm btn-mail-page" data-role-id="' + escapeHtml(String(roleId)) + '" data-page="' + escapeHtml(String(page)) + '">' + escapeHtml(t('Retry')) + '</button>';
      });
  }

  // --- Player links, currencies and stats ---
  // Every player name that has an account behind it links to that account's screen. The hashchange handler does the
  // navigation, so the link also works from another tab, in a new tab and with the keyboard.
  var AUDIT_ACCOUNT_ACTIONS = ['create_account', 'update_password', 'ban_account', 'unban_account', 'gm_command'];

  function accountLinkHtml(account, label) {
    var text = label === undefined || label === null ? account : label;
    if (!account) return escapeHtml(text);
    return '<a class="player-link" href="' + escapeHtml(accountRouteHash(account)) + '">' + escapeHtml(text) + '</a>';
  }

  // The audit target is an account only for the actions on accounts that still exist (a deleted account, a gift
  // code or a feature switch are plain text). Long targets are cut for display; the link and the title keep the full name.
  function auditTargetHtml(l) {
    var targetRaw = l.target || '';
    if (!targetRaw) return '\u2014';
    var MAX_TARGET_CHARS = 20;
    var shown = targetRaw.length > MAX_TARGET_CHARS ? targetRaw.substring(0, MAX_TARGET_CHARS) + '\u2026' : targetRaw;
    var inner = AUDIT_ACCOUNT_ACTIONS.indexOf(l.action) !== -1 ? accountLinkHtml(targetRaw, shown) : escapeHtml(shown);
    return '<strong class="audit-target text-strong" title="' + escapeHtml(targetRaw) + '">' + inner + '</strong>';
  }

  // One currency: image, name and amount. Currency ids are item ids, so the item catalog names them.
  function currencyRowHtml(entry, info, amount) {
    var name = info && info.name ? info.name : (entry === 1 ? t('Zeny') : t('Currency {id}', { id: entry }));
    return '<li class="char-currency">' +
      itemIconHtml({ entry: entry, name: name, icon: info && info.icon, quality: info && info.quality }) +
      '<span class="char-currency__name">' + escapeHtml(name) + '</span>' +
      '<span class="char-currency__amount">' + escapeHtml(formatNumber(amount)) + '</span>' +
    '</li>';
  }

  function renderCharacterCurrencies(c) {
    var rows = [currencyRowHtml(1, c.currency.zeny_item, c.currency.zeny)];
    (c.currency.others || []).forEach(function (other) {
      rows.push(currencyRowHtml(other.id, other, other.amount));
    });
    return '<section class="char-currencies-block">' +
      '<h4 class="char-subtitle">' + escapeHtml(t('Currencies')) + '</h4>' +
      '<ul class="char-currencies" tabindex="0" aria-label="' + escapeHtml(t('Currencies')) + '">' + rows.join('') + '</ul>' +
    '</section>';
  }

  function renderCharacterStats(stats) {
    return '<dl class="char-stats">' + ['str', 'agi', 'vit', 'int', 'dex', 'luk'].map(function (key) {
      return '<div class="char-stat"><dt>' + key.toUpperCase() + '</dt><dd>' + cellValue(stats[key]) + '</dd></div>';
    }).join('') + '</dl>';
  }

  // --- Item name + image ---
  // The server sends name, icon (a file name) and quality (one of five words) per item. The icon URL is built
  // here from the same-site base in the branding config; anything that does not look like a plain file name
  // or a plain same-site folder gets the placeholder instead of an <img>.
  var ITEM_QUALITIES = ['common', 'fine', 'rare', 'legendary', 'mythic'];
  var ITEM_ICON_FILE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,100}\.(?:png|webp|jpg)$/;
  var ITEM_ICON_BASE = /^\/?(?:[A-Za-z0-9._~-]+\/)+$/;
  var ITEM_ICON_PLACEHOLDER = '<svg class="item-icon__placeholder" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M21 8l-9-5-9 5v8l9 5 9-5V8z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></svg>';

  function itemIconSrc(icon) {
    var base = state.branding && state.branding.item_icons_url;
    if (typeof base !== 'string' || !ITEM_ICON_BASE.test(base) || base.indexOf('//') !== -1 || base.indexOf('..') !== -1) return '';
    if (typeof icon !== 'string' || !ITEM_ICON_FILE.test(icon)) return '';
    return base + encodeURIComponent(icon);
  }

  function itemIconHtml(item) {
    var quality = ITEM_QUALITIES.indexOf(item.quality) !== -1 ? ' quality--' + item.quality : '';
    var src = itemIconSrc(item.icon);
    var label = item.name || '#' + item.entry;
    // Decorative next to the visible name, so screen readers skip it; the alt stays descriptive for when it is not.
    return '<span class="item-icon' + quality + (src ? '' : ' is-missing') + '" aria-hidden="true">' +
      (src
        ? '<img class="item-icon__img" src="' + escapeHtml(src) + '" alt="' + escapeHtml(label) + '" width="32" height="32" loading="lazy" decoding="async">'
        : ITEM_ICON_PLACEHOLDER) +
      '</span>';
  }

  // Image + name (+ id when the name is known), for tables and lists. `extra` is trusted HTML after the name.
  function itemChipHtml(item, extra) {
    var named = !!item.name;
    return '<span class="item-chip">' + itemIconHtml(item) +
      '<span class="item-chip__text"><strong class="item-chip__name text-strong">' +
        escapeHtml(named ? item.name : '#' + item.entry) + '</strong>' +
        (named ? ' <span class="text-dim">#' + escapeHtml(String(item.entry)) + '</span>' : '') +
        (extra || '') +
      '</span></span>';
  }

  // A file that does not load (missing on the server, blocked) becomes the placeholder.
  function handleItemIconError(e) {
    var img = e.target;
    if (!img || img.tagName !== 'IMG' || !img.classList.contains('item-icon__img')) return;
    var holder = img.parentNode;
    if (!holder) return;
    holder.classList.add('is-missing');
    holder.innerHTML = ITEM_ICON_PLACEHOLDER;
  }

  // --- Character Inventory (read-only) ---
  // A character card shows its inventory or its mail, never both: opening one closes the other. `which` is
  // 'inventory', 'mail' or null (both closed); the card remembers it in data-panel, so a slow load can tell
  // whether the admin has already moved on.
  function setCharacterPanel(card, which) {
    card.setAttribute('data-panel', which || '');
    var inventoryBox = card.querySelector('.char-inventory');
    var mailBox = card.querySelector('.char-mail-panel');
    if (inventoryBox && which !== 'inventory') inventoryBox.hidden = true;
    if (mailBox && which !== 'mail') mailBox.hidden = true;
    var inventoryBtn = card.querySelector('.btn-view-inventory');
    var mailBtn = card.querySelector('.btn-view-mail');
    if (inventoryBtn) {
      inventoryBtn.setAttribute('aria-expanded', which === 'inventory' ? 'true' : 'false');
      inventoryBtn.textContent = which === 'inventory' ? t('Hide inventory') : t('View inventory');
    }
    if (mailBtn) {
      mailBtn.setAttribute('aria-expanded', which === 'mail' ? 'true' : 'false');
      mailBtn.textContent = which === 'mail' ? t('Hide mail') : t('View mail');
    }
  }

  function toggleCharacterInventory(btn) {
    var card = btn.closest('.char-card-detail');
    var container = card ? card.querySelector('.char-inventory') : null;
    var roleId = btn.getAttribute('data-role-id');
    if (!container || !roleId) return;

    if (card.getAttribute('data-panel') === 'inventory') {
      setCharacterPanel(card, null);
      return;
    }

    setCharacterPanel(card, 'inventory');
    btn.disabled = true;
    btn.textContent = t('Loading...');
    apiFetch('/api/admin/characters/' + encodeURIComponent(roleId) + '/items')
      .then(function (data) {
        if (card.getAttribute('data-panel') !== 'inventory') return;
        container.innerHTML = renderInventory(data);
        container.hidden = false;
        setCharacterPanel(card, 'inventory');
      })
      .catch(function (err) {
        if (card.getAttribute('data-panel') === 'inventory') setCharacterPanel(card, null);
        showToast(t('Error loading inventory: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function renderInventory(data) {
    if (!data || data.available === false) {
      return '<div class="inventory-box is-empty">' + escapeHtml(t('The inventory is not available in this database.')) + '</div>';
    }
    var items = data.items || [];
    if (!items.length) {
      return '<div class="inventory-box is-empty">' + escapeHtml(t('This character has no items.')) + '</div>';
    }

    // Group by pack, keeping the server order (pack, sort, guid).
    var groups = [];
    var byPack = {};
    items.forEach(function (item) {
      var key = String(item.pack);
      if (!byPack[key]) {
        byPack[key] = { pack: item.pack, packName: item.pack_name, items: [] };
        groups.push(byPack[key]);
      }
      byPack[key].items.push(item);
    });

    var html = '<div class="inventory-box">' +
      '<div class="inventory-total">' + escapeHtml(t('Total items:')) + ' <strong class="text-strong">' + formatNumber(data.total) + '</strong></div>';
    groups.forEach(function (g) {
      var label = g.packName || t('Bag {pack}', { pack: g.pack });
      html += '<div class="inventory-group">' +
        '<span class="badge badge-admin">' + escapeHtml(label) + ' (' + g.items.length + ')</span>' +
        '<table class="data-table">' +
          '<thead><tr><th>' + escapeHtml(t('Inventory item')) + '</th><th>' + escapeHtml(t('Quantity')) + '</th><th>' + escapeHtml(t('Status')) + '</th></tr></thead><tbody>';
      g.items.forEach(function (item) {
        var flags = [];
        if (item.equipped) flags.push('<span class="badge badge-active">' + escapeHtml(t('Equipped')) + '</span>');
        if (item.locked) flags.push('<span class="badge badge-banned">' + escapeHtml(t('Locked')) + '</span>');
        if (item.bind_type) flags.push('<span class="badge badge-admin">' + escapeHtml(t('Bound')) + '</span>');
        html += '<tr>' +
          '<td>' + itemChipHtml(item) + '</td>' +
          '<td>' + formatNumber(item.stack) + '</td>' +
          '<td>' + (flags.length ? flags.join(' ') : '—') + '</td>' +
        '</tr>';
      });
      html += '</tbody></table></div>';
    });
    html += '</div>';
    return html;
  }

  // --- Account Vault (read-only) ---
  var VAULT_PAGE_SIZE = 20;

  function resetAccountVault(account) {
    var vault = state.vault;
    vault.account = account;
    vault.page = 1;
    vault.pages = 1;
    vault.loaded = false;
    vault.status = 'idle';
    vault.requestedPage = 1;
    vault.data = null;
    vault.vip = null;
    vault.message = '';
    // Invalidates any response still in flight for the previous account.
    vault.request += 1;
    if (els.accountVault) {
      els.accountVault.innerHTML = '';
      els.accountVault.removeAttribute('aria-busy');
      els.accountVault.classList.remove('is-busy');
    }
  }

  function goToVaultPage(page) {
    if (page < 1 || page > state.vault.pages || page === state.vault.page) return;
    loadAccountVault(page);
  }

  function loadAccountVault(page) {
    var account = state.vault.account;
    if (!account || !els.accountVault) return;
    var requestId = state.vault.request + 1;
    state.vault.request = requestId;
    state.vault.status = 'loading';
    state.vault.requestedPage = page;
    renderVaultPanel();
    apiFetch('/api/admin/accounts/' + encodeURIComponent(account) + '/vault?page=' + encodeURIComponent(String(page)) +
      '&page_size=' + VAULT_PAGE_SIZE)
      .then(function (data) {
        if (requestId !== state.vault.request) return;
        state.vault.page = data.page || 1;
        state.vault.pages = data.pages || 1;
        state.vault.loaded = true;
        state.vault.status = 'ready';
        state.vault.data = data;
        state.vault.vip = data.vip || null;
        renderVaultPanel();
        renderAccountBadges();
      })
      .catch(function (err) {
        if (requestId !== state.vault.request) return;
        state.vault.status = 'error';
        state.vault.message = t('Error loading vault: {message}', { message: err.message });
        renderVaultPanel();
        if (state.accountScreen.tab === 'vault') showToast(state.vault.message, 'error');
      });
  }

  // Skeleton while the first page loads, a retry state on failure, otherwise the table (dimmed while paging).
  function renderVaultPanel() {
    var vault = state.vault;
    var el = els.accountVault;
    if (!el) return;
    if (vault.status === 'error') {
      el.innerHTML = retryStateHtml(vault.message, 'vault');
      el.setAttribute('aria-busy', 'false');
      el.classList.remove('is-busy');
      return;
    }
    if (!vault.loaded) {
      el.innerHTML = skeletonHtml(5);
      el.setAttribute('aria-busy', 'true');
      return;
    }
    el.innerHTML = renderAccountVault(vault.data);
    el.setAttribute('aria-busy', vault.status === 'loading' ? 'true' : 'false');
    el.classList.toggle('is-busy', vault.status === 'loading');
  }

  function vaultVipBadge(vip) {
    var info = vip || {};
    var source = info.source;
    var label;
    var cls;
    if (source === 'gm') {
      label = t('GM');
      cls = 'badge-admin';
    } else if (source === 'vip') {
      label = t('VIP');
      cls = 'badge-active';
    } else if (source === 'note') {
      label = t('VIP (note)');
      cls = 'badge-active';
    } else {
      label = t('Not VIP');
      cls = 'badge-neutral';
    }
    var html = '<span class="badge ' + cls + '">' + escapeHtml(label) + '</span>';
    if (info.vip_until) {
      html += ' <span class="vault-meta">' + escapeHtml(t('Until {date}', { date: formatDate(info.vip_until) })) + '</span>';
    }
    return html;
  }

  function renderAccountVault(data) {
    var vipLine = '<div class="vault-vip"><span class="vault-meta">' + escapeHtml(t('VIP status:')) + '</span> ' +
      vaultVipBadge(data ? data.vip : null) + '</div>';
    if (!data || data.available === false) {
      var reason = data && data.reason ? data.reason : t('The vault is not available in this database.');
      return vipLine + '<div class="readonly-notice" role="status">' + escapeHtml(reason) + '</div>';
    }
    var items = data.items || [];
    if (!items.length) {
      return vipLine + '<p class="vault-empty">' + escapeHtml(t('The vault is empty.')) + '</p>';
    }

    var html = vipLine +
      '<div class="table-container"><table class="data-table"><thead><tr>' +
        '<th>' + escapeHtml(t('Item')) + '</th>' +
        '<th>' + escapeHtml(t('Quantity')) + '</th>' +
        '<th>' + escapeHtml(t('Bag')) + '</th>' +
        '<th>' + escapeHtml(t('Locked')) + '</th>' +
        '<th>' + escapeHtml(t('Deposited by')) + '</th>' +
        '<th>' + escapeHtml(t('Deposited')) + '</th>' +
      '</tr></thead><tbody>';
    items.forEach(function (item) {
      var depositor = item.deposited_by_name ? escapeHtml(item.deposited_by_name) :
        (item.deposited_by_role_id === null || item.deposited_by_role_id === undefined ? '—' : '#' + escapeHtml(String(item.deposited_by_role_id)));
      html += '<tr>' +
        '<td class="vault-item">' + itemChipHtml(item) + '</td>' +
        '<td>' + formatNumber(item.stack) + '</td>' +
        '<td>' + (item.pack_name ? escapeHtml(item.pack_name) : '—') + '</td>' +
        '<td>' + escapeHtml(item.locked ? t('Yes') : t('No')) + '</td>' +
        '<td>' + depositor + '</td>' +
        '<td class="vault-meta">' + formatDate(item.deposited_utc) + '</td>' +
      '</tr>';
    });
    html += '</tbody></table></div>';

    var page = data.page || 1;
    var pages = data.pages || 1;
    html += '<div class="pager" role="navigation" aria-label="' + escapeHtml(t('Vault pagination')) + '">' +
      '<button type="button" class="btn btn-secondary btn-sm btn-vault-page" data-page="' + escapeHtml(String(page - 1)) + '"' + (page <= 1 ? ' disabled' : '') + '>' + escapeHtml(t('Previous')) + '</button>' +
      '<span class="pager-info" aria-live="polite">' + escapeHtml(t('Page {page} of {pages} · {total} items', { page: page, pages: pages, total: formatNumber(data.total) })) + '</span>' +
      '<button type="button" class="btn btn-secondary btn-sm btn-vault-page" data-page="' + escapeHtml(String(page + 1)) + '"' + (page >= pages ? ' disabled' : '') + '>' + escapeHtml(t('Next')) + '</button>' +
    '</div>';
    return html;
  }

  // --- GM Tools (POST /api/admin/gm, relayed to RO3Emu's loopback GM endpoint) ---
  function buildGmPanel() {
    var body = els.accountGmSlot;
    if (!body || document.getElementById('gm-tools')) return;
    var panel = document.createElement('div');
    panel.id = 'gm-tools';
    panel.className = 'gm-tools';
    panel.innerHTML =
      '<h3 class="gm-tools-title" data-i18n="GM Tools">GM Tools</h3>' +
      '<p class="gm-tools-note" data-i18n="Only works if the panel runs on the same host as RO3Emu (local GM endpoint) and the account has a connected character. The result appears in the player game chat.">Only works if the panel runs on the same host as RO3Emu (local GM endpoint) and the account has a connected character. The result appears in the player game chat.</p>' +
      '<form id="gm-warp-form" class="gm-warp-form" novalidate>' +
        '<div><label class="form-label" for="gm-warp-scene" data-i18n="Scene">Scene</label>' +
          '<input type="number" id="gm-warp-scene" class="form-input" min="1" step="1" required placeholder="10111"></div>' +
        '<div><label class="form-label" for="gm-warp-x" data-i18n="X (optional)">X (optional)</label>' +
          '<input type="number" id="gm-warp-x" class="form-input" step="1" placeholder="150"></div>' +
        '<div><label class="form-label" for="gm-warp-z" data-i18n="Z (optional)">Z (optional)</label>' +
          '<input type="number" id="gm-warp-z" class="form-input" step="1" placeholder="190"></div>' +
        '<div class="gm-warp-actions">' +
          '<button type="submit" class="btn btn-secondary btn-sm" data-i18n="Teleport">Teleport</button>' +
          '<button type="button" id="gm-unstuck" class="btn btn-secondary btn-sm" data-i18n="Unstuck">Unstuck</button>' +
        '</div>' +
      '</form>' +
      '<form id="gm-fieldexp-form" class="gm-warp-form gm-tools-section" novalidate>' +
        '<h4 class="gm-tools-title" data-i18n="Field EXP rate">Field EXP rate</h4>' +
        '<p class="gm-tools-note" data-i18n="Changes the EXP of open-field kills for the whole server, by level range. It stays in memory until the server restarts. The command must be enabled in gm_allowed_commands.">Changes the EXP of open-field kills for the whole server, by level range. It stays in memory until the server restarts. The command must be enabled in gm_allowed_commands.</p>' +
        '<div><label class="form-label" for="gm-fx-min" data-i18n="Level from">Level from</label>' +
          '<input type="number" id="gm-fx-min" class="form-input" min="1" step="1" required placeholder="20"></div>' +
        '<div><label class="form-label" for="gm-fx-max" data-i18n="Level to">Level to</label>' +
          '<input type="number" id="gm-fx-max" class="form-input" min="1" step="1" required placeholder="40"></div>' +
        '<div><label class="form-label" for="gm-fx-percent" data-i18n="Percent">Percent</label>' +
          '<input type="number" id="gm-fx-percent" class="form-input" min="1" max="10000" step="1" required placeholder="300"></div>' +
        '<div class="gm-warp-actions">' +
          '<button type="submit" class="btn btn-secondary btn-sm" data-i18n="Apply rate">Apply rate</button>' +
          '<button type="button" id="gm-fx-clear" class="btn btn-secondary btn-sm" data-i18n="Remove rate">Remove rate</button>' +
          '<button type="button" id="gm-fx-reset" class="btn btn-secondary btn-sm" data-i18n="Back to configuration">Back to configuration</button>' +
        '</div>' +
      '</form>' +
      questToolsMarkup() +
      '<p id="gm-tools-result" class="gm-tools-result" aria-live="polite"></p>';
    applyI18n(panel);
    body.appendChild(panel);

    document.getElementById('gm-warp-form').addEventListener('submit', handleGmWarp);
    document.getElementById('gm-unstuck').addEventListener('click', function () {
      sendGmCommand('unstuck', {});
    });
    document.getElementById('gm-fieldexp-form').addEventListener('submit', handleGmFieldExp);
    document.getElementById('gm-fx-clear').addEventListener('click', function () {
      sendGmCommand('fieldexp', { action: 'clear' });
    });
    document.getElementById('gm-fx-reset').addEventListener('click', function () {
      sendGmCommand('fieldexp', { action: 'reset' });
    });
    bindQuestTools();
  }

  function resetGmPanel() {
    ['gm-warp-scene', 'gm-warp-x', 'gm-warp-z', 'gm-fx-min', 'gm-fx-max', 'gm-fx-percent'].forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.value = '';
    });
    setGmResult('', '');
    resetQuestTools();
  }

  function setGmResult(message, type, resultId) {
    var result = document.getElementById(resultId || 'gm-tools-result');
    if (!result) return;
    result.textContent = message;
    result.className = 'gm-tools-result' + (type ? ' ' + type : '');
  }

  function parseGmInt(id) {
    var raw = (document.getElementById(id).value || '').trim();
    if (raw === '') return null;
    if (!/^-?\d+$/.test(raw)) return NaN;
    return parseInt(raw, 10);
  }

  function handleGmWarp(e) {
    e.preventDefault();
    var scene = parseGmInt('gm-warp-scene');
    var x = parseGmInt('gm-warp-x');
    var z = parseGmInt('gm-warp-z');
    if (scene === null || isNaN(scene) || scene < 1) {
      setGmResult(t('Enter a valid scene number.'), 'error');
      return;
    }
    if ((x === null) !== (z === null) || (x !== null && (isNaN(x) || isNaN(z)))) {
      setGmResult(t('Enter X and Z as whole numbers, or leave both empty.'), 'error');
      return;
    }
    var args = { scene: scene };
    if (x !== null) {
      args.x = x;
      args.z = z;
    }
    sendGmCommand('warp', args);
  }

  function handleGmFieldExp(e) {
    e.preventDefault();
    var min = parseGmInt('gm-fx-min');
    var max = parseGmInt('gm-fx-max');
    var percent = parseGmInt('gm-fx-percent');
    var numbers = [min, max, percent];
    if (numbers.some(function (n) { return n === null || isNaN(n); }) ||
        min < 1 || max < min || percent < 1 || percent > 10000) {
      setGmResult(t('Enter both levels and a percent from 1 to 10000, with the first level not above the second.'), 'error');
      return;
    }
    sendGmCommand('fieldexp', { action: 'set', rules: [{ min: min, max: max, percent: percent }] });
  }

  // The result line shows what was sent and RO3Emu's reply (older RO3Emu builds only answer the generic message).
  function sendGmCommand(command, args, resultId) {
    var account = state.accountScreen.data;
    if (!account) return Promise.resolve();
    setGmResult(t('Sending…'), '', resultId);
    var gmButtons = Array.prototype.slice.call(document.querySelectorAll('#gm-tools button'));
    gmButtons.forEach(function (button) { setSubmitting(button, true); });
    return apiFetch('/api/admin/gm', {
      method: 'POST',
      body: { account: account.name, command: command, args: args }
    })
      .then(function (data) {
        setGmResult(data.sent + ': ' + (data.reply || data.message), 'success', resultId);
        showToast(t('GM command sent'), 'success');
      })
      .catch(function (err) {
        setGmResult(err.message, 'error', resultId);
        showToast(t('GM error: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        gmButtons.forEach(function (button) { setSubmitting(button, false); });
      });
  }

  // --- Quest tools (GM "quest" command; hidden unless "quest" is in gm_allowed_commands) ---
  // The catalog comes from GET /api/admin/quests/catalog and the character's quests from
  // GET /api/admin/quests?account=. Quest names come from game data, so they are only ever set as text.
  var QUEST_PICKER_LIMIT = 200;
  var questTools = { catalog: null, catalogLoading: false, selectedId: null, account: null, requestSeq: 0 };

  function questToolsMarkup() {
    return '<section id="gm-quests" class="gm-tools-section gm-quests" hidden>' +
        '<h4 class="gm-tools-title" data-i18n="Quests">Quests</h4>' +
        '<p class="gm-tools-note" data-i18n="Find a quest by name or number and apply an action to the connected character. Repeat drops the quest and accepts it again.">Find a quest by name or number and apply an action to the connected character. Repeat drops the quest and accepts it again.</p>' +
        '<div class="gm-quest-picker">' +
          '<label class="form-label" for="gm-quest-search" data-i18n="Search quest">Search quest</label>' +
          '<input type="search" id="gm-quest-search" class="form-input" autocomplete="off" data-i18n-placeholder="Name or number" placeholder="Name or number">' +
          '<select id="gm-quest-select" class="form-input gm-quest-select" size="6" data-i18n-aria-label="Quest" aria-label="Quest"></select>' +
        '</div>' +
        '<div class="gm-warp-actions gm-quest-actions">' +
          '<button type="button" class="btn btn-secondary btn-sm" data-quest-action="accept" data-i18n="Accept">Accept</button>' +
          '<button type="button" class="btn btn-secondary btn-sm" data-quest-action="finish" data-i18n="Complete objectives">Complete objectives</button>' +
          '<button type="button" class="btn btn-secondary btn-sm" data-quest-action="done" data-i18n="Deliver">Deliver</button>' +
          '<button type="button" class="btn btn-secondary btn-sm" data-quest-action="drop" data-i18n="Drop">Drop</button>' +
          '<button type="button" class="btn btn-secondary btn-sm" data-quest-action="repeat" data-i18n="Repeat">Repeat</button>' +
        '</div>' +
        '<p id="gm-quest-result" class="gm-tools-result" aria-live="polite"></p>' +
        '<div class="gm-quest-head">' +
          '<h4 class="gm-tools-title" data-i18n="Character quests">Character quests</h4>' +
          '<button type="button" id="gm-quest-refresh" class="btn btn-secondary btn-sm" data-i18n="Refresh">Refresh</button>' +
        '</div>' +
        '<div class="table-container"><table class="data-table gm-quest-table"><thead><tr>' +
          '<th data-i18n="ID">ID</th>' +
          '<th data-i18n="Quest">Quest</th>' +
          '<th data-i18n="Status">Status</th>' +
          '<th data-i18n="Progress">Progress</th>' +
          '<th data-i18n="Times completed">Times completed</th>' +
          '<th data-i18n="Actions">Actions</th>' +
        '</tr></thead><tbody id="gm-quest-tbody"></tbody></table></div>' +
      '</section>';
  }

  function bindQuestTools() {
    document.getElementById('gm-quest-search').addEventListener('input', renderQuestPicker);
    document.getElementById('gm-quest-select').addEventListener('change', function (e) {
      questTools.selectedId = e.target.value ? parseInt(e.target.value, 10) : null;
    });
    document.querySelectorAll('#gm-quests .gm-quest-actions [data-quest-action]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!questTools.selectedId) {
          setGmResult(t('Choose a quest first.'), 'error', 'gm-quest-result');
          return;
        }
        runQuestAction(button.getAttribute('data-quest-action'), questTools.selectedId);
      });
    });
    document.getElementById('gm-quest-tbody').addEventListener('click', function (e) {
      var button = e.target.closest ? e.target.closest('[data-quest-row-action]') : null;
      if (!button) return;
      runQuestAction(button.getAttribute('data-quest-row-action'), parseInt(button.getAttribute('data-quest-id'), 10));
    });
    document.getElementById('gm-quest-refresh').addEventListener('click', loadCharacterQuests);
  }

  function runQuestAction(action, questId) {
    if (!questId || questId < 1) return;
    sendGmCommand('quest', { action: action, id: questId }, 'gm-quest-result').then(loadCharacterQuests);
  }

  function resetQuestTools() {
    var section = document.getElementById('gm-quests');
    if (!section) return;
    questTools.account = state.accountScreen.name || null;
    questTools.selectedId = null;
    document.getElementById('gm-quest-search').value = '';
    setGmResult('', '', 'gm-quest-result');
    clearChildren(document.getElementById('gm-quest-tbody'));
    if (!questTools.account) return;
    if (questTools.catalog) {
      section.hidden = false;
      renderQuestPicker();
      loadCharacterQuests();
      return;
    }
    if (questTools.catalogLoading) return;
    questTools.catalogLoading = true;
    apiFetch('/api/admin/quests/catalog')
      .then(function (data) {
        questTools.catalog = Array.isArray(data.quests) ? data.quests : [];
        section.hidden = false;
        renderQuestPicker();
        loadCharacterQuests();
      })
      .catch(function (err) {
        // 403: "quest" is not allowed, so the section stays hidden. Anything else is shown so it can be fixed.
        if (err.status === 403) return;
        section.hidden = false;
        setGmResult(err.message, 'error', 'gm-quest-result');
      })
      .finally(function () {
        questTools.catalogLoading = false;
      });
  }

  function clearChildren(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function questLabel(quest) {
    return quest.id + ' · ' + (quest.name || t('Unnamed quest'));
  }

  function renderQuestPicker() {
    var select = document.getElementById('gm-quest-select');
    if (!select) return;
    var query = (document.getElementById('gm-quest-search').value || '').trim().toLowerCase();
    var matches = (questTools.catalog || []).filter(function (quest) {
      return !query || String(quest.id).indexOf(query) !== -1 || String(quest.name || '').toLowerCase().indexOf(query) !== -1;
    });
    clearChildren(select);
    matches.slice(0, QUEST_PICKER_LIMIT).forEach(function (quest) {
      var option = document.createElement('option');
      option.value = String(quest.id);
      option.textContent = questLabel(quest);
      if (quest.id === questTools.selectedId) option.selected = true;
      select.appendChild(option);
    });
    if (matches.length > QUEST_PICKER_LIMIT) {
      var more = document.createElement('option');
      more.disabled = true;
      more.textContent = t('{count} more: refine the search', { count: matches.length - QUEST_PICKER_LIMIT });
      select.appendChild(more);
    }
  }

  function questStatusLabel(status) {
    switch (status) {
      case 'running': return t('In progress');
      case 'finish': return t('Objectives complete');
      case 'delivery': return t('Delivered');
      case 'canaccept': return t('Available');
      case 'fail': return t('Failed');
      case 'none': return t('Not started');
      default: return status || '—';
    }
  }

  function questProgressText(progress) {
    if (!Array.isArray(progress) || !progress.length) return '—';
    return progress.map(function (p) { return p.done + '/' + p.need; }).join(', ');
  }

  function questCell(row, text) {
    var cell = document.createElement('td');
    cell.textContent = text;
    row.appendChild(cell);
    return cell;
  }

  function questStateRow(tbody, message, isError) {
    var row = document.createElement('tr');
    var cell = questCell(row, message);
    cell.colSpan = 6;
    cell.className = 'table-state' + (isError ? ' gm-quest-error' : '');
    tbody.appendChild(row);
  }

  function loadCharacterQuests() {
    var tbody = document.getElementById('gm-quest-tbody');
    var account = questTools.account;
    if (!tbody || !account) return;
    var seq = ++questTools.requestSeq;
    clearChildren(tbody);
    questStateRow(tbody, t('Loading...'), false);
    apiFetch('/api/admin/quests?account=' + encodeURIComponent(account))
      .then(function (data) {
        if (seq !== questTools.requestSeq) return;
        renderCharacterQuests(tbody, Array.isArray(data.quests) ? data.quests : []);
      })
      .catch(function (err) {
        if (seq !== questTools.requestSeq) return;
        clearChildren(tbody);
        questStateRow(tbody, err.message, true);
      });
  }

  function renderCharacterQuests(tbody, quests) {
    clearChildren(tbody);
    if (!quests.length) {
      questStateRow(tbody, t('This character has no quests.'), false);
      return;
    }
    var rowActions = [
      ['repeat', t('Repeat')],
      ['finish', t('Complete objectives')],
      ['done', t('Deliver')],
      ['drop', t('Drop')]
    ];
    quests.forEach(function (quest) {
      var row = document.createElement('tr');
      questCell(row, String(quest.id));
      questCell(row, quest.name || t('Unnamed quest'));
      questCell(row, questStatusLabel(quest.status));
      questCell(row, questProgressText(quest.progress));
      questCell(row, formatNumber(quest.completed));
      var actions = questCell(row, '');
      actions.className = 'gm-quest-row-actions';
      rowActions.forEach(function (entry) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-secondary btn-sm';
        button.setAttribute('data-quest-row-action', entry[0]);
        button.setAttribute('data-quest-id', String(quest.id));
        button.textContent = entry[1];
        actions.appendChild(button);
      });
      tbody.appendChild(row);
    });
  }

  // --- Sidebar menu ---
  // Dashboard sits on its own, the other sections live in collapsible groups. The sidebar can fold into an icon
  // rail (the choice is remembered) and, on a phone, becomes a drawer opened from the header.
  var SIDEBAR_PREFS_KEY = 'panel_sidebar';
  var sidebarState = { collapsed: false, closedGroups: [] };
  var sidebarMobile = null;

  function readSidebarPrefs() {
    try {
      var prefs = JSON.parse(globalThis.localStorage.getItem(SIDEBAR_PREFS_KEY) || 'null');
      if (prefs && typeof prefs === 'object') {
        return {
          collapsed: prefs.collapsed === true,
          closedGroups: Array.isArray(prefs.closedGroups)
            ? prefs.closedGroups.filter(function (g) { return typeof g === 'string'; })
            : []
        };
      }
    } catch (e) {
      // Storage blocked or the value is not JSON: start from the defaults.
    }
    return { collapsed: false, closedGroups: [] };
  }

  function saveSidebarPrefs() {
    try {
      globalThis.localStorage.setItem(SIDEBAR_PREFS_KEY, JSON.stringify(sidebarState));
    } catch (e) {
      // Private mode or a full quota: the menu still works, it just forgets next time.
    }
  }

  function sidebarGroups() {
    return els.subnav ? Array.prototype.slice.call(els.subnav.querySelectorAll('.sidebar-group')) : [];
  }

  function toggleSidebarGroup(group, open) {
    if (!group) return;
    var willOpen = typeof open === 'boolean' ? open : !group.classList.contains('is-open');
    group.classList.toggle('is-open', willOpen);
    var toggle = group.querySelector('.sidebar-group-toggle');
    if (toggle) toggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    var name = group.getAttribute('data-group');
    var at = sidebarState.closedGroups.indexOf(name);
    if (willOpen && at !== -1) sidebarState.closedGroups.splice(at, 1);
    if (!willOpen && at === -1) sidebarState.closedGroups.push(name);
  }

  // Going to a section shows it: its group opens if the admin had folded it.
  function openSidebarGroupOf(tabId) {
    if (!els.subnav) return;
    Array.prototype.forEach.call(els.subnav.querySelectorAll('.tab-btn'), function (btn) {
      if (btn.getAttribute('data-tab') !== tabId) return;
      var group = btn.closest('.sidebar-group');
      if (group && !group.classList.contains('is-open')) toggleSidebarGroup(group, true);
    });
  }

  // In the icon rail the labels are hidden, so each item carries its name as tooltip and accessible name.
  function syncSidebarTitles() {
    if (!els.subnav) return;
    Array.prototype.forEach.call(els.subnav.querySelectorAll('.tab-btn'), function (btn) {
      var label = btn.querySelector('span:not(.tab-counter)');
      var name = label ? label.textContent.trim() : '';
      if (sidebarState.collapsed && name) {
        btn.setAttribute('title', name);
        btn.setAttribute('aria-label', name);
      } else {
        btn.removeAttribute('title');
        btn.removeAttribute('aria-label');
      }
    });
  }

  function setSidebarCollapsed(collapsed, persist) {
    sidebarState.collapsed = collapsed;
    if (els.appShell) els.appShell.classList.toggle('is-collapsed', collapsed);
    if (els.sidebarCollapse) {
      els.sidebarCollapse.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
      els.sidebarCollapse.setAttribute('aria-label', collapsed ? t('Expand menu') : t('Collapse menu'));
    }
    syncSidebarTitles();
    if (persist) saveSidebarPrefs();
  }

  // A language change rewrites the translated labels; the ones that depend on the state are set again.
  function refreshSidebarLabels() {
    if (!sidebarState) return;
    setSidebarCollapsed(sidebarState.collapsed, false);
  }

  function openSidebarDrawer() {
    if (!els.subnav) return;
    els.subnav.classList.add('is-open');
    if (els.sidebarBackdrop) els.sidebarBackdrop.hidden = false;
    if (els.sidebarOpen) els.sidebarOpen.setAttribute('aria-expanded', 'true');
    if (els.mainContent) els.mainContent.inert = true;
    var target = els.subnav.querySelector('.tab-btn.active') || els.sidebarClose;
    if (target) target.focus();
  }

  function closeSidebarDrawer(returnFocus) {
    if (!els.subnav || !els.subnav.classList.contains('is-open')) return;
    els.subnav.classList.remove('is-open');
    if (els.sidebarBackdrop) els.sidebarBackdrop.hidden = true;
    if (els.sidebarOpen) els.sidebarOpen.setAttribute('aria-expanded', 'false');
    if (els.mainContent) els.mainContent.inert = false;
    if (returnFocus && els.sidebarOpen) els.sidebarOpen.focus();
  }

  function handleSidebarKeydown(e) {
    if (e.key !== 'Escape' || !els.subnav || !els.subnav.classList.contains('is-open')) return;
    if (modalStack.length) return;
    e.preventDefault();
    closeSidebarDrawer(true);
  }

  function initSidebar() {
    var prefs = readSidebarPrefs();
    sidebarState.closedGroups = prefs.closedGroups;
    sidebarGroups().forEach(function (group) {
      if (prefs.closedGroups.indexOf(group.getAttribute('data-group')) !== -1) toggleSidebarGroup(group, false);
    });
    setSidebarCollapsed(prefs.collapsed, false);

    if (els.subnav) {
      els.subnav.addEventListener('click', function (e) {
        // Any section button closes the drawer, also one added by another script (Konsor's own section).
        if (e.target.closest('.tab-btn')) closeSidebarDrawer();
        var toggle = e.target.closest('.sidebar-group-toggle');
        if (!toggle) return;
        toggleSidebarGroup(toggle.closest('.sidebar-group'));
        saveSidebarPrefs();
      });
    }
    if (els.sidebarCollapse) {
      els.sidebarCollapse.addEventListener('click', function () {
        setSidebarCollapsed(!sidebarState.collapsed, true);
      });
    }
    if (els.sidebarOpen) els.sidebarOpen.addEventListener('click', openSidebarDrawer);
    if (els.sidebarClose) els.sidebarClose.addEventListener('click', function () { closeSidebarDrawer(true); });
    if (els.sidebarBackdrop) els.sidebarBackdrop.addEventListener('click', function () { closeSidebarDrawer(true); });
    document.addEventListener('keydown', handleSidebarKeydown);
    // Growing past phone width turns the drawer back into the fixed sidebar.
    if (typeof globalThis.matchMedia === 'function') {
      sidebarMobile = globalThis.matchMedia('(max-width: 860px)');
      sidebarMobile.addEventListener('change', function () { closeSidebarDrawer(false); });
    }
  }

  // --- Confirmation modal ---
  // Every delete and password change asks here first. askConfirm resolves true only when the admin confirms
  // (and, with typeToConfirm, typed that exact text); Cancel, the close button and Escape all resolve false.
  var confirmState = { resolve: null, expected: null };

  function settleConfirm(result) {
    var resolve = confirmState.resolve;
    confirmState.resolve = null;
    if (resolve) resolve(result);
  }

  function askConfirm(opts) {
    settleConfirm(false);
    var typed = typeof opts.typeToConfirm === 'string' && opts.typeToConfirm !== '';
    confirmState.expected = typed ? opts.typeToConfirm : null;
    els.confirmTitle.textContent = opts.title;
    els.confirmTitle.classList.toggle('modal-title-danger', !!opts.danger);
    els.confirmMessage.textContent = opts.message;
    els.confirmTypedGroup.hidden = !typed;
    els.confirmTypedLabel.textContent = opts.typeLabel || '';
    els.confirmTypedInput.value = '';
    els.confirmSubmit.textContent = opts.confirmLabel || t('Confirm');
    els.confirmSubmit.classList.toggle('btn-danger', !!opts.danger);
    els.confirmSubmit.classList.toggle('btn-primary', !opts.danger);
    els.confirmSubmit.disabled = typed;
    return new Promise(function (resolve) {
      confirmState.resolve = resolve;
      openModal(els.modalConfirm);
      if (typed) {
        els.confirmTypedInput.focus();
      } else {
        // Nothing to type: the safe choice has the focus, so a stray Enter never confirms.
        els.confirmCancel.focus();
      }
    });
  }

  function handleConfirmTyping() {
    if (confirmState.expected === null) return;
    els.confirmSubmit.disabled = els.confirmTypedInput.value !== confirmState.expected;
  }

  function handleConfirmSubmit(e) {
    e.preventDefault();
    if (confirmState.expected !== null && els.confirmTypedInput.value !== confirmState.expected) return;
    settleConfirm(true);
    closeModal(els.modalConfirm);
  }

  // Whole-sentence modal intros: `template` is a translated sentence containing {account}, which is
  // replaced with the bold, escaped account name (the rest of the sentence is escaped as text).
  function setModalIntro(id, template, accountName) {
    var el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = escapeHtml(template).replace('{account}', function () {
      return '<strong>' + escapeHtml(accountName) + '</strong>';
    });
  }

  function showChangePassword(name) {
    state.selectedAccount = { name: name };
    setModalIntro('pw-intro', t('Set a new password for account {account}. Active game sessions will be revoked.'), name);
    document.getElementById('pw-new-pass').value = '';
    openModal(els.modalPassword);
  }

  function handleUpdatePassword(e) {
    e.preventDefault();
    var submit = submitButtonOf(e);
    if (!state.selectedAccount || (submit && submit.disabled)) return;
    var newPass = document.getElementById('pw-new-pass').value || '';
    if (!newPass || newPass.length < 6) {
      showToast(t('The new password must be at least 6 characters.'), 'error');
      return;
    }

    var accountName = state.selectedAccount.name;
    askConfirm({
      title: t('Change password'),
      message: t('Change the password of account {account}? Active sessions of that account will be signed out.', { account: accountName }),
      confirmLabel: t('Change password')
    }).then(function (ok) {
      if (!ok) return null;
      setSubmitting(submit, true);
      return apiFetch('/api/admin/accounts/update-password', {
        method: 'POST',
        body: { username: accountName, new_password: newPass }
      })
        .then(function (data) {
          showToast(data.message, 'success');
          closeModal(els.modalPassword);
          refreshOpenAccount(accountName);
        })
        .catch(function (err) {
          showToast(t('Error: {message}', { message: err.message }), 'error');
        })
        .finally(function () {
          setSubmitting(submit, false);
        });
    });
  }

  function showCreateAccount() {
    document.getElementById('create-username').value = '';
    document.getElementById('create-password').value = '';
    document.getElementById('create-notes').value = '';
    openModal(els.modalCreate);
  }

  function handleCreateAccount(e) {
    e.preventDefault();
    var submit = submitButtonOf(e);
    if (submit && submit.disabled) return;
    var user = (document.getElementById('create-username').value || '').trim();
    var pass = (document.getElementById('create-password').value || '').trim();
    var notes = (document.getElementById('create-notes').value || '').trim();

    if (!user || user.length < 3) {
      showToast(t('The username must be at least 3 characters.'), 'error');
      return;
    }
    if (!pass || pass.length < 6) {
      showToast(t('The password must be at least 6 characters.'), 'error');
      return;
    }

    setSubmitting(submit, true);
    apiFetch('/api/admin/accounts/create', {
      method: 'POST',
      body: { username: user, password: pass, notes: notes }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        closeModal(els.modalCreate);
        loadAccounts();
        loadStats();
      })
      .catch(function (err) {
        showToast(t('Error creating account: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        setSubmitting(submit, false);
      });
  }

  function showBanAccount(name) {
    state.selectedAccount = { name: name };
    setModalIntro('ban-intro', state.bansSupported ?
      t('Suspending account {account} makes RO3Emu refuse its sign-in and revokes its active sessions.') :
      t('This RO3Emu does not support account bans, so account {account} cannot be suspended. Update RO3Emu first.'), name);
    document.getElementById('ban-reason').value = '';
    document.getElementById('ban-days').value = '';
    openModal(els.modalBan);
  }

  function handleBanAccount(e) {
    e.preventDefault();
    var submit = submitButtonOf(e);
    if (!state.selectedAccount || (submit && submit.disabled)) return;
    var reason = (document.getElementById('ban-reason').value || '').trim() || t('Administrative suspension');
    var accountName = state.selectedAccount.name;
    var body = { username: accountName, reason: reason };
    // Empty: a permanent ban. Otherwise RO3Emu lifts it by itself after that many days.
    var days = parseInt(document.getElementById('ban-days').value, 10);
    if (days > 0) body.days = days;

    setSubmitting(submit, true);
    apiFetch('/api/admin/accounts/ban', {
      method: 'POST',
      body: body
    })
      .then(function (data) {
        showToast(data.message, data.enforced === false ? 'info' : 'success');
        closeModal(els.modalBan);
        loadAccounts();
        loadStats();
        refreshOpenAccount(accountName);
      })
      .catch(function (err) {
        showToast(t('Error suspending account: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        setSubmitting(submit, false);
      });
  }

  function handleUnbanAccount(name, btn) {
    askConfirm({
      title: t('Remove suspension'),
      message: t('Do you want to reset and remove the suspension of account "{name}"?', { name: name }),
      confirmLabel: t('Remove suspension')
    }).then(function (ok) {
      if (!ok) return null;
      setSubmitting(btn, true);
      return apiFetch('/api/admin/accounts/unban', {
        method: 'POST',
        body: { username: name }
      })
        .then(function (data) {
          showToast(data.message, 'success');
          loadAccounts();
          loadStats();
          refreshOpenAccount(name);
        })
        .catch(function (err) {
          showToast(t('Error removing suspension: {message}', { message: err.message }), 'error');
        })
        .finally(function () {
          setSubmitting(btn, false);
        });
    });
  }

  function handleDeleteCharacter(btn) {
    var roleId = parseInt(btn.getAttribute('data-role-id'), 10);
    var name = btn.getAttribute('data-role-name') || '';
    var account = btn.getAttribute('data-account') || '';
    if (!roleId || !name) return;
    askConfirm({
      title: t('Delete character'),
      message: t('This deletes character {name} of account {account}. The character leaves the account; its data stays in the database.', { name: name, account: account }),
      danger: true,
      typeToConfirm: name,
      typeLabel: t('Type the exact character name to confirm'),
      confirmLabel: t('Delete character')
    }).then(function (ok) {
      if (!ok) return null;
      setSubmitting(btn, true);
      return apiFetch('/api/admin/characters/delete', {
        method: 'POST',
        body: { role_id: roleId, confirm_name: name }
      })
        .then(function (data) {
          showToast(data.message, 'success');
          refreshOpenAccount(account);
          loadAccounts();
          loadStats();
        })
        .catch(function (err) {
          showToast(t('Error: {message}', { message: err.message }), 'error');
        })
        .finally(function () {
          setSubmitting(btn, false);
        });
    });
  }

  function showDeleteAccount(name) {
    state.selectedAccount = { name: name };
    setModalIntro('del-intro', t('This action will permanently delete account {account}. To confirm, type the account name below:'), name);
    document.getElementById('del-confirm-name').value = '';
    openModal(els.modalDelete);
  }

  function handleDeleteAccount(e) {
    e.preventDefault();
    var submit = submitButtonOf(e);
    if (!state.selectedAccount || (submit && submit.disabled)) return;
    var typedName = (document.getElementById('del-confirm-name').value || '').trim();
    if (typedName !== state.selectedAccount.name) {
      showToast(t('You must type the account name exactly to confirm.'), 'error');
      return;
    }

    var accountName = state.selectedAccount.name;
    setSubmitting(submit, true);
    apiFetch('/api/admin/accounts/delete', {
      method: 'POST',
      body: { username: accountName }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        closeModal(els.modalDelete);
        loadAccounts();
        loadStats();
        if (state.accountScreen.open) {
          // The account is gone: leave its screen for the list without a leave-without-saving warning.
          state.accountScreen.notesBaseline = els.accountNotes.value;
          goToAccountList();
        }
      })
      .catch(function (err) {
        showToast(t('Error deleting account: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        setSubmitting(submit, false);
      });
  }

  function loadAuditLog() {
    var request = apiFetch('/api/admin/audit-log?page=' + encodeURIComponent(String(state.auditPage)));
    trackBusy(els.auditTbody, request);
    return request
      .then(function (data) {
        var logs = data.logs || [];
        state.auditPages = data.pages || 1;
        state.auditTotal = data.total || 0;
        if (!els.auditTbody) return;
        // Records were removed since the last load: land on the last page instead of an empty one.
        if (!logs.length && state.auditTotal > 0 && state.auditPage > state.auditPages) {
          state.auditPage = state.auditPages;
          return loadAuditLog();
        }
        renderPager(els.auditPager, els.auditPagerInfo, els.auditPagerPrev, els.auditPagerNext,
          state.auditPage, state.auditPages, state.auditTotal, 'records');
        if (!logs.length) {
          els.auditTbody.innerHTML = emptyRow(5, t('No audit records yet.'));
          return;
        }
        var html = '';
        logs.forEach(function (l) {
          html += '<tr>' +
            '<td class="cell-meta">' + formatDate(l.created_utc) + '</td>' +
            '<td><strong class="text-gold">' + escapeHtml(l.admin_user) + '</strong></td>' +
            '<td><span class="badge badge-admin">' + escapeHtml(l.action) + '</span></td>' +
            '<td>' + auditTargetHtml(l) + '</td>' +
            '<td class="text-muted">' + escapeHtml(l.details) + '</td>' +
          '</tr>';
        });
        els.auditTbody.innerHTML = html;
      })
      .catch(function (err) {
        var message = t('Error loading records: {message}', { message: err.message });
        if (els.auditTbody) els.auditTbody.innerHTML = errorRowHtml(5, message, 'audit');
        showToast(message, 'error');
      });
  }

  function goToAuditPage(page) {
    if (page < 1 || page > state.auditPages || page === state.auditPage) return;
    state.auditPage = page;
    loadAuditLog();
  }

  // --- Economy Log (read-only) ---
  function loadEconomy() {
    var eco = state.economy;
    var params = new URLSearchParams();
    if (eco.account) params.set('account', eco.account);
    if (eco.character) params.set('character', eco.character);
    if (eco.from) params.set('from', eco.from);
    if (eco.to) params.set('to', eco.to);
    params.set('page', String(eco.page));
    params.set('page_size', String(eco.pageSize));

    var request = apiFetch('/api/admin/economy?' + params.toString());
    trackBusy(els.economyTbody, request);
    request
      .then(function (data) {
        eco.page = data.page || 1;
        eco.pages = data.pages || 1;
        if (els.economyUnavailable) els.economyUnavailable.hidden = data.available !== false;
        renderEconomyTable(data.entries || [], data.available !== false);
        renderEconomyPager(data.total || 0);
      })
      .catch(function (err) {
        var message = t('Error loading economy: {message}', { message: err.message });
        if (els.economyTbody) els.economyTbody.innerHTML = errorRowHtml(7, message, 'economy');
        showToast(message, 'error');
      });
  }

  function describeEconomyOwner(e) {
    if (e.owner_name) return accountLinkHtml(e.owner_account, e.owner_name);
    return escapeHtml(e.owner_kind_label) + ' ' + escapeHtml(e.owner_id);
  }

  function renderEconomyTable(entries, available) {
    if (!els.economyTbody) return;
    if (!entries.length) {
      els.economyTbody.innerHTML = emptyRow(7, available ? t('No movements for the selected filters.') : t('Economy log not available in this database.'));
      return;
    }
    var html = '';
    entries.forEach(function (e) {
      var deltaClass = e.delta < 0 ? 'economy-delta-neg' : 'economy-delta-pos';
      var deltaText = (e.delta > 0 ? '+' : '') + formatNumber(e.delta);
      var actorRole = e.actor_role_name ? e.actor_role_name : ('#' + String(e.actor_role));
      html += '<tr>' +
        '<td class="cell-meta">' + formatDate(e.recorded_utc) + '</td>' +
        '<td><span class="badge badge-admin">' + escapeHtml(e.command_kind) + '</span>' +
          '<div class="economy-sub" title="' + escapeHtml(e.operation_id) + '">' + escapeHtml(e.operation_id) + '</div></td>' +
        '<td><strong class="text-strong">' + accountLinkHtml(e.actor_account) + '</strong>' +
          '<div class="economy-sub">' + (e.actor_role_name ? accountLinkHtml(e.actor_account, actorRole) : escapeHtml(actorRole)) + '</div></td>' +
        '<td>' + describeEconomyOwner(e) + '</td>' +
        '<td>' + escapeHtml(e.asset_label) + '</td>' +
        '<td class="' + deltaClass + '">' + escapeHtml(deltaText) + '</td>' +
        '<td class="text-muted">' + escapeHtml(String(e.reason_code)) + '</td>' +
      '</tr>';
    });
    els.economyTbody.innerHTML = html;
  }

  function renderEconomyPager(total) {
    var eco = state.economy;
    if (els.economyPageInfo) {
      els.economyPageInfo.textContent = t('Page {page} of {pages} ({total} movements)', { page: eco.page, pages: eco.pages, total: formatNumber(total) });
    }
    if (els.economyPrev) els.economyPrev.disabled = eco.page <= 1;
    if (els.economyNext) els.economyNext.disabled = eco.page >= eco.pages;
  }

  function applyEconomyFilters(e) {
    if (e) e.preventDefault();
    var eco = state.economy;
    eco.account = (els.economyAccount.value || '').trim();
    eco.character = (els.economyCharacter.value || '').trim();
    eco.from = els.economyFrom.value || '';
    eco.to = els.economyTo.value || '';
    eco.page = 1;
    loadEconomy();
  }

  function resetEconomyFilters() {
    els.economyAccount.value = '';
    els.economyCharacter.value = '';
    els.economyFrom.value = '';
    els.economyTo.value = '';
    applyEconomyFilters();
  }

  function changeEconomyPage(step) {
    var eco = state.economy;
    var next = eco.page + step;
    if (next < 1 || next > eco.pages) return;
    eco.page = next;
    loadEconomy();
  }

  // --- Rankings (read-only) ---
  function rankingMetricLabel(type) {
    if (type === 'level') return t('Base Level');
    if (type === 'zeny') return t('Zeny');
    if (type === 'power') return t('Power');
    return '';
  }

  function renderRankingsHead(type) {
    if (!els.rankingsThead) return;
    if (type === 'guilds') {
      els.rankingsThead.innerHTML = '<tr>' +
        '<th class="w-10">#</th>' +
        '<th>' + escapeHtml(t('Clan')) + '</th>' +
        '<th class="w-22">' + escapeHtml(t('Active Members')) + '</th>' +
        '<th class="w-22">' + escapeHtml(t('Total Level')) + '</th>' +
      '</tr>';
      return;
    }
    els.rankingsThead.innerHTML = '<tr>' +
      '<th class="w-8">#</th>' +
      '<th>' + escapeHtml(t('Character')) + '</th>' +
      '<th class="w-18">' + escapeHtml(t('Account')) + '</th>' +
      '<th class="w-18">' + escapeHtml(t('Class')) + '</th>' +
      '<th class="w-14">' + escapeHtml(t('Level / Job')) + '</th>' +
      '<th class="w-16">' + escapeHtml(rankingMetricLabel(type)) + '</th>' +
    '</tr>';
  }

  function renderRankingsPager() {
    var totalPages = Math.max(1, Math.ceil(state.rankingTotal / state.rankingLimit));
    if (els.rankingPageLabel) {
      els.rankingPageLabel.textContent = t('Page {page} of {pages} ({total})', {
        page: state.rankingPage,
        pages: totalPages,
        total: formatNumber(state.rankingTotal)
      });
    }
    if (els.rankingPrev) els.rankingPrev.disabled = state.rankingPage <= 1;
    if (els.rankingNext) els.rankingNext.disabled = state.rankingPage >= totalPages;
  }

  function loadRankings() {
    var type = state.rankingType;
    var url = '/api/admin/rankings?type=' + encodeURIComponent(type) +
      '&limit=' + state.rankingLimit + '&page=' + state.rankingPage;
    renderRankingsHead(type);
    var request = apiFetch(url);
    trackBusy(els.rankingsTbody, request);
    request
      .then(function (data) {
        if (!els.rankingsTbody) return;
        var rows = data.rankings || [];
        var colspan = type === 'guilds' ? 4 : 6;
        state.rankingTotal = data.total || 0;
        renderRankingsPager();

        if (data.available === false) {
          els.rankingsTbody.innerHTML = emptyRow(colspan, t('The database has no clan tables yet.'));
          return;
        }
        if (!rows.length) {
          els.rankingsTbody.innerHTML = emptyRow(colspan, t('No data for this ranking.'));
          return;
        }

        var html = '';
        rows.forEach(function (r) {
          if (type === 'guilds') {
            html += '<tr>' +
              '<td><strong class="text-gold">' + r.rank + '</strong></td>' +
              '<td><strong class="text-strong">' + escapeHtml(r.name) + '</strong></td>' +
              '<td>' + formatNumber(r.member_count) + '</td>' +
              '<td>' + formatNumber(r.total_level) + '</td>' +
            '</tr>';
            return;
          }
          html += '<tr>' +
            '<td><strong class="text-gold">' + r.rank + '</strong></td>' +
            '<td><strong class="text-strong">' + accountLinkHtml(r.account, r.name) + '</strong></td>' +
            '<td class="text-muted">' + accountLinkHtml(r.account) + '</td>' +
            '<td>' + escapeHtml(r.career_name) + '</td>' +
            '<td>' + formatNumber(r.level) + ' / ' + formatNumber(r.job_level) + '</td>' +
            '<td><strong>' + formatNumber(r.value) + '</strong></td>' +
          '</tr>';
        });
        els.rankingsTbody.innerHTML = html;
      })
      .catch(function (err) {
        var message = t('Error loading rankings: {message}', { message: err.message });
        if (els.rankingsTbody) els.rankingsTbody.innerHTML = errorRowHtml(type === 'guilds' ? 4 : 6, message, 'rankings');
        showToast(message, 'error');
      });
  }

  // --- Read-only views: Guilds & Auctions ---
  // escapeHtml() returns '' for 0, so numbers go through String() first.
  function cellValue(value) {
    if (value === null || value === undefined) return '—';
    return escapeHtml(String(value));
  }

  function emptyRow(colspan, text) {
    return '<tr><td colspan="' + colspan + '" class="table-state">' + escapeHtml(text) + '</td></tr>';
  }

  // kind selects a whole-sentence label ('guilds' or 'records') so word order can differ per language.
  function renderPager(pagerEl, infoEl, prevEl, nextEl, page, pages, total, kind) {
    if (!pagerEl) return;
    pagerEl.hidden = total === 0;
    if (infoEl) {
      var info = { page: page, pages: pages, total: formatNumber(total) };
      infoEl.textContent = kind === 'guilds' ?
        t('Page {page} of {pages} ({total} guilds)', info) :
        t('Page {page} of {pages} ({total} records)', info);
    }
    if (prevEl) prevEl.disabled = page <= 1;
    if (nextEl) nextEl.disabled = page >= pages;
  }

  function loadGuilds() {
    var params = new URLSearchParams();
    if (state.guildQuery) params.set('q', state.guildQuery);
    params.set('page', String(state.guildsPage));

    var request = apiFetch('/api/admin/guilds?' + params.toString());
    trackBusy(els.guildsTbody, request);
    request
      .then(function (data) {
        state.guildsPages = data.pages || 1;
        state.guildsTotal = data.total || 0;
        if (els.guildsUnavailable) els.guildsUnavailable.hidden = data.available !== false;
        renderGuildsTable(data.guilds || []);
        renderPager(els.guildsPager, els.guildsPagerInfo, els.guildsPagerPrev, els.guildsPagerNext,
          state.guildsPage, state.guildsPages, state.guildsTotal, 'guilds');
      })
      .catch(function (err) {
        var message = t('Error loading guilds: {message}', { message: err.message });
        if (els.guildsTbody) els.guildsTbody.innerHTML = errorRowHtml(6, message, 'guilds');
        showToast(message, 'error');
      });
  }

  function renderGuildsTable(guilds) {
    if (!els.guildsTbody) return;
    if (!guilds.length) {
      els.guildsTbody.innerHTML = emptyRow(6, t('No guilds found.'));
      return;
    }
    var html = '';
    guilds.forEach(function (g) {
      html += '<tr>' +
        '<td class="text-muted">' + cellValue(g.id) + '</td>' +
        '<td><strong class="text-strong">' + escapeHtml(g.name) + '</strong></td>' +
        '<td>' + cellValue(g.level) + '</td>' +
        '<td>' + cellValue(g.member_count) + '</td>' +
        '<td>' + cellValue(g.total_level) + '</td>' +
        '<td><button class="btn btn-secondary btn-sm btn-view-guild" data-guild="' + cellValue(g.id) + '" title="' + escapeHtml(t('View members')) + '">' + escapeHtml(t('Record')) + '</button></td>' +
      '</tr>';
    });
    els.guildsTbody.innerHTML = html;
  }

  function goToGuildsPage(page) {
    if (page < 1 || page > state.guildsPages || page === state.guildsPage) return;
    state.guildsPage = page;
    loadGuilds();
  }

  function showGuildDetail(guildId) {
    apiFetch('/api/admin/guilds/' + encodeURIComponent(guildId))
      .then(function (data) {
        if (data.available === false || !data.guild) {
          showToast(t('The database does not contain guild tables.'), 'info');
          return;
        }
        var g = data.guild;
        document.getElementById('guild-detail-name').textContent = g.name;
        document.getElementById('guild-detail-summary').innerHTML =
          '<div><strong>ID:</strong> <div>' + cellValue(g.id) + '</div></div>' +
          '<div><strong>' + escapeHtml(t('Level:')) + '</strong> <div>' + cellValue(g.level) + '</div></div>' +
          '<div><strong>' + escapeHtml(t('Members:')) + '</strong> <div>' + cellValue(g.member_count) + '</div></div>' +
          '<div><strong>' + escapeHtml(t('Total level:')) + '</strong> <div>' + cellValue(g.total_level) + '</div></div>';

        var members = data.members || [];
        var tbody = document.getElementById('guild-members-tbody');
        if (!members.length) {
          tbody.innerHTML = emptyRow(4, t('This guild has no active members.'));
        } else {
          var html = '';
          members.forEach(function (m) {
            html += '<tr>' +
              '<td><strong class="text-strong">' + accountLinkHtml(m.account, m.name) + '</strong></td>' +
              '<td>' + accountLinkHtml(m.account) + '</td>' +
              '<td>' + escapeHtml(m.career_name) + '</td>' +
              '<td>' + cellValue(m.level) + '</td>' +
            '</tr>';
          });
          tbody.innerHTML = html;
        }
        openModal(els.modalGuild);
      })
      .catch(function (err) {
        showToast(t('Error loading guild: {message}', { message: err.message }), 'error');
      });
  }

  // Built per call so the column labels follow the active language.
  function auctionColumns(view) {
    if (view === 'prebuy') {
      return [
        ['id', 'ID'], ['role_name', t('Character')], ['role_id', t('Character ID')], ['auction_type', t('Type')],
        ['item_id', t('Item ID')], ['quantity', t('Quantity')], ['unit_price', t('Unit price')],
        ['currency', t('Currency')], ['processed', t('Processed')], ['paused', t('Paused')]
      ];
    }
    return [
      ['id', 'ID'], ['source_key', t('Source')], ['auction_type', t('Type')],
      ['run_id', t('Round')], ['end_time', t('End')], ['settled', t('Settled')]
    ];
  }

  function auctionCell(value) {
    if (value === true) return t('Yes');
    if (value === false) return t('No');
    return cellValue(value);
  }

  function loadAuctions() {
    var params = new URLSearchParams();
    params.set('view', state.auctionView);
    params.set('page', String(state.auctionsPage));

    var request = apiFetch('/api/admin/auctions?' + params.toString());
    trackBusy(els.auctionsTbody, request);
    request
      .then(function (data) {
        state.auctionsPages = data.pages || 1;
        state.auctionsTotal = data.total || 0;
        if (els.auctionsUnavailable) els.auctionsUnavailable.hidden = data.available !== false;
        renderAuctionsTable(data.view || state.auctionView, data.rows || []);
        renderPager(els.auctionsPager, els.auctionsPagerInfo, els.auctionsPagerPrev, els.auctionsPagerNext,
          state.auctionsPage, state.auctionsPages, state.auctionsTotal, 'records');
      })
      .catch(function (err) {
        var message = t('Error loading auctions: {message}', { message: err.message });
        if (els.auctionsTbody) els.auctionsTbody.innerHTML = errorRowHtml(6, message, 'auctions');
        showToast(message, 'error');
      });
  }

  function renderAuctionsTable(view, rows) {
    var columns = auctionColumns(view);
    if (els.auctionsThead) {
      els.auctionsThead.innerHTML = '<tr>' + columns.map(function (c) {
        return '<th>' + escapeHtml(c[1]) + '</th>';
      }).join('') + '</tr>';
    }
    if (!els.auctionsTbody) return;
    if (!rows.length) {
      els.auctionsTbody.innerHTML = emptyRow(columns.length, t('No auction records.'));
      return;
    }
    els.auctionsTbody.innerHTML = rows.map(function (r) {
      return '<tr>' + columns.map(function (c) {
        // A character in the pre-buy list links to the account it belongs to.
        var cell = c[0] === 'role_name' && r.role_name ? accountLinkHtml(r.role_account, r.role_name) : auctionCell(r[c[0]]);
        return '<td>' + cell + '</td>';
      }).join('') + '</tr>';
    }).join('');
  }

  function goToAuctionsPage(page) {
    if (page < 1 || page > state.auctionsPages || page === state.auctionsPage) return;
    state.auctionsPage = page;
    loadAuctions();
  }

  // --- Gift Codes ---
  // Rewards are redeemed in the game client; the panel only creates, lists and enables/disables codes.
  function giftCodeStatusBadge(status) {
    switch (status) {
      case 'active':
        return '<span class="badge badge-active">' + escapeHtml(t('Active')) + '</span>';
      case 'scheduled':
        return '<span class="badge badge-admin">' + escapeHtml(t('Scheduled')) + '</span>';
      case 'disabled':
        return '<span class="badge badge-banned">' + escapeHtml(t('Disabled')) + '</span>';
      case 'expired':
        return '<span class="badge badge-banned">' + escapeHtml(t('Expired')) + '</span>';
      case 'exhausted':
        return '<span class="badge badge-banned">' + escapeHtml(t('Exhausted')) + '</span>';
      default:
        return '<span class="badge badge-admin">' + escapeHtml(String(status || '')) + '</span>';
    }
  }

  function giftCodeRewardsHtml(items) {
    if (!items || !items.length) return '—';
    return '<ul class="item-chip-list">' + items.map(function (item) {
      return '<li>' + itemChipHtml(item, ' <span class="item-qty">x' + escapeHtml(String(item.count)) + '</span>') + '</li>';
    }).join('') + '</ul>';
  }

  // Unix seconds from the API, shown in the active locale; "—" when unset.
  function giftCodeDate(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    return escapeHtml(formatDate(seconds * 1000));
  }

  function renderGiftCodesTable(codes) {
    if (!els.giftCodesTbody) return;
    if (!codes.length) {
      els.giftCodesTbody.innerHTML = emptyRow(10, t('No gift codes yet.'));
      return;
    }
    var html = '';
    codes.forEach(function (c) {
      var limit = c.max_uses > 0 ? formatNumber(c.max_uses) : t('unlimited');
      var isDisabled = c.status === 'disabled' || c.disabled === true;
      var toggleLabel = isDisabled ? t('Enable') : t('Disable');
      var toggleClass = isDisabled ? 'btn-secondary' : 'btn-danger';
      html += '<tr>' +
        '<td><span class="giftcode-code">' + escapeHtml(c.code) + '</span></td>' +
        '<td class="giftcode-rewards">' + giftCodeRewardsHtml(c.items) + '</td>' +
        '<td>' + escapeHtml(formatNumber(c.uses) + ' / ' + limit) + '</td>' +
        '<td>' + cellValue(c.per_account) + '</td>' +
        '<td>' + giftCodeDate(c.starts_utc) + '</td>' +
        '<td>' + giftCodeDate(c.expires_utc) + '</td>' +
        '<td>' + giftCodeStatusBadge(c.status) + '</td>' +
        '<td>' + (c.created_by ? escapeHtml(c.created_by) : '—') + '</td>' +
        '<td>' + (c.note ? escapeHtml(c.note) : '—') + '</td>' +
        '<td><button type="button" class="btn ' + toggleClass + ' btn-sm btn-giftcode-toggle" data-code="' + escapeHtml(c.code) + '" data-action="' + (isDisabled ? 'enable' : 'disable') + '">' + escapeHtml(toggleLabel) + '</button></td>' +
      '</tr>';
    });
    els.giftCodesTbody.innerHTML = html;
  }

  function loadGiftCodes() {
    var request = apiFetch('/api/admin/gift-codes');
    trackBusy(els.giftCodesTbody, request);
    request
      .then(function (data) {
        var unavailable = data.available === false;
        if (els.giftCodesUnavailable) {
          els.giftCodesUnavailable.hidden = !unavailable;
          els.giftCodesUnavailable.textContent = unavailable ? (data.reason || '') : '';
        }
        if (els.giftCodesTableWrap) els.giftCodesTableWrap.hidden = unavailable;
        if (els.btnNewGiftCode) els.btnNewGiftCode.hidden = unavailable;
        if (unavailable) return;
        renderGiftCodesTable(data.codes || []);
      })
      .catch(function (err) {
        var message = t('Error loading gift codes: {message}', { message: err.message });
        if (els.giftCodesTbody) els.giftCodesTbody.innerHTML = errorRowHtml(10, message, 'giftcodes');
        showToast(message, 'error');
      });
  }

  function handleGiftCodeToggle(code, action) {
    var path = action === 'enable' ? '/enable' : '/disable';
    apiFetch('/api/admin/gift-codes' + path, {
      method: 'POST',
      body: { code: code }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        loadGiftCodes();
      })
      .catch(function (err) {
        showToast(err.message, 'error');
        loadGiftCodes();
      });
  }

  function setGiftCodeError(message) {
    if (!els.giftCodeError) return;
    els.giftCodeError.hidden = !message;
    els.giftCodeError.textContent = message || '';
  }

  function updateGiftCodeRemoveButtons() {
    if (!els.giftCodeItems) return;
    var rows = els.giftCodeItems.querySelectorAll('.giftcode-item-row');
    rows.forEach(function (row) {
      row.querySelector('.btn-giftcode-remove-item').disabled = rows.length <= 1;
    });
  }

  function addGiftCodeItemRow() {
    if (!els.giftCodeItems) return;
    var row = document.createElement('div');
    row.className = 'giftcode-item-row';
    row.innerHTML =
      '<input type="number" class="form-input giftcode-item-entry" min="1" step="1" inputmode="numeric" placeholder="Item ID" data-i18n-placeholder="Item ID" aria-label="Item ID" data-i18n-aria-label="Item ID">' +
      '<input type="number" class="form-input giftcode-item-count" min="1" step="1" value="1" inputmode="numeric" placeholder="Quantity" data-i18n-placeholder="Quantity" aria-label="Quantity" data-i18n-aria-label="Quantity">' +
      '<button type="button" class="btn btn-secondary btn-sm btn-giftcode-remove-item" title="Remove reward" data-i18n-title="Remove reward" aria-label="Remove reward" data-i18n-aria-label="Remove reward">&times;</button>';
    els.giftCodeItems.appendChild(row);
    applyI18n(row);
    updateGiftCodeRemoveButtons();
  }

  function showCreateGiftCode() {
    document.getElementById('giftcode-code').value = '';
    document.getElementById('giftcode-max-uses').value = '0';
    document.getElementById('giftcode-per-account').value = '1';
    document.getElementById('giftcode-starts').value = '';
    document.getElementById('giftcode-expires').value = '';
    document.getElementById('giftcode-note').value = '';
    els.giftCodeItems.innerHTML = '';
    addGiftCodeItemRow();
    setGiftCodeError('');
    openModal(els.modalGiftCode);
  }

  // Whole non-negative integer from a form field, or null when it is not one.
  function parseWholeNumber(value) {
    var text = String(value === null || value === undefined ? '' : value).trim();
    return /^\d{1,15}$/.test(text) ? Number(text) : null;
  }

  // datetime-local gives local time without a zone; the API wants unix seconds. Empty means no limit.
  function datetimeLocalToUnix(value) {
    if (!value) return null;
    var date = new Date(value);
    return isNaN(date.getTime()) ? NaN : Math.floor(date.getTime() / 1000);
  }

  function handleCreateGiftCode(e) {
    e.preventDefault();
    var pending = document.getElementById('btn-giftcode-submit');
    if (pending && pending.disabled) return;
    var code = (document.getElementById('giftcode-code').value || '').trim();
    if (code.length < 1 || code.length > 64) {
      setGiftCodeError(t('The code must be between 1 and 64 characters.'));
      return;
    }

    var items = [];
    var itemsValid = true;
    els.giftCodeItems.querySelectorAll('.giftcode-item-row').forEach(function (row) {
      var entry = parseWholeNumber(row.querySelector('.giftcode-item-entry').value);
      var count = parseWholeNumber(row.querySelector('.giftcode-item-count').value);
      if (!entry || !count) {
        itemsValid = false;
        return;
      }
      items.push({ entry: entry, count: count });
    });
    if (!itemsValid || !items.length) {
      setGiftCodeError(t('Every reward needs a positive item ID and a positive quantity.'));
      return;
    }

    var maxUses = parseWholeNumber(document.getElementById('giftcode-max-uses').value);
    if (maxUses === null) {
      setGiftCodeError(t('Max uses must be 0 (unlimited) or a positive whole number.'));
      return;
    }
    var perAccount = parseWholeNumber(document.getElementById('giftcode-per-account').value);
    if (!perAccount) {
      setGiftCodeError(t('Uses per account must be a positive whole number.'));
      return;
    }

    var starts = datetimeLocalToUnix(document.getElementById('giftcode-starts').value);
    var expires = datetimeLocalToUnix(document.getElementById('giftcode-expires').value);
    if (Number.isNaN(starts) || Number.isNaN(expires)) {
      setGiftCodeError(t('Enter valid start and expiry dates.'));
      return;
    }
    if (starts !== null && expires !== null && expires <= starts) {
      setGiftCodeError(t('The expiry must be later than the start.'));
      return;
    }

    var note = (document.getElementById('giftcode-note').value || '').trim();
    setGiftCodeError('');

    var submit = document.getElementById('btn-giftcode-submit');
    setSubmitting(submit, true);
    apiFetch('/api/admin/gift-codes', {
      method: 'POST',
      body: {
        code: code,
        items: items,
        max_uses: maxUses,
        per_account: perAccount,
        starts_utc: starts,
        expires_utc: expires,
        note: note || null
      }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        closeModal(els.modalGiftCode);
        loadGiftCodes();
      })
      .catch(function (err) {
        setGiftCodeError(err.message);
        showToast(err.message, 'error');
      })
      .finally(function () {
        setSubmitting(submit, false);
      });
  }

  // --- Web Market (read-only) ---
  var MARKET_PAGE_SIZE = 50;

  function marketStatusBadge(status) {
    if (status === 'active') return '<span class="badge badge-active">' + escapeHtml(t('Active')) + '</span>';
    if (status === 'sold') return '<span class="badge badge-admin">' + escapeHtml(t('Sold')) + '</span>';
    if (status === 'cancelled') return '<span class="badge badge-banned">' + escapeHtml(t('Cancelled')) + '</span>';
    return status ? escapeHtml(String(status)) : '—';
  }

  function renderMarketSummary(summary) {
    var s = summary || {};
    function set(el, value) {
      if (el) el.textContent = formatNumber(value);
    }
    set(document.getElementById('market-stat-active'), s.active);
    set(document.getElementById('market-stat-sold'), s.sold);
    set(document.getElementById('market-stat-active-zeny'), s.active_zeny);
    set(document.getElementById('market-stat-pending-zeny'), s.pending_zeny);
    var sub = t('{count} pending claims', { count: formatNumber(s.pending_claims) });
    var subEl = document.getElementById('market-stat-pending-sub');
    if (subEl) subEl.textContent = sub;
    var card = document.getElementById('market-card-pending');
    if (card) card.title = sub;
  }

  // Seller and buyer cells: account on top, character underneath.
  function marketPartyCell(account, character) {
    if (!account) return '—';
    var html = '<strong class="market-account">' + accountLinkHtml(account) + '</strong>';
    if (character) html += '<div class="economy-sub" title="' + escapeHtml(character) + '">' + accountLinkHtml(account, character) + '</div>';
    return html;
  }

  function renderMarketTable(listings) {
    if (!els.marketTbody) return;
    if (!listings.length) {
      els.marketTbody.innerHTML = emptyRow(8, t('No market listings found.'));
      return;
    }
    var html = '';
    listings.forEach(function (l) {
      var lockedBadge = l.locked ? ' <span class="badge badge-banned">' + escapeHtml(t('Locked')) + '</span>' : '';
      var pack = l.pack_name ? '<div class="economy-sub" title="' + escapeHtml(l.pack_name) + '">' + escapeHtml(l.pack_name) + '</div>' : '';
      html += '<tr>' +
        '<td class="market-item">' + itemChipHtml(l, lockedBadge) + pack + '</td>' +
        '<td>' + formatNumber(l.stack) + '</td>' +
        '<td><span class="market-price">' + formatNumber(l.price_zeny) + ' Z</span></td>' +
        '<td>' + marketPartyCell(l.seller_account, l.seller_role_name) + '</td>' +
        '<td>' + marketStatusBadge(l.status) + '</td>' +
        '<td>' + marketPartyCell(l.buyer_account, l.buyer_role_name) + '</td>' +
        '<td class="market-date">' + formatDate(l.created_utc) + '</td>' +
        '<td class="market-date">' + formatDate(l.updated_utc) + '</td>' +
      '</tr>';
    });
    els.marketTbody.innerHTML = html;
  }

  function loadMarket() {
    var market = state.market;
    var requestId = market.request + 1;
    market.request = requestId;
    var params = new URLSearchParams();
    params.set('status', market.status);
    if (market.query) params.set('q', market.query);
    params.set('page', String(market.page));
    params.set('page_size', String(MARKET_PAGE_SIZE));

    var request = apiFetch('/api/admin/market?' + params.toString());
    trackBusy(els.marketTbody, request);
    return request
      .then(function (data) {
        // A newer filter or page request supersedes this response.
        if (requestId !== market.request) return;
        var listings = data.listings || [];
        market.pages = data.pages || 1;
        market.total = data.total || 0;
        var unavailable = data.available === false;
        if (els.marketUnavailable) {
          els.marketUnavailable.hidden = !unavailable;
          els.marketUnavailable.textContent = unavailable ? (data.reason || t('The web market is not available in this database.')) : '';
        }
        if (els.marketSummary) els.marketSummary.hidden = unavailable;
        if (els.marketTableWrap) els.marketTableWrap.hidden = unavailable;
        if (unavailable) {
          renderPager(els.marketPager, els.marketPagerInfo, els.marketPagerPrev, els.marketPagerNext, 1, 1, 0, 'records');
          return;
        }
        // Listings were removed since the last load: land on the last page instead of an empty one.
        if (!listings.length && market.total > 0 && market.page > market.pages) {
          market.page = market.pages;
          return loadMarket();
        }
        renderMarketSummary(data.summary);
        renderMarketTable(listings);
        renderPager(els.marketPager, els.marketPagerInfo, els.marketPagerPrev, els.marketPagerNext,
          market.page, market.pages, market.total, 'records');
      })
      .catch(function (err) {
        if (requestId !== market.request) return;
        var message = t('Error loading market: {message}', { message: err.message });
        if (els.marketTbody) els.marketTbody.innerHTML = errorRowHtml(8, message, 'market');
        showToast(message, 'error');
      });
  }

  function applyMarketFilters(e) {
    if (e && e.preventDefault) e.preventDefault();
    state.market.status = els.marketStatusSelect ? els.marketStatusSelect.value : 'active';
    state.market.query = els.marketSearchInput ? els.marketSearchInput.value.trim() : '';
    state.market.page = 1;
    loadMarket();
  }

  function resetMarketFilters() {
    if (els.marketStatusSelect) els.marketStatusSelect.value = 'active';
    if (els.marketSearchInput) els.marketSearchInput.value = '';
    state.market.status = 'active';
    state.market.query = '';
    state.market.page = 1;
    loadMarket();
  }

  function goToMarketPage(page) {
    if (page < 1 || page > state.market.pages || page === state.market.page) return;
    state.market.page = page;
    loadMarket();
  }

  // --- Tabs Switching ---
  // The loader behind each Retry button of a table error row (see errorRowHtml).
  var RETRY_LOADERS = {
    accounts: loadAccounts,
    audit: loadAuditLog,
    economy: loadEconomy,
    rankings: loadRankings,
    guilds: loadGuilds,
    auctions: loadAuctions,
    giftcodes: loadGiftCodes,
    market: loadMarket
  };

  function switchTab(tabId) {
    var previousTab = state.activeTab;
    state.activeTab = tabId;
    openSidebarGroupOf(tabId);
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      var active = b.getAttribute('data-tab') === tabId;
      b.classList.toggle('active', active);
      if (active) {
        b.setAttribute('aria-current', 'page');
      } else {
        b.removeAttribute('aria-current');
      }
    });

    if (els.tabViewDashboard) els.tabViewDashboard.hidden = (tabId !== 'dashboard');
    if (tabId !== 'accounts' && state.accountScreen.open) resetAccountScreen();
    renderAccountsViews();
    if (els.tabViewAudit) els.tabViewAudit.hidden = (tabId !== 'audit');
    if (els.tabViewEconomy) els.tabViewEconomy.hidden = (tabId !== 'economy');
    if (els.tabViewRankings) els.tabViewRankings.hidden = (tabId !== 'rankings');
    if (els.tabViewGuilds) els.tabViewGuilds.hidden = (tabId !== 'guilds');
    if (els.tabViewAuctions) els.tabViewAuctions.hidden = (tabId !== 'auctions');
    if (els.tabViewGiftCodes) els.tabViewGiftCodes.hidden = (tabId !== 'giftcodes');
    if (els.tabViewMarket) els.tabViewMarket.hidden = (tabId !== 'market');

    if (tabId === 'audit') {
      // Entering the tab starts on the newest page; a language reload of the open tab keeps its page.
      if (previousTab !== 'audit') state.auditPage = 1;
      loadAuditLog();
    } else if (tabId === 'economy') {
      loadEconomy();
    } else if (tabId === 'rankings') {
      loadRankings();
    } else if (tabId === 'guilds') {
      loadGuilds();
    } else if (tabId === 'auctions') {
      loadAuctions();
    } else if (tabId === 'giftcodes') {
      loadGiftCodes();
    } else if (tabId === 'market') {
      loadMarket();
    } else if (tabId === 'dashboard') {
      loadStats();
      loadServerMetrics();
      loadOnlinePlayers();
    } else if (tabId === 'accounts') {
      loadAccounts();
    }
  }

  function setupAccountScreenListeners() {
    globalThis.addEventListener('hashchange', handleRouteChange);
    document.addEventListener('keydown', handleAccountEscape);
    globalThis.addEventListener('beforeunload', function (e) {
      if (!accountNotesDirty()) return;
      e.preventDefault();
      e.returnValue = '';
    });

    var tablist = document.querySelector('.account-tabs');
    if (tablist) {
      tablist.addEventListener('keydown', handleAccountTabKeydown);
      tablist.addEventListener('click', function (e) {
        var tabButton = e.target.closest('[role="tab"]');
        if (tabButton) setAccountTab(tabButton.getAttribute('data-account-tab'));
      });
    }

    if (els.accountScreen) {
      // Retry buttons rendered by the error states (account load, vault load).
      els.accountScreen.addEventListener('click', function (e) {
        var retry = e.target.closest('[data-retry]');
        if (!retry) return;
        if (retry.getAttribute('data-retry') === 'vault') {
          loadAccountVault(state.vault.requestedPage || 1);
        } else if (state.accountScreen.open) {
          loadAccountScreen(state.accountScreen.name, false);
        }
      });
    }

    if (els.accountNotes) els.accountNotes.addEventListener('input', handleNotesInput);
    if (els.accountSaveNotes) els.accountSaveNotes.addEventListener('click', handleSaveNotes);

    if (els.accountVault) {
      els.accountVault.addEventListener('click', function (e) {
        var target = e.target.closest('button.btn-vault-page');
        if (!target || target.disabled) return;
        goToVaultPage(parseInt(target.getAttribute('data-page'), 10) || 1);
      });
    }

    if (els.accountCharacters) {
      els.accountCharacters.addEventListener('click', function (e) {
        var target = e.target.closest('button');
        if (!target) return;
        var roleId = target.getAttribute('data-role-id');
        if (!roleId) return;

        if (target.classList.contains('btn-view-inventory')) {
          toggleCharacterInventory(target);
        } else if (target.classList.contains('btn-view-mail')) {
          var card = target.closest('.char-card-detail');
          if (!card) return;
          if (card.getAttribute('data-panel') === 'mail') {
            setCharacterPanel(card, null);
            return;
          }
          setCharacterPanel(card, 'mail');
          loadCharacterMail(roleId, 1);
        } else if (target.classList.contains('btn-mail-page')) {
          loadCharacterMail(roleId, parseInt(target.getAttribute('data-page'), 10) || 1);
        } else if (target.classList.contains('btn-delete-character')) {
          handleDeleteCharacter(target);
        }
      });
    }

    // The confirmation and form modals stay modals; they just start from the screen's buttons now.
    var screenName = function () {
      return state.accountScreen.data ? state.accountScreen.data.name : state.accountScreen.name;
    };
    if (els.accountBtnPassword) els.accountBtnPassword.addEventListener('click', function () { showChangePassword(screenName()); });
    if (els.accountBtnBan) els.accountBtnBan.addEventListener('click', function () { showBanAccount(screenName()); });
    if (els.accountBtnUnban) els.accountBtnUnban.addEventListener('click', function () { handleUnbanAccount(screenName(), els.accountBtnUnban); });
    if (els.accountBtnDelete) els.accountBtnDelete.addEventListener('click', function () { showDeleteAccount(screenName()); });
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    if (els.loginForm) {
      els.loginForm.addEventListener('submit', handleLogin);
      els.loginForm.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          if (e.repeat || isLoginSubmitting || loginLockoutTimer) {
            e.preventDefault();
            return false;
          }
        }
      });
    }
    if (els.btnLogout) els.btnLogout.addEventListener('click', handleLogout);

    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.addEventListener('click', handleLangClick);
    });

    document.querySelectorAll('.tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tab = this.getAttribute('data-tab');
        if (!tab) return;
        // The Accounts tab stays highlighted while an account is open; clicking it goes back to the list.
        if (tab === 'accounts' && isAccountScreenOpen()) {
          goToAccountList();
          return;
        }
        if (tab !== 'accounts' && !confirmDiscardNotes()) return;
        switchTab(tab);
      });
    });

    var searchTimeout = null;
    if (els.searchInput) {
      els.searchInput.addEventListener('input', function () {
        clearTimeout(searchTimeout);
        state.searchQuery = this.value.trim().toLowerCase();
        resetAccountsPage();
        searchTimeout = setTimeout(loadAccounts, 250);
      });
    }

    if (els.statusSelect) {
      els.statusSelect.addEventListener('change', function () {
        state.statusFilter = this.value;
        resetAccountsPage();
        loadAccounts();
      });
    }

    if (els.sortSelect) {
      els.sortSelect.addEventListener('change', function () {
        state.sortBy = this.value;
        resetAccountsPage();
        loadAccounts();
      });
    }

    if (els.pagerPrev) {
      els.pagerPrev.addEventListener('click', function () {
        goToAccountsPage(state.accountsPage - 1);
      });
    }

    if (els.pagerNext) {
      els.pagerNext.addEventListener('click', function () {
        goToAccountsPage(state.accountsPage + 1);
      });
    }

    if (els.rankingTypeSelect) {
      els.rankingTypeSelect.addEventListener('change', function () {
        state.rankingType = this.value;
        state.rankingPage = 1;
        loadRankings();
      });
    }

    if (els.rankingPrev) {
      els.rankingPrev.addEventListener('click', function () {
        if (state.rankingPage > 1) {
          state.rankingPage -= 1;
          loadRankings();
        }
      });
    }

    if (els.rankingNext) {
      els.rankingNext.addEventListener('click', function () {
        state.rankingPage += 1;
        loadRankings();
      });
    }

    var guildSearchTimeout = null;
    if (els.guildSearchInput) {
      els.guildSearchInput.addEventListener('input', function () {
        clearTimeout(guildSearchTimeout);
        state.guildQuery = this.value.trim().toLowerCase();
        state.guildsPage = 1;
        guildSearchTimeout = setTimeout(loadGuilds, 250);
      });
    }

    if (els.auditPagerPrev) {
      els.auditPagerPrev.addEventListener('click', function () {
        goToAuditPage(state.auditPage - 1);
      });
    }

    if (els.auditPagerNext) {
      els.auditPagerNext.addEventListener('click', function () {
        goToAuditPage(state.auditPage + 1);
      });
    }

    if (els.guildsPagerPrev) {
      els.guildsPagerPrev.addEventListener('click', function () {
        goToGuildsPage(state.guildsPage - 1);
      });
    }

    if (els.guildsPagerNext) {
      els.guildsPagerNext.addEventListener('click', function () {
        goToGuildsPage(state.guildsPage + 1);
      });
    }

    if (els.guildsTbody) {
      els.guildsTbody.addEventListener('click', function (e) {
        var target = e.target.closest('button.btn-view-guild');
        if (!target) return;
        var guildId = target.getAttribute('data-guild');
        if (guildId) showGuildDetail(guildId);
      });
    }

    if (els.auctionViewSelect) {
      els.auctionViewSelect.addEventListener('change', function () {
        state.auctionView = this.value;
        state.auctionsPage = 1;
        loadAuctions();
      });
    }

    if (els.auctionsPagerPrev) {
      els.auctionsPagerPrev.addEventListener('click', function () {
        goToAuctionsPage(state.auctionsPage - 1);
      });
    }

    if (els.auctionsPagerNext) {
      els.auctionsPagerNext.addEventListener('click', function () {
        goToAuctionsPage(state.auctionsPage + 1);
      });
    }

    var btnGiftCodesRefresh = document.getElementById('btn-giftcodes-refresh');
    if (btnGiftCodesRefresh) {
      btnGiftCodesRefresh.addEventListener('click', function () {
        loadGiftCodes();
        showToast(t('Data refreshed'), 'info');
      });
    }
    if (els.btnNewGiftCode) els.btnNewGiftCode.addEventListener('click', showCreateGiftCode);
    var btnGiftCodeAddItem = document.getElementById('btn-giftcode-add-item');
    if (btnGiftCodeAddItem) btnGiftCodeAddItem.addEventListener('click', addGiftCodeItemRow);
    if (els.giftCodeItems) {
      els.giftCodeItems.addEventListener('click', function (e) {
        var target = e.target.closest('button.btn-giftcode-remove-item');
        if (!target) return;
        var row = target.closest('.giftcode-item-row');
        if (row && els.giftCodeItems.querySelectorAll('.giftcode-item-row').length > 1) {
          row.remove();
          updateGiftCodeRemoveButtons();
        }
      });
    }
    var formGiftCode = document.getElementById('form-giftcode');
    if (formGiftCode) formGiftCode.addEventListener('submit', handleCreateGiftCode);
    if (els.giftCodesTbody) {
      els.giftCodesTbody.addEventListener('click', function (e) {
        var target = e.target.closest('button.btn-giftcode-toggle');
        if (!target) return;
        var code = target.getAttribute('data-code');
        var action = target.getAttribute('data-action');
        if (!code || !action) return;
        target.disabled = true;
        handleGiftCodeToggle(code, action);
      });
    }

    if (els.marketForm) els.marketForm.addEventListener('submit', applyMarketFilters);
    if (els.marketStatusSelect) els.marketStatusSelect.addEventListener('change', applyMarketFilters);
    var btnMarketClear = document.getElementById('market-clear');
    if (btnMarketClear) btnMarketClear.addEventListener('click', resetMarketFilters);
    if (els.marketPagerPrev) {
      els.marketPagerPrev.addEventListener('click', function () {
        goToMarketPage(state.market.page - 1);
      });
    }
    if (els.marketPagerNext) {
      els.marketPagerNext.addEventListener('click', function () {
        goToMarketPage(state.market.page + 1);
      });
    }

    var btnNewAccount = document.getElementById('btn-new-account');
    if (btnNewAccount) btnNewAccount.addEventListener('click', showCreateAccount);

    var btnNewAccountDash = document.getElementById('btn-new-account-dash');
    if (btnNewAccountDash) btnNewAccountDash.addEventListener('click', showCreateAccount);

    var btnBrowseAccounts = document.getElementById('btn-browse-accounts');
    if (btnBrowseAccounts) {
      btnBrowseAccounts.addEventListener('click', function () {
        var accountsTab = document.querySelector('.tab-btn[data-tab="accounts"]');
        if (accountsTab) accountsTab.click();
      });
    }

    if (els.mainContent) {
      // Retry buttons rendered by the table error rows.
      els.mainContent.addEventListener('click', function (e) {
        var retry = e.target.closest('[data-retry]');
        if (!retry) return;
        var key = retry.getAttribute('data-retry');
        if (Object.prototype.hasOwnProperty.call(RETRY_LOADERS, key)) RETRY_LOADERS[key]();
      });
    }

    var btnRefresh = document.getElementById('btn-refresh');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', function () {
        loadStats();
        loadAccounts();
        showToast(t('Data refreshed'), 'info');
      });
    }

    if (els.accountsTbody) {
      els.accountsTbody.addEventListener('click', function (e) {
        var target = e.target.closest('button');
        if (!target) return;
        var acc = target.getAttribute('data-account');
        if (!acc) return;

        if (target.classList.contains('btn-view-detail')) {
          navigateToAccount(acc);
        } else if (target.classList.contains('btn-change-pw')) {
          showChangePassword(acc);
        } else if (target.classList.contains('btn-ban')) {
          showBanAccount(acc);
        } else if (target.classList.contains('btn-unban')) {
          handleUnbanAccount(acc, target);
        } else if (target.classList.contains('btn-delete')) {
          showDeleteAccount(acc);
        }
      });
    }

    document.querySelectorAll('[data-close-modal]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var modal = this.closest('.modal-backdrop');
        if (modal) closeModal(modal);
      });
    });
    // Registered before the account screen's own Escape rule: a press that closes a modal is handled once.
    document.addEventListener('keydown', handleModalKeydown);
    initSidebar();
    // 'error' does not bubble, so a failed icon is caught while the event travels down.
    document.addEventListener('error', handleItemIconError, true);

    var formPw = document.getElementById('form-password');
    if (formPw) formPw.addEventListener('submit', handleUpdatePassword);

    var formCreate = document.getElementById('form-create');
    if (formCreate) formCreate.addEventListener('submit', handleCreateAccount);

    var formBan = document.getElementById('form-ban');
    if (formBan) formBan.addEventListener('submit', handleBanAccount);

    if (els.formConfirm) els.formConfirm.addEventListener('submit', handleConfirmSubmit);
    if (els.confirmTypedInput) els.confirmTypedInput.addEventListener('input', handleConfirmTyping);

    var formDel = document.getElementById('form-delete');
    if (formDel) formDel.addEventListener('submit', handleDeleteAccount);

    setupAccountScreenListeners();

    if (els.economyForm) els.economyForm.addEventListener('submit', applyEconomyFilters);
    var btnEconomyReset = document.getElementById('economy-reset');
    if (btnEconomyReset) btnEconomyReset.addEventListener('click', resetEconomyFilters);
    if (els.economyPrev) els.economyPrev.addEventListener('click', function () { changeEconomyPage(-1); });
    if (els.economyNext) els.economyNext.addEventListener('click', function () { changeEconomyPage(1); });

    buildGmPanel();
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', function () {
    var storedLang = readStoredLang();
    if (storedLang) {
      i18n.lang = storedLang;
      i18n.stored = true;
    }
    setupEventListeners();
    applyI18n(document);
    updateLangButtons();
    loadLocale();
    loadBranding();
    checkSession();
  });

})();
