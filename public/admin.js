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
    guildsPage: 1,
    guildsPages: 1,
    guildsTotal: 0,
    auctionView: 'lots',
    auctionsPage: 1,
    auctionsPages: 1,
    auctionsTotal: 0
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

    // Modals
    modalDetail: document.getElementById('modal-detail'),
    modalPassword: document.getElementById('modal-password'),
    modalCreate: document.getElementById('modal-create'),
    modalBan: document.getElementById('modal-ban'),
    modalDelete: document.getElementById('modal-delete'),

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

  // --- Toast Notifications ---
  function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.innerHTML = '<span>' + escapeHtml(message) + '</span>';
    els.toasts.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s';
      setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
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

  // Currencies other than Zeny have no verified name in RO3Emu, so they are listed by item id.
  function formatOtherCurrencies(others) {
    if (!others || !others.length) return '—';
    return others.map(function (c) {
      return '#' + escapeHtml(String(c.id)) + ': ' + formatNumber(c.amount);
    }).join(', ');
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
      el.textContent = state.branding.logo_text;
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
  }

  function setUnauthenticated() {
    state.authenticated = false;
    state.adminUser = null;
    if (els.loginScreen) els.loginScreen.hidden = false;
    if (els.appHeader) els.appHeader.hidden = true;
    if (els.subnav) els.subnav.hidden = true;
    if (els.mainContent) els.mainContent.hidden = true;
    if (els.loginError) els.loginError.hidden = true;
  }

  var loginLockoutTimer = null;

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

  function handleLogin(e) {
    e.preventDefault();
    if (loginLockoutTimer) return;
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

    els.loginSubmit.disabled = true;
    els.loginSubmit.textContent = t('Verifying...');
    if (els.loginError) els.loginError.hidden = true;

    apiFetch('/api/admin/login', {
      method: 'POST',
      body: { username: user, password: pass }
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
    if (els.statBanned) els.statBanned.textContent = formatNumber(s.counts.banned);
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
      els.onlineTbody.innerHTML = '<tr><td colspan="' + cols + '" style="text-align: center; color: var(--text-muted); padding: 24px;">' + escapeHtml(t('No players connected.')) + '</td></tr>';
      return;
    }

    els.onlineTbody.innerHTML = players.map(function (p) {
      var pos = (isNum(p.x) && isNum(p.z)) ? String(p.x) + ', ' + String(p.z) : '—';
      var row = '<tr>' +
        '<td>' + escapeHtml(p.account) + '</td>' +
        '<td>' + (p.character ? escapeHtml(p.character) : '<span style="color: var(--text-muted);">' + escapeHtml(t('No character')) + '</span>') + '</td>' +
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

    apiFetch('/api/admin/accounts?' + params.toString())
      .then(function (data) {
        var pages = data.pages || 1;
        // The current page can disappear (e.g. after deleting its last account): jump to the last one.
        if (state.accountsPage > pages) {
          state.accountsPage = pages;
          loadAccounts();
          return;
        }
        state.accounts = data.accounts || [];
        state.accountsPages = pages;
        state.accountsTotal = data.total || 0;
        renderAccountsTable();
        renderAccountsPager();
      })
      .catch(function (err) {
        showToast(t('Error loading accounts: {message}', { message: err.message }), 'error');
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
      els.accountsTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 32px;">' + escapeHtml(t('No accounts found matching the search criteria.')) + '</td></tr>';
      return;
    }

    var html = '';
    list.forEach(function (acc) {
      var badgeHtml = '';
      if (acc.is_admin) {
        badgeHtml = '<span class="badge badge-admin">★ GM Admin</span>';
      } else if (acc.is_banned) {
        badgeHtml = '<span class="badge badge-banned" title="' + escapeHtml(acc.ban_reason) + '">' + escapeHtml(t('✕ Banned')) + '</span>';
      } else {
        badgeHtml = '<span class="badge badge-active">' + escapeHtml(t('✓ Active')) + '</span>';
      }

      var charsHtml = '';
      if (acc.characters && acc.characters.length > 0) {
        charsHtml = '<div class="char-chips-container">';
        acc.characters.forEach(function (c) {
          charsHtml += '<span class="char-chip">' +
            '<strong>' + escapeHtml(c.name) + '</strong> ' +
            '<span class="char-class">' + escapeHtml(c.career_name) + '</span> ' +
            '<span class="char-lv">Lv.' + c.level + '/' + c.job_level + '</span>' +
            '</span>';
        });
        charsHtml += '</div>';
      } else {
        charsHtml = '<span style="color: var(--text-dim); font-size: 11px;">' + escapeHtml(t('No characters')) + '</span>';
      }

      html += '<tr data-account="' + escapeHtml(acc.name) + '">' +
        '<td><strong style="color: #fff; font-size: 14px;">' + escapeHtml(acc.name) + '</strong></td>' +
        '<td>' + badgeHtml + '</td>' +
        '<td>' + charsHtml + '</td>' +
        '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(acc.created_utc) + '</td>' +
        '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(acc.last_login) + '</td>' +
        '<td>' +
          '<div style="display: flex; gap: 6px;">' +
            '<button class="btn btn-secondary btn-sm btn-view-detail" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('View details and characters')) + '">' + escapeHtml(t('Record')) + '</button>' +
            '<button class="btn btn-secondary btn-sm btn-change-pw" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Change password')) + '">' + escapeHtml(t('Pass')) + '</button>' +
            (acc.is_admin ? '' : (acc.is_banned ?
              '<button class="btn btn-secondary btn-sm btn-unban" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Remove suspension')) + '">' + escapeHtml(t('Unban')) + '</button>' :
              '<button class="btn btn-danger btn-sm btn-ban" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Suspend account')) + '">' + escapeHtml(t('Ban')) + '</button>'
            )) +
            (acc.is_admin ? '' : '<button class="btn btn-danger btn-sm btn-delete" data-account="' + escapeHtml(acc.name) + '" title="' + escapeHtml(t('Delete account')) + '">✕</button>') +
          '</div>' +
        '</td>' +
      '</tr>';
    });

    els.accountsTbody.innerHTML = html;
  }

  // --- Modals ---
  function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.hidden = false;
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.hidden = true;
  }

  function showAccountDetail(name) {
    apiFetch('/api/admin/accounts/' + encodeURIComponent(name))
      .then(function (acc) {
        state.selectedAccount = acc;
        document.getElementById('detail-acc-name').textContent = acc.name;
        document.getElementById('detail-acc-created').textContent = formatDate(acc.created_utc);
        document.getElementById('detail-acc-status').innerHTML = acc.is_banned ?
          '<span class="badge badge-banned">' + escapeHtml(t('Banned ({reason})', { reason: acc.ban_reason })) + '</span>' :
          '<span class="badge badge-active">' + escapeHtml(t('Active')) + '</span>';
        document.getElementById('detail-acc-tokens').textContent = t('{count} sessions', { count: acc.tokens_count });

        var notesField = document.getElementById('detail-acc-notes');
        if (notesField) notesField.value = acc.notes || '';
        resetGmPanel();

        var charsContainer = document.getElementById('detail-chars-list');
        if (charsContainer) {
          if (!acc.characters || !acc.characters.length) {
            charsContainer.innerHTML = '<p style="color: var(--text-muted); padding: 12px;">' + escapeHtml(t('This account has no characters yet.')) + '</p>';
          } else {
            var charsHtml = '';
            acc.characters.forEach(function (c) {
              charsHtml += '<div class="char-card-detail">' +
                '<div class="char-card-header">' +
                  '<div>' +
                    '<span class="char-title">' + escapeHtml(c.name) + '</span> ' +
                    '<span class="badge badge-admin" style="margin-left: 6px;">' + escapeHtml(c.career_name) + '</span>' +
                  '</div>' +
                  '<div style="font-size: 12px; color: var(--gold); font-weight: 700;">' +
                    escapeHtml(t('Level {level} / Job {job}', { level: c.level, job: c.job_level })) +
                  '</div>' +
                '</div>' +
                '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 8px;">' +
                  '<div><strong>Zeny:</strong> <span style="color: var(--success);">' + formatNumber(c.currency.zeny) + ' Z</span></div>' +
                  '<div><strong>' + escapeHtml(t('Other currencies:')) + '</strong> <span style="color: var(--info);">' + formatOtherCurrencies(c.currency.others) + '</span></div>' +
                  '<div><strong>' + escapeHtml(t('Location:')) + '</strong> ' + escapeHtml(c.scene_name) + ' (' + c.pos.x + ', ' + c.pos.z + ')</div>' +
                  '<div><strong>' + escapeHtml(t('Last login:')) + '</strong> ' + formatDate(c.last_login) + '</div>' +
                '</div>' +
                '<div class="stats-grid-mini">' +
                  '<div><div class="stat-box-lbl">STR</div><div class="stat-box-val">' + c.stats.str + '</div></div>' +
                  '<div><div class="stat-box-lbl">AGI</div><div class="stat-box-val">' + c.stats.agi + '</div></div>' +
                  '<div><div class="stat-box-lbl">VIT</div><div class="stat-box-val">' + c.stats.vit + '</div></div>' +
                  '<div><div class="stat-box-lbl">INT</div><div class="stat-box-val">' + c.stats.int + '</div></div>' +
                  '<div><div class="stat-box-lbl">DEX</div><div class="stat-box-val">' + c.stats.dex + '</div></div>' +
                  '<div><div class="stat-box-lbl">LUK</div><div class="stat-box-val">' + c.stats.luk + '</div></div>' +
                '</div>' +
                '<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">' +
                  '<button class="btn btn-secondary btn-sm btn-view-inventory" data-role-id="' + escapeHtml(String(c.id)) + '" title="' + escapeHtml(t('View character items')) + '">' + escapeHtml(t('View inventory')) + '</button>' +
                  '<button type="button" class="btn btn-secondary btn-sm btn-view-mail" data-role-id="' + escapeHtml(String(c.id)) + '" title="' + escapeHtml(t('View character mail (read-only)')) + '">' + escapeHtml(t('View mail')) + '</button>' +
                '</div>' +
                '<div class="char-inventory" hidden></div>' +
                '<div class="char-mail-panel" id="char-mail-' + escapeHtml(String(c.id)) + '" hidden></div>' +
              '</div>';
            });
            charsContainer.innerHTML = charsHtml;
          }
        }

        openModal(els.modalDetail);
      })
      .catch(function (err) {
        showToast(t('Error loading record: {message}', { message: err.message }), 'error');
      });
  }

  // --- Character Mail (read-only) ---
  var MAIL_PAGE_SIZE = 10;

  function renderMailAttachments(m) {
    var parts = [];
    (m.attachments || []).forEach(function (a) {
      parts.push(escapeHtml(t('Item {entry} x{count}', { entry: a.entry, count: a.count })));
    });
    (m.items || []).forEach(function (it) {
      parts.push(escapeHtml(t('Item {entry} x{count}', { entry: it.entry, count: it.stack })));
    });
    (m.currency || []).forEach(function (cur) {
      parts.push(escapeHtml(t('Currency {entry}: {amount}', { entry: cur.entry, amount: formatNumber(cur.amount) })));
    });
    return parts.length ? parts.join(', ') : escapeHtml(t('No attachments'));
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
        panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(t('Error loading mail: {message}', { message: err.message })) + '</p>';
      });
  }

  // --- Character Inventory (read-only) ---
  function toggleCharacterInventory(btn) {
    var card = btn.closest('.char-card-detail');
    var container = card ? card.querySelector('.char-inventory') : null;
    var roleId = btn.getAttribute('data-role-id');
    if (!container || !roleId) return;

    if (!container.hidden) {
      container.hidden = true;
      btn.textContent = t('View inventory');
      return;
    }

    btn.disabled = true;
    btn.textContent = t('Loading...');
    apiFetch('/api/admin/characters/' + encodeURIComponent(roleId) + '/items')
      .then(function (data) {
        container.innerHTML = renderInventory(data);
        container.hidden = false;
        btn.textContent = t('Hide inventory');
      })
      .catch(function (err) {
        btn.textContent = t('View inventory');
        showToast(t('Error loading inventory: {message}', { message: err.message }), 'error');
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function renderInventory(data) {
    var boxStyle = 'margin-top: 8px; padding: 10px; background: #0c1018; border: 1px solid var(--border-color); border-radius: var(--radius-sm); font-size: 12px;';
    if (!data || data.available === false) {
      return '<div style="' + boxStyle + ' color: var(--text-muted);">' + escapeHtml(t('The inventory is not available in this database.')) + '</div>';
    }
    var items = data.items || [];
    if (!items.length) {
      return '<div style="' + boxStyle + ' color: var(--text-muted);">' + escapeHtml(t('This character has no items.')) + '</div>';
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

    var html = '<div style="' + boxStyle + '">' +
      '<div style="color: var(--text-muted); margin-bottom: 8px;">' + escapeHtml(t('Total items:')) + ' <strong style="color: #fff;">' + formatNumber(data.total) + '</strong></div>';
    groups.forEach(function (g) {
      var label = g.packName || t('Bag {pack}', { pack: g.pack });
      html += '<div style="margin-bottom: 10px;">' +
        '<span class="badge badge-admin">' + escapeHtml(label) + ' (' + g.items.length + ')</span>' +
        '<table class="data-table" style="margin-top: 6px;">' +
          '<thead><tr><th>' + escapeHtml(t('Inventory item')) + '</th><th>' + escapeHtml(t('Quantity')) + '</th><th>' + escapeHtml(t('Status')) + '</th></tr></thead><tbody>';
      g.items.forEach(function (item) {
        var name = item.name ? escapeHtml(item.name) : '#' + escapeHtml(String(item.entry));
        var flags = [];
        if (item.equipped) flags.push('<span class="badge badge-active">' + escapeHtml(t('Equipped')) + '</span>');
        if (item.locked) flags.push('<span class="badge badge-banned">' + escapeHtml(t('Locked')) + '</span>');
        if (item.bind_type) flags.push('<span class="badge badge-admin">' + escapeHtml(t('Bound')) + '</span>');
        html += '<tr>' +
          '<td><strong style="color: #fff;">' + name + '</strong> <span style="color: var(--text-dim);">#' + escapeHtml(String(item.entry)) + '</span></td>' +
          '<td>' + formatNumber(item.stack) + '</td>' +
          '<td>' + (flags.length ? flags.join(' ') : '—') + '</td>' +
        '</tr>';
      });
      html += '</tbody></table></div>';
    });
    html += '</div>';
    return html;
  }

  function handleSaveNotes() {
    if (!state.selectedAccount) return;
    var notes = (document.getElementById('detail-acc-notes').value || '').trim();
    apiFetch('/api/admin/accounts/save-notes', {
      method: 'POST',
      body: { username: state.selectedAccount.name, notes: notes }
    })
      .then(function () {
        showToast(t('Notes updated successfully'), 'success');
      })
      .catch(function (err) {
        showToast(t('Error saving notes: {message}', { message: err.message }), 'error');
      });
  }

  // --- GM Tools (POST /api/admin/gm, relayed to RO3Emu's loopback GM endpoint) ---
  function buildGmPanel() {
    var body = document.querySelector('#modal-detail .modal-body');
    if (!body || document.getElementById('gm-tools')) return;
    var panel = document.createElement('div');
    panel.id = 'gm-tools';
    panel.className = 'gm-tools';
    panel.innerHTML =
      '<h4 class="gm-tools-title" data-i18n="GM Tools">GM Tools</h4>' +
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
      '<p id="gm-tools-result" class="gm-tools-result" aria-live="polite"></p>';
    applyI18n(panel);
    body.appendChild(panel);

    document.getElementById('gm-warp-form').addEventListener('submit', handleGmWarp);
    document.getElementById('gm-unstuck').addEventListener('click', function () {
      sendGmCommand('unstuck', {});
    });
  }

  function resetGmPanel() {
    ['gm-warp-scene', 'gm-warp-x', 'gm-warp-z'].forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.value = '';
    });
    setGmResult('', '');
  }

  function setGmResult(message, type) {
    var result = document.getElementById('gm-tools-result');
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

  function sendGmCommand(command, args) {
    if (!state.selectedAccount) return;
    setGmResult(t('Sending…'), '');
    apiFetch('/api/admin/gm', {
      method: 'POST',
      body: { account: state.selectedAccount.name, command: command, args: args }
    })
      .then(function (data) {
        setGmResult(data.sent + ': ' + data.message, 'success');
        showToast(t('GM command sent'), 'success');
      })
      .catch(function (err) {
        setGmResult(err.message, 'error');
        showToast(t('GM error: {message}', { message: err.message }), 'error');
      });
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
    if (!state.selectedAccount) return;
    var newPass = document.getElementById('pw-new-pass').value || '';
    if (!newPass || newPass.length < 6) {
      showToast(t('The new password must be at least 6 characters.'), 'error');
      return;
    }

    apiFetch('/api/admin/accounts/update-password', {
      method: 'POST',
      body: { username: state.selectedAccount.name, new_password: newPass }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        closeModal(els.modalPassword);
      })
      .catch(function (err) {
        showToast(t('Error: {message}', { message: err.message }), 'error');
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
      });
  }

  function showBanAccount(name) {
    state.selectedAccount = { name: name };
    setModalIntro('ban-intro', t('Suspending account {account} will mark it as suspended in the panel and revoke its active sessions. RO3Emu does not check this suspension at login yet, so the player may be able to log in again.'), name);
    document.getElementById('ban-reason').value = '';
    openModal(els.modalBan);
  }

  function handleBanAccount(e) {
    e.preventDefault();
    if (!state.selectedAccount) return;
    var reason = (document.getElementById('ban-reason').value || '').trim() || t('Administrative suspension');

    apiFetch('/api/admin/accounts/ban', {
      method: 'POST',
      body: { username: state.selectedAccount.name, reason: reason }
    })
      .then(function (data) {
        showToast(data.message, data.enforced === false ? 'info' : 'success');
        closeModal(els.modalBan);
        loadAccounts();
        loadStats();
      })
      .catch(function (err) {
        showToast(t('Error suspending account: {message}', { message: err.message }), 'error');
      });
  }

  function handleUnbanAccount(name) {
    if (!confirm(t('Do you want to reset and remove the suspension of account "{name}"?', { name: name }))) return;
    apiFetch('/api/admin/accounts/unban', {
      method: 'POST',
      body: { username: name }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        loadAccounts();
        loadStats();
      })
      .catch(function (err) {
        showToast(t('Error removing suspension: {message}', { message: err.message }), 'error');
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
    if (!state.selectedAccount) return;
    var typedName = (document.getElementById('del-confirm-name').value || '').trim();
    if (typedName !== state.selectedAccount.name) {
      showToast(t('You must type the account name exactly to confirm.'), 'error');
      return;
    }

    apiFetch('/api/admin/accounts/delete', {
      method: 'POST',
      body: { username: state.selectedAccount.name }
    })
      .then(function (data) {
        showToast(data.message, 'success');
        closeModal(els.modalDelete);
        loadAccounts();
        loadStats();
      })
      .catch(function (err) {
        showToast(t('Error deleting account: {message}', { message: err.message }), 'error');
      });
  }

  function loadAuditLog() {
    apiFetch('/api/admin/audit-log')
      .then(function (data) {
        var logs = data.logs || [];
        if (!els.auditTbody) return;
        if (!logs.length) {
          els.auditTbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">' + escapeHtml(t('No audit records yet.')) + '</td></tr>';
          return;
        }
        var html = '';
        logs.forEach(function (l) {
          var targetRaw = l.target || '';
          var targetDisplay = targetRaw;
          var MAX_TARGET_CHARS = 20;
          if (targetDisplay.length > MAX_TARGET_CHARS) {
            targetDisplay = targetDisplay.substring(0, MAX_TARGET_CHARS) + '…';
          }
          var targetCell = targetRaw
            ? '<strong class="audit-target" title="' + escapeHtml(targetRaw) + '" style="color: #fff;">' + escapeHtml(targetDisplay) + '</strong>'
            : '—';

          html += '<tr>' +
            '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(l.created_utc) + '</td>' +
            '<td><strong style="color: var(--gold);">' + escapeHtml(l.admin_user) + '</strong></td>' +
            '<td><span class="badge badge-admin">' + escapeHtml(l.action) + '</span></td>' +
            '<td>' + targetCell + '</td>' +
            '<td style="color: var(--text-muted);">' + escapeHtml(l.details) + '</td>' +
          '</tr>';
        });
        els.auditTbody.innerHTML = html;
      })
      .catch(function (err) {
        showToast(t('Error loading records: {message}', { message: err.message }), 'error');
      });
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

    apiFetch('/api/admin/economy?' + params.toString())
      .then(function (data) {
        eco.page = data.page || 1;
        eco.pages = data.pages || 1;
        if (els.economyUnavailable) els.economyUnavailable.hidden = data.available !== false;
        renderEconomyTable(data.entries || [], data.available !== false);
        renderEconomyPager(data.total || 0);
      })
      .catch(function (err) {
        showToast(t('Error loading economy: {message}', { message: err.message }), 'error');
      });
  }

  function describeEconomyOwner(e) {
    if (e.owner_name) return escapeHtml(e.owner_name);
    return escapeHtml(e.owner_kind_label) + ' ' + escapeHtml(e.owner_id);
  }

  function renderEconomyTable(entries, available) {
    if (!els.economyTbody) return;
    if (!entries.length) {
      var msg = escapeHtml(available ? t('No movements for the selected filters.') : t('Economy log not available in this database.'));
      els.economyTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">' + msg + '</td></tr>';
      return;
    }
    var html = '';
    entries.forEach(function (e) {
      var deltaClass = e.delta < 0 ? 'economy-delta-neg' : 'economy-delta-pos';
      var deltaText = (e.delta > 0 ? '+' : '') + formatNumber(e.delta);
      var actorRole = e.actor_role_name ? escapeHtml(e.actor_role_name) : ('#' + escapeHtml(String(e.actor_role)));
      html += '<tr>' +
        '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(e.recorded_utc) + '</td>' +
        '<td><span class="badge badge-admin">' + escapeHtml(e.command_kind) + '</span>' +
          '<div class="economy-sub" title="' + escapeHtml(e.operation_id) + '">' + escapeHtml(e.operation_id) + '</div></td>' +
        '<td><strong style="color: #fff;">' + escapeHtml(e.actor_account) + '</strong>' +
          '<div class="economy-sub">' + actorRole + '</div></td>' +
        '<td>' + describeEconomyOwner(e) + '</td>' +
        '<td>' + escapeHtml(e.asset_label) + '</td>' +
        '<td class="' + deltaClass + '">' + escapeHtml(deltaText) + '</td>' +
        '<td style="color: var(--text-muted);">' + escapeHtml(String(e.reason_code)) + '</td>' +
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
        '<th style="width: 10%;">#</th>' +
        '<th>' + escapeHtml(t('Clan')) + '</th>' +
        '<th style="width: 22%;">' + escapeHtml(t('Active Members')) + '</th>' +
        '<th style="width: 22%;">' + escapeHtml(t('Total Level')) + '</th>' +
      '</tr>';
      return;
    }
    els.rankingsThead.innerHTML = '<tr>' +
      '<th style="width: 8%;">#</th>' +
      '<th>' + escapeHtml(t('Character')) + '</th>' +
      '<th style="width: 18%;">' + escapeHtml(t('Account')) + '</th>' +
      '<th style="width: 18%;">' + escapeHtml(t('Class')) + '</th>' +
      '<th style="width: 14%;">' + escapeHtml(t('Level / Job')) + '</th>' +
      '<th style="width: 16%;">' + escapeHtml(rankingMetricLabel(type)) + '</th>' +
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
    apiFetch(url)
      .then(function (data) {
        if (!els.rankingsTbody) return;
        var rows = data.rankings || [];
        var colspan = type === 'guilds' ? 4 : 6;
        state.rankingTotal = data.total || 0;
        renderRankingsPager();

        if (data.available === false) {
          els.rankingsTbody.innerHTML = '<tr><td colspan="' + colspan + '" style="text-align: center; color: var(--text-muted); padding: 24px;">' + escapeHtml(t('The database has no clan tables yet.')) + '</td></tr>';
          return;
        }
        if (!rows.length) {
          els.rankingsTbody.innerHTML = '<tr><td colspan="' + colspan + '" style="text-align: center; color: var(--text-muted); padding: 24px;">' + escapeHtml(t('No data for this ranking.')) + '</td></tr>';
          return;
        }

        var html = '';
        rows.forEach(function (r) {
          if (type === 'guilds') {
            html += '<tr>' +
              '<td><strong style="color: var(--gold);">' + r.rank + '</strong></td>' +
              '<td><strong style="color: #fff;">' + escapeHtml(r.name) + '</strong></td>' +
              '<td>' + formatNumber(r.member_count) + '</td>' +
              '<td>' + formatNumber(r.total_level) + '</td>' +
            '</tr>';
            return;
          }
          html += '<tr>' +
            '<td><strong style="color: var(--gold);">' + r.rank + '</strong></td>' +
            '<td><strong style="color: #fff;">' + escapeHtml(r.name) + '</strong></td>' +
            '<td style="color: var(--text-muted);">' + escapeHtml(r.account) + '</td>' +
            '<td>' + escapeHtml(r.career_name) + '</td>' +
            '<td>' + formatNumber(r.level) + ' / ' + formatNumber(r.job_level) + '</td>' +
            '<td><strong>' + formatNumber(r.value) + '</strong></td>' +
          '</tr>';
        });
        els.rankingsTbody.innerHTML = html;
      })
      .catch(function (err) {
        showToast(t('Error loading rankings: {message}', { message: err.message }), 'error');
      });
  }

  // --- Read-only views: Guilds & Auctions ---
  // escapeHtml() returns '' for 0, so numbers go through String() first.
  function cellValue(value) {
    if (value === null || value === undefined) return '—';
    return escapeHtml(String(value));
  }

  function emptyRow(colspan, text) {
    return '<tr><td colspan="' + colspan + '" style="text-align: center; color: var(--text-muted); padding: 32px;">' +
      escapeHtml(text) + '</td></tr>';
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

    apiFetch('/api/admin/guilds?' + params.toString())
      .then(function (data) {
        state.guildsPages = data.pages || 1;
        state.guildsTotal = data.total || 0;
        if (els.guildsUnavailable) els.guildsUnavailable.hidden = data.available !== false;
        renderGuildsTable(data.guilds || []);
        renderPager(els.guildsPager, els.guildsPagerInfo, els.guildsPagerPrev, els.guildsPagerNext,
          state.guildsPage, state.guildsPages, state.guildsTotal, 'guilds');
      })
      .catch(function (err) {
        showToast(t('Error loading guilds: {message}', { message: err.message }), 'error');
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
        '<td style="color: var(--text-muted);">' + cellValue(g.id) + '</td>' +
        '<td><strong style="color: #fff;">' + escapeHtml(g.name) + '</strong></td>' +
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
              '<td><strong style="color: #fff;">' + escapeHtml(m.name) + '</strong></td>' +
              '<td>' + escapeHtml(m.account) + '</td>' +
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

    apiFetch('/api/admin/auctions?' + params.toString())
      .then(function (data) {
        state.auctionsPages = data.pages || 1;
        state.auctionsTotal = data.total || 0;
        if (els.auctionsUnavailable) els.auctionsUnavailable.hidden = data.available !== false;
        renderAuctionsTable(data.view || state.auctionView, data.rows || []);
        renderPager(els.auctionsPager, els.auctionsPagerInfo, els.auctionsPagerPrev, els.auctionsPagerNext,
          state.auctionsPage, state.auctionsPages, state.auctionsTotal, 'records');
      })
      .catch(function (err) {
        showToast(t('Error loading auctions: {message}', { message: err.message }), 'error');
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
        return '<td>' + auctionCell(r[c[0]]) + '</td>';
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
    return items.map(function (item) {
      var label = item.name ? escapeHtml(item.name) : escapeHtml(String(item.entry));
      return label + ' x' + escapeHtml(String(item.count));
    }).join(', ');
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
    apiFetch('/api/admin/gift-codes')
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
        if (els.giftCodesTbody) els.giftCodesTbody.innerHTML = emptyRow(10, t('Error loading gift codes: {message}', { message: err.message }));
        showToast(t('Error loading gift codes: {message}', { message: err.message }), 'error');
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
    if (submit) submit.disabled = true;
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
      .then(function () {
        if (submit) submit.disabled = false;
      });
  }

  // --- Tabs Switching ---
  function switchTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
    });

    if (els.tabViewDashboard) els.tabViewDashboard.hidden = (tabId !== 'dashboard');
    if (els.tabViewAccounts) els.tabViewAccounts.hidden = (tabId !== 'accounts');
    if (els.tabViewAudit) els.tabViewAudit.hidden = (tabId !== 'audit');
    if (els.tabViewEconomy) els.tabViewEconomy.hidden = (tabId !== 'economy');
    if (els.tabViewRankings) els.tabViewRankings.hidden = (tabId !== 'rankings');
    if (els.tabViewGuilds) els.tabViewGuilds.hidden = (tabId !== 'guilds');
    if (els.tabViewAuctions) els.tabViewAuctions.hidden = (tabId !== 'auctions');
    if (els.tabViewGiftCodes) els.tabViewGiftCodes.hidden = (tabId !== 'giftcodes');

    if (tabId === 'audit') {
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
    } else if (tabId === 'dashboard') {
      loadStats();
      loadServerMetrics();
      loadOnlinePlayers();
    } else if (tabId === 'accounts') {
      loadAccounts();
    }
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    if (els.loginForm) els.loginForm.addEventListener('submit', handleLogin);
    if (els.btnLogout) els.btnLogout.addEventListener('click', handleLogout);

    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.addEventListener('click', handleLangClick);
    });

    document.querySelectorAll('.tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tab = this.getAttribute('data-tab');
        if (tab) switchTab(tab);
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

    var btnNewAccount = document.getElementById('btn-new-account');
    if (btnNewAccount) btnNewAccount.addEventListener('click', showCreateAccount);

    var btnNewAccountDash = document.getElementById('btn-new-account-dash');
    if (btnNewAccountDash) btnNewAccountDash.addEventListener('click', showCreateAccount);

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
          showAccountDetail(acc);
        } else if (target.classList.contains('btn-change-pw')) {
          showChangePassword(acc);
        } else if (target.classList.contains('btn-ban')) {
          showBanAccount(acc);
        } else if (target.classList.contains('btn-unban')) {
          handleUnbanAccount(acc);
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

    var formPw = document.getElementById('form-password');
    if (formPw) formPw.addEventListener('submit', handleUpdatePassword);

    var formCreate = document.getElementById('form-create');
    if (formCreate) formCreate.addEventListener('submit', handleCreateAccount);

    var formBan = document.getElementById('form-ban');
    if (formBan) formBan.addEventListener('submit', handleBanAccount);

    var formDel = document.getElementById('form-delete');
    if (formDel) formDel.addEventListener('submit', handleDeleteAccount);

    var detailCharsList = document.getElementById('detail-chars-list');
    if (detailCharsList) {
      detailCharsList.addEventListener('click', function (e) {
        var btn = e.target.closest('.btn-view-inventory');
        if (btn) toggleCharacterInventory(btn);
      });
    }

    var btnSaveNotes = document.getElementById('btn-save-notes');
    if (btnSaveNotes) btnSaveNotes.addEventListener('click', handleSaveNotes);

    var detailChars = document.getElementById('detail-chars-list');
    if (detailChars) {
      detailChars.addEventListener('click', function (e) {
        var target = e.target.closest('button');
        if (!target) return;
        var roleId = target.getAttribute('data-role-id');
        if (!roleId) return;

        if (target.classList.contains('btn-view-mail')) {
          var panel = document.getElementById('char-mail-' + roleId);
          if (panel && !panel.hidden) {
            panel.hidden = true;
            return;
          }
          loadCharacterMail(roleId, 1);
        } else if (target.classList.contains('btn-mail-page')) {
          loadCharacterMail(roleId, parseInt(target.getAttribute('data-page'), 10) || 1);
        }
      });
    }

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
