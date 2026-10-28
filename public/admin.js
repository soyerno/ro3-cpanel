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
        showToast('Error cargando cuentas: ' + err.message, 'error');
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
      els.pagerInfo.textContent = 'Página ' + state.accountsPage + ' de ' + state.accountsPages +
        ' (' + formatNumber(state.accountsTotal) + ' cuentas)';
    }
    if (els.pagerPrev) els.pagerPrev.disabled = state.accountsPage <= 1;
    if (els.pagerNext) els.pagerNext.disabled = state.accountsPage >= state.accountsPages;
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
                '<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">' +
                  '<button class="btn btn-secondary btn-sm btn-view-inventory" data-role-id="' + escapeHtml(String(c.id)) + '" title="Ver objetos del personaje">Ver inventario</button>' +
                  '<button type="button" class="btn btn-secondary btn-sm btn-view-mail" data-role-id="' + escapeHtml(String(c.id)) + '" title="Ver correo del personaje (solo lectura)">Ver correo</button>' +
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
        showToast('Error cargando ficha: ' + err.message, 'error');
      });
  }

  // --- Character Mail (read-only) ---
  var MAIL_PAGE_SIZE = 10;

  function renderMailAttachments(m) {
    var parts = [];
    (m.attachments || []).forEach(function (a) {
      parts.push('Ítem ' + escapeHtml(String(a.entry)) + ' x' + escapeHtml(String(a.count)));
    });
    (m.items || []).forEach(function (it) {
      parts.push('Ítem ' + escapeHtml(String(it.entry)) + ' x' + escapeHtml(String(it.stack)));
    });
    (m.currency || []).forEach(function (cur) {
      parts.push('Moneda ' + escapeHtml(String(cur.entry)) + ': ' + formatNumber(cur.amount));
    });
    return parts.length ? parts.join(', ') : 'Sin adjuntos';
  }

  function renderCharacterMail(panel, roleId, data) {
    if (!data.decodable) {
      panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml(data.message || 'El buzón no se pudo decodificar.') + '</p>';
      return;
    }
    if (!data.mails.length) {
      panel.innerHTML = '<p class="char-mail-empty">' + (data.total ? 'No hay correos en esta página.' : 'El buzón está vacío.') + '</p>';
      return;
    }
    var html = '<ul class="char-mail-list">';
    data.mails.forEach(function (m) {
      var subject = m.title || m.abstract || ('Plantilla ' + String(m.template_id));
      html += '<li class="char-mail-item">' +
        '<div class="char-mail-head">' +
          '<strong>' + escapeHtml(subject) + '</strong>' +
          '<span class="badge ' + (m.read ? 'badge-active' : 'badge-admin') + '">' + (m.read ? 'Leído' : 'No leído') + '</span>' +
          (m.claimed ? ' <span class="badge badge-active">Reclamado</span>' : '') +
        '</div>' +
        '<div class="char-mail-meta">De: ' + escapeHtml(m.sender || '—') + ' · ' + formatDate(m.created_at) +
          (m.remove_at ? ' · Expira: ' + formatDate(m.remove_at) : '') + '</div>' +
        (m.content ? '<div class="char-mail-body">' + escapeHtml(m.content) + '</div>' : '') +
        '<div class="char-mail-meta">Adjuntos (' + escapeHtml(String(m.attachment_count)) + '): ' + renderMailAttachments(m) + '</div>' +
      '</li>';
    });
    html += '</ul>';
    html += '<div class="pager">' +
      '<button type="button" class="btn btn-secondary btn-sm btn-mail-page" data-role-id="' + escapeHtml(String(roleId)) + '" data-page="' + escapeHtml(String(data.page - 1)) + '"' + (data.page <= 1 ? ' disabled' : '') + '>Anterior</button>' +
      '<span class="pager-info">Página ' + escapeHtml(String(data.page)) + ' de ' + escapeHtml(String(data.pages)) + ' · ' + escapeHtml(String(data.total)) + ' correos</span>' +
      '<button type="button" class="btn btn-secondary btn-sm btn-mail-page" data-role-id="' + escapeHtml(String(roleId)) + '" data-page="' + escapeHtml(String(data.page + 1)) + '"' + (data.page >= data.pages ? ' disabled' : '') + '>Siguiente</button>' +
    '</div>';
    panel.innerHTML = html;
  }

  function loadCharacterMail(roleId, page) {
    var panel = document.getElementById('char-mail-' + roleId);
    if (!panel) return;
    panel.hidden = false;
    panel.innerHTML = '<p class="char-mail-empty">Cargando correo...</p>';
    apiFetch('/api/admin/characters/' + encodeURIComponent(roleId) + '/mail?page=' + encodeURIComponent(page) + '&page_size=' + MAIL_PAGE_SIZE)
      .then(function (data) {
        renderCharacterMail(panel, roleId, data);
      })
      .catch(function (err) {
        panel.innerHTML = '<p class="char-mail-empty">' + escapeHtml('Error cargando correo: ' + err.message) + '</p>';
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
      btn.textContent = 'Ver inventario';
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Cargando...';
    apiFetch('/api/admin/characters/' + encodeURIComponent(roleId) + '/items')
      .then(function (data) {
        container.innerHTML = renderInventory(data);
        container.hidden = false;
        btn.textContent = 'Ocultar inventario';
      })
      .catch(function (err) {
        btn.textContent = 'Ver inventario';
        showToast('Error cargando inventario: ' + err.message, 'error');
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function renderInventory(data) {
    var boxStyle = 'margin-top: 8px; padding: 10px; background: #0c1018; border: 1px solid var(--border-color); border-radius: var(--radius-sm); font-size: 12px;';
    if (!data || data.available === false) {
      return '<div style="' + boxStyle + ' color: var(--text-muted);">El inventario no está disponible en esta base de datos.</div>';
    }
    var items = data.items || [];
    if (!items.length) {
      return '<div style="' + boxStyle + ' color: var(--text-muted);">Este personaje no tiene objetos.</div>';
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
      '<div style="color: var(--text-muted); margin-bottom: 8px;">Total de objetos: <strong style="color: #fff;">' + formatNumber(data.total) + '</strong></div>';
    groups.forEach(function (g) {
      var label = g.packName || ('Bolsa ' + g.pack);
      html += '<div style="margin-bottom: 10px;">' +
        '<span class="badge badge-admin">' + escapeHtml(label) + ' (' + g.items.length + ')</span>' +
        '<table class="data-table" style="margin-top: 6px;">' +
          '<thead><tr><th>Objeto</th><th>Cantidad</th><th>Estado</th></tr></thead><tbody>';
      g.items.forEach(function (item) {
        var name = item.name ? escapeHtml(item.name) : '#' + escapeHtml(String(item.entry));
        var flags = [];
        if (item.equipped) flags.push('<span class="badge badge-active">Equipado</span>');
        if (item.locked) flags.push('<span class="badge badge-banned">Bloqueado</span>');
        if (item.bind_type) flags.push('<span class="badge badge-admin">Ligado</span>');
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
        showToast('Error cargando economía: ' + err.message, 'error');
      });
  }

  function describeEconomyOwner(e) {
    if (e.owner_name) return escapeHtml(e.owner_name);
    return escapeHtml(e.owner_kind_label) + ' ' + escapeHtml(e.owner_id);
  }

  function renderEconomyTable(entries, available) {
    if (!els.economyTbody) return;
    if (!entries.length) {
      var msg = available ? 'No hay movimientos para los filtros seleccionados.' : 'Registro de economía no disponible en esta base de datos.';
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
      els.economyPageInfo.textContent = 'Página ' + eco.page + ' de ' + eco.pages + ' (' + formatNumber(total) + ' movimientos)';
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
  var RANKING_METRIC_LABELS = {
    level: 'Nivel Base',
    zeny: 'Zeny',
    power: 'Poder'
  };

  function renderRankingsHead(type) {
    if (!els.rankingsThead) return;
    if (type === 'guilds') {
      els.rankingsThead.innerHTML = '<tr>' +
        '<th style="width: 10%;">#</th>' +
        '<th>Clan</th>' +
        '<th style="width: 22%;">Miembros Activos</th>' +
        '<th style="width: 22%;">Nivel Total</th>' +
      '</tr>';
      return;
    }
    els.rankingsThead.innerHTML = '<tr>' +
      '<th style="width: 8%;">#</th>' +
      '<th>Personaje</th>' +
      '<th style="width: 18%;">Cuenta</th>' +
      '<th style="width: 18%;">Clase</th>' +
      '<th style="width: 14%;">Nivel / Job</th>' +
      '<th style="width: 16%;">' + escapeHtml(RANKING_METRIC_LABELS[type] || '') + '</th>' +
    '</tr>';
  }

  function renderRankingsPager() {
    var totalPages = Math.max(1, Math.ceil(state.rankingTotal / state.rankingLimit));
    if (els.rankingPageLabel) {
      els.rankingPageLabel.textContent = 'Página ' + state.rankingPage + ' de ' + totalPages +
        ' (' + formatNumber(state.rankingTotal) + ')';
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
          els.rankingsTbody.innerHTML = '<tr><td colspan="' + colspan + '" style="text-align: center; color: var(--text-muted); padding: 24px;">La base de datos no tiene tablas de clanes todavía.</td></tr>';
          return;
        }
        if (!rows.length) {
          els.rankingsTbody.innerHTML = '<tr><td colspan="' + colspan + '" style="text-align: center; color: var(--text-muted); padding: 24px;">No hay datos para este ranking.</td></tr>';
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
        showToast('Error cargando rankings: ' + err.message, 'error');
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

    if (tabId === 'audit') {
      loadAuditLog();
    } else if (tabId === 'economy') {
      loadEconomy();
    } else if (tabId === 'rankings') {
      loadRankings();
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
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', function () {
    setupEventListeners();
    loadBranding();
    checkSession();
  });

})();
