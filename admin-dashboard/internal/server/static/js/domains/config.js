// Config — tenant config view/edit/rewrite
// Контракт: admin-endpoints.json (Go proxy)

window.Config = {
  state: {
    config: {},
    computed: {}, // derived display values
    configDirty: false,
    configgenTab: 'skip',
    savingDisplayNames: false,
    saveIndicator: '',
    saveIndicatorText: '',
    saving: false,
    introspecting: false,
    _configgenTimer: null,
    defaultSkipRules: [
      {prefix: 'sqlite_', reason: 'SQLite: internal schema tables (sqlite_sequence, sqlite_stat1) — not user data'},
      {prefix: 'pg_', reason: 'PostgreSQL: internal system catalogs (pg_type, pg_class, pg_attribute)'},
      {prefix: 'pg_catalog', reason: 'PostgreSQL: system catalog schema with internal types and meta'},
      {prefix: 'information_schema', reason: 'SQL standard: read-only system views describing database structure'},
      {prefix: 'auth_', reason: 'Django: built-in auth tables (auth_user, auth_group, auth_permission)'},
      {prefix: 'django_', reason: 'Django: framework metadata (django_migrations, django_content_type)'},
      {prefix: 'session', reason: 'Django: server-side session storage — no business value'},
      {prefix: 'documents', reason: 'Helperium RAG: internal document chunks and embeddings'},
      {prefix: 'migrations', reason: 'Laravel: framework migration tracking'},
      {prefix: 'jobs', reason: 'Laravel: queue job storage — operational'},
      {prefix: 'failed_jobs', reason: 'Laravel: queue failure log — operational'},
      {prefix: 'schema_migrations', reason: 'Rails: migration version tracking'},
      {prefix: 'ar_internal_metadata', reason: 'Rails: ActiveRecord internal schema metadata'},
    ],
    disabledDefaultRules: [],
    _configSeq: 0,
  },

  methods: function () {
    return {
      refreshConfig: async function (tenantId) {
        var id = tenantId || this.selectedTenant;
        if (!id) return;
        // Sequence guard — discard stale responses from concurrent calls
        var seq = ++this._configSeq;
        // Clear stale data immediately to prevent ghosting old endpoints
        this.config = {};
        this.computed = {};
        try {
          var data = await Alpine.store('api').get('/api/tenants/' + id + '/config');
          if (seq !== this._configSeq) return; // stale — a newer refresh was started
          this.config = data;
          this._computeSummary(data);
          // Init disabledDefaultRules from server
          this.disabledDefaultRules = data.disabled_default_rules || [];
        } catch (e) {
          if (seq !== this._configSeq) return;
          Alpine.store('notify').error(e.message);
        }
      },

      // ── Config summary (informative display) ──

      _computeSummary: function (cfg) {
        var s = {};
        s.driver = (cfg.data_source && cfg.data_source.driver) || '—';
        s.readonly = cfg.data_source ? cfg.data_source.read_only !== false : true;
        s.poolSize = (cfg.data_source && cfg.data_source.pool_size) || '—';
        s.entities = (cfg.entities && cfg.entities.length) || 0;
        s.endpoints = (cfg.endpoints && cfg.endpoints.length) || 0;
        s.mcpTools = (cfg.mcp_tools && cfg.mcp_tools.length) || 0;
        s.customQueries = cfg.custom_queries ? Object.keys(cfg.custom_queries).length : 0;

        // ConfigGen
        s.skipRules = (cfg.skip_rules && cfg.skip_rules.length) || 0;
        s.displayPrefixes = (cfg.display_prefixes && cfg.display_prefixes.join(', ')) || '—';
        s.customPlurals = cfg.custom_plurals ? Object.keys(cfg.custom_plurals).length : 0;

        // Approved tools
        s.approvedTools = (cfg.approved_tools && cfg.approved_tools.length) || 0;

        this.computed = s;
      },

      // ── Configgen auto-save (debounced) ──

      _configgenChanged: function () {
        this.configDirty = true;
        if (this._configgenTimer) clearTimeout(this._configgenTimer);
        var self = this;
        this._configgenTimer = setTimeout(function () {
          self._cleanConfiggen();
          self.saveConfig()
            .then(function () {
              self._computeSummary(self.config);
              self.configDirty = false;
            })
            .catch(function (err) {
              Alpine.store('notify').error(err.message);
              self.configDirty = false;
            });
        }, 800);
      },

      // Clean empty values from configgen fields before save
      _cleanConfiggen: function () {
        // Remove empty skip rules
        if (this.config.skip_rules) {
          this.config.skip_rules = this.config.skip_rules.filter(function (r) {
            return r && (r.prefix || r.suffix || r.contains);
          });
          if (this.config.skip_rules.length === 0) {
            delete this.config.skip_rules;
          }
        }
        // Remove empty display prefixes
        if (this.config.display_prefixes) {
          this.config.display_prefixes = this.config.display_prefixes.filter(function (p) {
            return p && p.trim() !== '';
          });
        }
        // Remove empty custom plurals
        if (this.config.custom_plurals) {
          var cleaned = {};
          var has = false;
          for (var k in this.config.custom_plurals) {
            if (this.config.custom_plurals.hasOwnProperty(k) && k && this.config.custom_plurals[k]) {
              cleaned[k] = this.config.custom_plurals[k];
              has = true;
            }
          }
          if (has) {
            this.config.custom_plurals = cleaned;
          } else {
            delete this.config.custom_plurals;
          }
        }
      },

      // ── Skip Rules ──

      addSkipRule: function () {
        if (!this.config.skip_rules) {
          this.config.skip_rules = [];
        }
        this.config.skip_rules.push({ prefix: '', suffix: '', contains: '', reason: '' });
        this._configgenChanged();
      },

      removeSkipRule: function (index) {
        if (this.config.skip_rules) {
          this.config.skip_rules.splice(index, 1);
          this._configgenChanged();
        }
      },

      // ── Custom Plurals ──

      addCustomPlural: function () {
        if (!this.config.custom_plurals) {
          this.config.custom_plurals = {};
        }
        var key = 'new_' + Date.now();
        this.config.custom_plurals[key] = '';
        this._configgenChanged();
      },

      removeCustomPlural: function (key) {
        if (this.config.custom_plurals) {
          delete this.config.custom_plurals[key];
          this._configgenChanged();
        }
      },

      // ── Hide Entity (adds skip rule for its table) ──

      hideEntity: function (index) {
        var entity = this.config.entities[index];
        if (!entity) return;
        var name = entity.name;
        var tableName = entity.table_name || name;

        // Add skip rule for rewrite
        if (!this.config.skip_rules) {
          this.config.skip_rules = [];
        }
        this.config.skip_rules.push({ prefix: '', suffix: '', contains: tableName, reason: 'Скрыта из UI' });

        // Clean up related endpoints, counters, mcp_tools
        if (this.config.endpoints) {
          this.config.endpoints = this.config.endpoints.filter(function (ep) { return ep.entity !== name; });
        }
        if (this.config.mcp_tools) {
          this.config.mcp_tools = this.config.mcp_tools.filter(function (tool) {
            // Match both direct entity ref and prefixed tool names
            return !tool.name.endsWith('_' + name) && tool.entity !== name;
          });
        }
        if (this.config.stats && this.config.stats.counters) {
          this.config.stats.counters = this.config.stats.counters.filter(function (c) { return c.entity !== name; });
        }

        // Remove entity from list
        this.config.entities.splice(index, 1);
        this._configgenChanged();
      },

      // ── Display Prefixes (chip-style) ──

      addDisplayPrefix: function () {
        if (!this.config.display_prefixes) {
          this.config.display_prefixes = [];
        }
        this.config.display_prefixes.push('');
        this._configgenChanged();
      },

      removeDisplayPrefix: function (index) {
        if (this.config.display_prefixes) {
          this.config.display_prefixes.splice(index, 1);
          this._configgenChanged();
        }
      },

      // ── Save ──

      autoSaveConfig: function (label) {
        this.saveIndicator = label;
        this.saveIndicatorText = window.__('msg.saving');
        var self = this;
        this.saveConfig().then(function () {
          self.saveIndicatorText = window.__('msg.saved');
          // Reload config from server to get actual persisted state
          return self.refreshConfig();
        }).then(function () {
          self.configDirty = false;
          setTimeout(function () { self.saveIndicator = ''; }, 2000);
        }).catch(function () {
          self.saveIndicatorText = window.__('msg.failed');
          setTimeout(function () { self.saveIndicator = ''; }, 3000);
        });
      },

      saveConfig: async function (tenantId) {
        var id = tenantId || this.selectedTenant;
        if (!id) return;
        this.saving = true;
        try {
          var result = await Alpine.store('api').put('/api/tenants/' + id + '/config', this.config);
          Alpine.store('events').emit('config:saved', { id: id });
          return result;
        } catch (e) {
          throw e;
        } finally {
          this.saving = false;
        }
      },

      introspectTenant: async function (tenantId) {
        var id = tenantId || this.selectedTenant;
        if (!id) return;
        this.introspecting = true;
        try {
          // Rewrite returns status — discard it, re-read config from server
          await Alpine.store('api').post('/api/tenants/' + id + '/introspect');
          await this.refreshConfig(id);
          Alpine.store('notify').success(window.__('msg.introspected'));
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.introspecting = false;
        }
      },

      // Preview: strip prefix from entity name (mirrors Go's shortBusinessName)
      _stripPrefix: function (name) {
        if (!name) return '';
        // Use configured prefixes; if none, fall back to Go defaults
        var prefixes = this.config.display_prefixes || [];
        // If no custom prefixes set, use defaults (same as Go DefaultDisplayPrefixes)
        var effective = prefixes.filter(function (p) { return p && p.length > 0; });
        if (effective.length === 0) {
          effective = ['catalog_', 'auth_', 'django_'];
        }
        for (var i = 0; i < effective.length; i++) {
          if (name.indexOf(effective[i]) === 0) {
            var result = name.substring(effective[i].length);
            if (result.length === 0) return name;
            return result.charAt(0).toUpperCase() + result.slice(1);
          }
        }
        return name.charAt(0).toUpperCase() + name.slice(1);
      },

      // Toggle a built-in default rule on/off
      toggleDefaultRule: function (prefix) {
        if (!this.disabledDefaultRules) this.disabledDefaultRules = [];
        var idx = this.disabledDefaultRules.indexOf(prefix);
        if (idx >= 0) {
          this.disabledDefaultRules.splice(idx, 1);
        } else {
          this.disabledDefaultRules.push(prefix);
        }
        this.config.disabled_default_rules = this.disabledDefaultRules;
        this._configgenChanged();
      },

      isDefaultRuleDisabled: function (prefix) {
        return this.disabledDefaultRules && this.disabledDefaultRules.indexOf(prefix) >= 0;
      },
    };
  },
};
