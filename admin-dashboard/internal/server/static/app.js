// app.js — точка входа. Собирает state + methods из всех доменов.
// Каждый домен = window.DOMAIN = { state: {...}, methods: function() { return {...} } }
// State мерджится в return объект, methods инжектятся через Object.assign в init().
//
// Чтобы добавить новый домен:
//   1. Создай js/domains/<name>.js по контракту window.<Name> = { state, methods()
//   2. Добавь название в DASHBOARD_DOMAINS (единственный source of truth)
//   3. Добавь <script src="/js/domains/<name>.js"> в index.html
//   4. Добавь endpoint(ы) в tests/contracts/*.json

var DASHBOARD_DOMAINS = ['Auth','Tenants','Config','Tools','RAG','Agents','Abuse','Emergency','Llm','Voice'];

function collectDomainStates() {
  var s = {};
  DASHBOARD_DOMAINS.forEach(function (d) {
    Object.assign(s, window[d].state);
  });
  return s;
}

function dashboard() {
  return {
    // ═══════════════════════════════════════════
    //  STATE: мердж из всех доменов (через DASHBOARD_DOMAINS)
    // ═══════════════════════════════════════════
    ...collectDomainStates(),

    // ── Emergency computed getters ──
    // These can't be in state (they're computed) and Object.assign can't copy getters
    get emergencyPresetLabel() {
      if (this.emergencyCurrentPreset === 'lockdown') return this.__('emergency.labelLockdown');
      if (this.emergencyCurrentPreset === 'cautious') return this.__('emergency.labelCautious');
      return this.__('emergency.labelNormal');
    },
    get emergencyPresetDescription() {
      if (this.emergencyCurrentPreset === 'lockdown') return this.__('emergency.descLockdown');
      if (this.emergencyCurrentPreset === 'cautious') return this.__('emergency.descCautious');
      return this.__('emergency.descNormal');
    },
    get emergencyPresetClass() {
      if (this.emergencyCurrentPreset === 'lockdown') return 'emergency-lockdown';
      if (this.emergencyCurrentPreset === 'cautious') return 'emergency-cautious';
      return 'emergency-normal';
    },

    // ── Dashboard (своя малая секция) ──
    dashboard: {},

    // ── Aliases to Alpine.store('ui') (HTML uses direct properties) ──
    get page() { return Alpine.store('ui').page; },
    set page(v) { Alpine.store('ui').page = v; },
    get error() { return Alpine.store('ui').error; },
    set error(v) { Alpine.store('ui').error = v; },
    get loading() { return Alpine.store('ui').loading; },
    set loading(v) { Alpine.store('ui').loading = v; },
    get dataService() { return Alpine.store('ui').dataService; },
    set dataService(v) { Alpine.store('ui').dataService = v; },

    // ═══════════════════════════════════════════
    //  I18N
    // ═══════════════════════════════════════════
    __: function (key) {
      if (typeof window.__ === 'function') {
        return window.__(key);
      }
      return key;
    },

    // ═══════════════════════════════════════════
    //  INIT — inject методы + подписки
    // ═══════════════════════════════════════════
    init: function () {
      if (!this.tokenSet) return;

      // Inject методы из всех доменов (через DASHBOARD_DOMAINS)
      var self = this;
      DASHBOARD_DOMAINS.forEach(function (d) {
        Object.assign(self, window[d].methods());
      });

      // Cross-domain подписки

      Alpine.store('events').on('tenant:selected', function (data) {
        self.refreshConfig(data.id);
        self.loadPendingTools(data.id);
        self.loadManifest(data.id);
      });

      Alpine.store('events').on('config:saved', function () {
        self.loadPendingTools(self.selectedTenant);
        self.loadManifest(self.selectedTenant);
      });

      // LLM провайдеры изменились — обновить список в agent диалоге
      Alpine.store('events').on('llm:providers-changed', function () {
        if (typeof self.loadLlmProviderStoreList === 'function') {
          self.loadLlmProviderStoreList();
        }
        // Также обновить Llm модуль, если он уже загружен
        if (typeof self.loadLlmConfig === 'function') {
          self.loadLlmConfig();
        }
      });

      // Agents изменились — обновить список LLM провайдеров (кеш мог протухнуть)
      Alpine.store('events').on('agents:updated', function () {
        if (typeof self.loadLlmProviderStoreList === 'function') {
          self.loadLlmProviderStoreList();
        }
      });

      // Первичная загрузка
      this.refreshDashboard();
      this.loadTenants();
      this.refreshRag();
    },

    // ═══════════════════════════════════════════
    //  DASHBOARD (малый — не вынесен в домен)
    // ═══════════════════════════════════════════
    refreshDashboard: async function () {
      try {
        this.dashboard = await Alpine.store('api').get('/api/dashboard');
        Alpine.store('ui').dataService = this.dashboard.data_service || '';
      } catch (_e) {
        // error handled in apiClient
      }
    },
  };
}
