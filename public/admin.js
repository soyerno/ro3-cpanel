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
    activeTab: 'accounts',
    searchQuery: '',
    statusFilter: 'all',
    sortBy: 'created_desc',
    selectedAccount: null
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

    searchInput: document.getElementById('search-input'),
    statusSelect: document.getElementById('status-select'),
    sortSelect: document.getElementById('sort-select'),
    accountsTbody: document.getElementById('accounts-tbody'),

    tabViewDashboard: document.getElementById('tab-view-dashboard'),
    tabViewAccounts: document.getElementById('tab-view-accounts'),
    tabViewAudit: document.getElementById('tab-view-audit'),
    auditTbody: document.getElementById('audit-tbody'),

    // Modals
    modalDetail: document.getElementById('modal-detail'),
    modalPassword: document.getElementById('modal-password'),
    modalCreate: document.getElementById('modal-create'),
    modalBan: document.getElementById('modal-ban'),
    modalDelete: document.getElementById('modal-delete'),

    toasts: document.getElementById('toast-container')
  };

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
    return Number(num).toLocaleString();
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleString(undefined, {
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

  function handleLogin(e) {
    e.preventDefault();
    var user = (els.loginUser.value || '').trim();
    var pass = els.loginPass.value || '';

    if (!user || !pass) {
      showLoginError('Por favor complete usuario y contraseña.');
      return;
    }

    els.loginSubmit.disabled = true;
    els.loginSubmit.textContent = 'Verificando...';
    if (els.loginError) els.loginError.hidden = true;

    apiFetch('/api/admin/login', {
      method: 'POST',
      body: { username: user, password: pass }
    })
      .then(function (data) {
        showToast('Bienvenido, ' + data.user + ' (Administrador)', 'success');
        els.loginPass.value = '';
        setAuthenticated(data.user);
      })
      .catch(function (err) {
        showLoginError(err.message || 'Credenciales inválidas');
      })
      .finally(function () {
        els.loginSubmit.disabled = false;
        els.loginSubmit.textContent = 'Acceder al Panel';
      });
  }

  function showLoginError(msg) {
    if (!els.loginError) return;
    els.loginError.textContent = msg;
    els.loginError.hidden = false;
  }

  function handleLogout() {
    if (!confirm('¿Desea cerrar la sesión de administración?')) return;
    apiFetch('/api/admin/logout', { method: 'POST' })
      .finally(function () {
        showToast('Sesión cerrada correctamente', 'info');
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
        console.error('Error cargando estadísticas:', err);
      });
  }

  function updateStatsUI() {
    if (!state.stats) return;
    var s = state.stats;

    if (els.serverStatusDot) {
      els.serverStatusDot.className = 'status-dot ' + (s.server.online ? 'online' : '');
    }
    if (els.serverStatusText) {
      els.serverStatusText.textContent = s.server.online ? 'En línea' : 'Sin conexión';
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

  function loadAccounts() {
    var params = new URLSearchParams();
    if (state.searchQuery) params.set('q', state.searchQuery);
    if (state.statusFilter) params.set('status', state.statusFilter);
    if (state.sortBy) params.set('sort', state.sortBy);

    apiFetch('/api/admin/accounts?' + params.toString())
      .then(function (data) {
        state.accounts = data.accounts || [];
        renderAccountsTable();
      })
      .catch(function (err) {
        showToast('Error cargando cuentas: ' + err.message, 'error');
      });
  }

  function renderAccountsTable() {
    if (!els.accountsTbody) return;
    var list = state.accounts;

    if (!list.length) {
      els.accountsTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 32px;">No se encontraron cuentas con los criterios de búsqueda.</td></tr>';
      return;
    }

    var html = '';
    list.forEach(function (acc) {
      var badgeHtml = '';
      if (acc.is_admin) {
        badgeHtml = '<span class="badge badge-admin">★ GM Admin</span>';
      } else if (acc.is_banned) {
        badgeHtml = '<span class="badge badge-banned" title="' + escapeHtml(acc.ban_reason) + '">✕ Baneada</span>';
      } else {
        badgeHtml = '<span class="badge badge-active">✓ Activa</span>';
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
        charsHtml = '<span style="color: var(--text-dim); font-size: 11px;">Sin personajes</span>';
      }

      html += '<tr data-account="' + escapeHtml(acc.name) + '">' +
        '<td><strong style="color: #fff; font-size: 14px;">' + escapeHtml(acc.name) + '</strong></td>' +
        '<td>' + badgeHtml + '</td>' +
        '<td>' + charsHtml + '</td>' +
        '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(acc.created_utc) + '</td>' +
        '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(acc.last_login) + '</td>' +
        '<td>' +
          '<div style="display: flex; gap: 6px;">' +
            '<button class="btn btn-secondary btn-sm btn-view-detail" data-account="' + escapeHtml(acc.name) + '" title="Ver detalles y personajes">Ficha</button>' +
            '<button class="btn btn-secondary btn-sm btn-change-pw" data-account="' + escapeHtml(acc.name) + '" title="Cambiar contraseña">Clave</button>' +
            (acc.is_admin ? '' : (acc.is_banned ?
              '<button class="btn btn-secondary btn-sm btn-unban" data-account="' + escapeHtml(acc.name) + '" title="Quitar suspensión">Desbanear</button>' :
              '<button class="btn btn-danger btn-sm btn-ban" data-account="' + escapeHtml(acc.name) + '" title="Suspender cuenta">Ban</button>'
            )) +
            (acc.is_admin ? '' : '<button class="btn btn-danger btn-sm btn-delete" data-account="' + escapeHtml(acc.name) + '" title="Eliminar cuenta">✕</button>') +
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
          '<span class="badge badge-banned">Baneada (' + escapeHtml(acc.ban_reason) + ')</span>' :
          '<span class="badge badge-active">Activa</span>';
        document.getElementById('detail-acc-tokens').textContent = acc.tokens_count + ' sesiones';

        var notesField = document.getElementById('detail-acc-notes');
        if (notesField) notesField.value = acc.notes || '';

        var charsContainer = document.getElementById('detail-chars-list');
        if (charsContainer) {
          if (!acc.characters || !acc.characters.length) {
            charsContainer.innerHTML = '<p style="color: var(--text-muted); padding: 12px;">Esta cuenta no posee personajes creados aún.</p>';
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
                    'Nivel ' + c.level + ' / Job ' + c.job_level +
                  '</div>' +
                '</div>' +
                '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 8px;">' +
                  '<div><strong>Zeny:</strong> <span style="color: var(--success);">' + formatNumber(c.currency.zeny) + ' Z</span></div>' +
                  '<div><strong>Diamantes:</strong> <span style="color: var(--info);">' + formatNumber(c.currency.diamonds) + '</span></div>' +
                  '<div><strong>Ubicación:</strong> ' + escapeHtml(c.scene_name) + ' (' + c.pos.x + ', ' + c.pos.z + ')</div>' +
                  '<div><strong>Último ingreso:</strong> ' + formatDate(c.last_login) + '</div>' +
                '</div>' +
                '<div class="stats-grid-mini">' +
                  '<div><div class="stat-box-lbl">STR</div><div class="stat-box-val">' + c.stats.str + '</div></div>' +
                  '<div><div class="stat-box-lbl">AGI</div><div class="stat-box-val">' + c.stats.agi + '</div></div>' +
                  '<div><div class="stat-box-lbl">VIT</div><div class="stat-box-val">' + c.stats.vit + '</div></div>' +
                  '<div><div class="stat-box-lbl">INT</div><div class="stat-box-val">' + c.stats.int + '</div></div>' +
                  '<div><div class="stat-box-lbl">DEX</div><div class="stat-box-val">' + c.stats.dex + '</div></div>' +
                  '<div><div class="stat-box-lbl">LUK</div><div class="stat-box-val">' + c.stats.luk + '</div></div>' +
                '</div>' +
              '</div>';
            });
            charsContainer.innerHTML = charsHtml;
          }
        }

        openModal(els.modalDetail);
      })
      .catch(function (err) {
        showToast('Error cargando ficha: ' + err.message, 'error');
      });
  }

  function handleSaveNotes() {
    if (!state.selectedAccount) return;
    var notes = (document.getElementById('detail-acc-notes').value || '').trim();
    apiFetch('/api/admin/accounts/save-notes', {
      method: 'POST',
      body: { username: state.selectedAccount.name, notes: notes }
    })
      .then(function () {
        showToast('Notas actualizadas correctamente', 'success');
      })
      .catch(function (err) {
        showToast('Error guardando notas: ' + err.message, 'error');
      });
  }

  function showChangePassword(name) {
    state.selectedAccount = { name: name };
    document.getElementById('pw-acc-name').textContent = name;
    document.getElementById('pw-new-pass').value = '';
    openModal(els.modalPassword);
  }

  function handleUpdatePassword(e) {
    e.preventDefault();
    if (!state.selectedAccount) return;
    var newPass = document.getElementById('pw-new-pass').value || '';
    if (!newPass || newPass.length < 6) {
      showToast('La nueva contraseña debe tener al menos 6 caracteres.', 'error');
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
        showToast('Error: ' + err.message, 'error');
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
      showToast('El usuario debe tener al menos 3 caracteres.', 'error');
      return;
    }
    if (!pass || pass.length < 6) {
      showToast('La contraseña debe tener al menos 6 caracteres.', 'error');
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
        showToast('Error creando cuenta: ' + err.message, 'error');
      });
  }

  function showBanAccount(name) {
    state.selectedAccount = { name: name };
    document.getElementById('ban-acc-name').textContent = name;
    document.getElementById('ban-reason').value = '';
    openModal(els.modalBan);
  }

  function handleBanAccount(e) {
    e.preventDefault();
    if (!state.selectedAccount) return;
    var reason = (document.getElementById('ban-reason').value || '').trim() || 'Suspensión administrativa';

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
        showToast('Error suspendiendo cuenta: ' + err.message, 'error');
      });
  }

  function handleUnbanAccount(name) {
    if (!confirm('¿Desea restablecer y quitar la suspensión de la cuenta "' + name + '"?')) return;
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
        showToast('Error quitando suspensión: ' + err.message, 'error');
      });
  }

  function showDeleteAccount(name) {
    state.selectedAccount = { name: name };
    document.getElementById('del-acc-name').textContent = name;
    document.getElementById('del-confirm-name').value = '';
    openModal(els.modalDelete);
  }

  function handleDeleteAccount(e) {
    e.preventDefault();
    if (!state.selectedAccount) return;
    var typedName = (document.getElementById('del-confirm-name').value || '').trim();
    if (typedName !== state.selectedAccount.name) {
      showToast('Debe escribir exactamente el nombre de la cuenta para confirmar.', 'error');
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
        showToast('Error eliminando cuenta: ' + err.message, 'error');
      });
  }

  function loadAuditLog() {
    apiFetch('/api/admin/audit-log')
      .then(function (data) {
        var logs = data.logs || [];
        if (!els.auditTbody) return;
        if (!logs.length) {
          els.auditTbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No hay registros de auditoría aún.</td></tr>';
          return;
        }
        var html = '';
        logs.forEach(function (l) {
          html += '<tr>' +
            '<td style="color: var(--text-muted); font-size: 12px;">' + formatDate(l.created_utc) + '</td>' +
            '<td><strong style="color: var(--gold);">' + escapeHtml(l.admin_user) + '</strong></td>' +
            '<td><span class="badge badge-admin">' + escapeHtml(l.action) + '</span></td>' +
            '<td>' + (l.target ? '<strong style="color: #fff;">' + escapeHtml(l.target) + '</strong>' : '—') + '</td>' +
            '<td style="color: var(--text-muted);">' + escapeHtml(l.details) + '</td>' +
          '</tr>';
        });
        els.auditTbody.innerHTML = html;
      })
      .catch(function (err) {
        showToast('Error cargando registros: ' + err.message, 'error');
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

    if (tabId === 'audit') {
      loadAuditLog();
    } else if (tabId === 'dashboard') {
      loadStats();
    } else if (tabId === 'accounts') {
      loadAccounts();
    }
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    if (els.loginForm) els.loginForm.addEventListener('submit', handleLogin);
    if (els.btnLogout) els.btnLogout.addEventListener('click', handleLogout);

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
        searchTimeout = setTimeout(loadAccounts, 250);
      });
    }

    if (els.statusSelect) {
      els.statusSelect.addEventListener('change', function () {
        state.statusFilter = this.value;
        loadAccounts();
      });
    }

    if (els.sortSelect) {
      els.sortSelect.addEventListener('change', function () {
        state.sortBy = this.value;
        loadAccounts();
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
        showToast('Datos actualizados', 'info');
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

    var btnSaveNotes = document.getElementById('btn-save-notes');
    if (btnSaveNotes) btnSaveNotes.addEventListener('click', handleSaveNotes);
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', function () {
    setupEventListeners();
    loadBranding();
    checkSession();
  });

})();
