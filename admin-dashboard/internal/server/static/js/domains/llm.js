// LLM Provider Fallback domain module
// Контракты: admin-contracts.json (GET /api/llm-config, GET/POST /api/llm-providers/*)

window.Llm = {
  state: {
    llmConfig: { providers: [], fallback_enabled: false },
    llmError: '',
    llmTab: 'list',
    llmNew: { name: '', model: '', api_key: '', api_base: '', enabled: true, provider: '' },
    llmEdit: { model: '', api_key: '', api_base: '', has_api_key: false, api_key_masked: '', enabled: true },
    llmEditName: '',
    llmProviderList: null,
    llmSaving: false,
    llmSaveMsg: '',
    llmDeleteConfirm: false,
  },

  methods: function () {
    return {
      loadLlmConfig: async function () {
        this.llmError = '';
        try {
          this.llmConfig = await Alpine.store('api').get('/api/llm-config');
          await this.loadLlmProviderList();
        } catch (e) {
          this.llmError = e.message || this.__('llm.loadError');
          this.llmConfig = null;
        }
      },

      get hasFallbackProvider() {
        return this.llmConfig && this.llmConfig.num_models > 0;
      },

      loadLlmProviderList: async function () {
        try {
          var res = await Alpine.store('api').get('/api/llm-provider-list');
          this.llmProviderList = res.providers || [];
        } catch (e) {
          this.llmProviderList = [];
        }
      },

      loadLlmProviders: async function () {
        await this.loadLlmConfig();
      },

      addLlmProvider: async function () {
        this.llmSaving = true;
        this.llmSaveMsg = '';
        try {
          var body = {
            name: this.llmNew.name,
            model: this.llmNew.model,
            provider: this.llmNew.provider || undefined,
            api_key: this.llmNew.api_key || undefined,
            api_base: this.llmNew.api_base || undefined,
            enabled: this.llmNew.enabled,
          };
          await Alpine.store('api').post('/api/llm-providers', body);
          this.llmNew = { name: '', model: '', api_key: '', api_base: '', enabled: true, provider: '' };
          Alpine.store('notify').success(this.__('msg.saved'));
          await this.loadLlmConfig();
          Alpine.store('events').emit('llm:providers-changed');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.llmSaving = false;
        }
      },

      startEditLlmProvider: function (name) {
        var p = this.llmConfig && this.llmConfig.providers && this.llmConfig.providers.find(function (x) {
          return x.name === name;
        });
        if (!p) return;
        this.llmEditName = name;
        this.llmEdit = {
          model: p.model,
          api_key: '',
          api_base: p.api_base || '',
          enabled: p.enabled,
          has_api_key: p.has_api_key,
          api_key_masked: p.api_key_masked,
        };
        this.llmTab = 'edit';
      },

      saveLlmProvider: async function () {
        if (!this.llmEditName) return;
        this.llmSaving = true;
        this.llmSaveMsg = '';
        try {
          var body = { model: this.llmEdit.model, api_base: this.llmEdit.api_base || undefined, enabled: this.llmEdit.enabled };
          if (this.llmEdit.api_key && this.llmEdit.api_key.trim()) {
            body.api_key = this.llmEdit.api_key.trim();
          } else if (this.llmEdit.api_key === '') {
            body.api_key = '';
          }
          await Alpine.store('api').put('/api/llm-providers/' + this.llmEditName, body);
          Alpine.store('notify').success(this.__('msg.saved'));
          await this.loadLlmConfig();
          Alpine.store('events').emit('llm:providers-changed');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.llmSaving = false;
        }
      },

      deleteLlmProvider: async function (name) {
        if (!confirm(this.__('llm.deleteConfirmMsg') + ' "' + name + '"?')) return;
        try {
          await Alpine.store('api').del('/api/llm-providers/' + name);
          await this.loadLlmConfig();
          Alpine.store('events').emit('llm:providers-changed');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      toggleLlmProvider: async function (name) {
        try {
          await Alpine.store('api').post('/api/llm-providers/' + name + '/toggle');
          await this.loadLlmConfig();
          Alpine.store('events').emit('llm:providers-changed');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      cancelLlmEdit: function () {
        this.llmTab = 'list';
        this.llmEdit = null;
        this.llmEditName = '';
      },
    };
  },
};
