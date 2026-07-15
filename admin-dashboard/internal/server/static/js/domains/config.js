// Config — tenant config view/edit/rewrite
// Контракт: admin-endpoints.json (Go proxy)

window.Config = {
  state: {
    config: {},
    configDirty: false,
    savingDisplayNames: false,
    saveIndicator: '',
    saveIndicatorText: '',
    saving: false,
    introspecting: false,
  },

  methods: function () {
    return {
      refreshConfig: async function (tenantId) {
        var id = tenantId || this.selectedTenant;
        if (!id) return;
        try {
          this.config = await Alpine.store('api').get('/api/tenants/' + id + '/config');
        } catch (e) {
          this.config = {};
          Alpine.store('notify').error(e.message);
        }
      },

      toggleReadOnly: function (val) {
        if (!this.config.data_source) {
          this.config.data_source = { read_only: true };
        }
        this.config.data_source.read_only = val;
        this.configDirty = true;
        this.autoSaveConfig('readonly');
      },

      autoSaveConfig: function (label) {
        this.saveIndicator = label;
        this.saveIndicatorText = window.__('msg.saving');
        var self = this;
        this.saveConfig().then(function () {
          self.saveIndicatorText = window.__('msg.saved');
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
          this.config = await Alpine.store('api').post('/api/tenants/' + id + '/introspect');
          Alpine.store('notify').success(window.__('msg.introspected'));
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.introspecting = false;
        }
      },
    };
  },
};
