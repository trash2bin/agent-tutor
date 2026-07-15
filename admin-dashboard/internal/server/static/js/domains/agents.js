// agents.js — Agent CRUD + voice overrides
// Контракты: api-endpoints.json (agents, tenants, voice-config, llm-providers)

window.Agents = {
  state: {
    agents: [],
    availableTenants: [],
    showNewAgentForm: false,
    newAgent: { name: '', description: '', tenant_ids_selected: [], provider_priority: [], system_prompt: '' },
    editingAgent: false,
    editAgentData: {
      name: '',
      description: '',
      tenant_ids: [],
      provider_priority: [],
      system_prompt: '',
      voice_config_enabled: true,
      voice_input_disabled: false,
      voice_output_disabled: false,
      voice_stt_provider: '',
      voice_tts_provider: '',
      _sttProviders: [],
      _ttsProviders: [],
    },
    llmProviderStoreList: [],
    creatingAgent: false,
    savingAgent: false,
    agentCreateResult: null,
  },

  methods: function () {
    // ── Private helpers (avoid copy-paste between new/edit forms) ──
    function _reorderArray(arr, idx, dir) {
      var result = [].concat(arr);
      var target = idx + dir;
      if (target < 0 || target >= result.length) return result;
      var tmp = result[idx];
      result[idx] = result[target];
      result[target] = tmp;
      return result;
    }

    function _toggleInArray(arr, name) {
      var idx = arr.indexOf(name);
      if (idx >= 0) {
        return arr.filter(function (n) { return n !== name; });
      }
      return [].concat(arr).concat([name]);
    }

    return {
      // ── Modal ──
      openNewAgentModal: function () {
        this.showNewAgentForm = true;
        this.editingAgent = false;
        this.newAgent = { name: '', description: '', tenant_ids_selected: [], provider_priority: [], system_prompt: '' };
        this.agentCreateResult = null;
        this.loadLlmProviderStoreList();
        this.loadAgents();
      },

      // ── LLM Provider list for priority selector ──
      loadLlmProviderStoreList: function () {
        var self = this;
        Alpine.store('api').get('/api/llm-providers').then(function (resp) {
          self.llmProviderStoreList = resp.providers || [];
        }).catch(function () {
          self.llmProviderStoreList = [];
        });
      },

      // ── Provider priority reorder ──
      moveProviderPriority: function (idx, dir) {
        this.newAgent.provider_priority = _reorderArray(this.newAgent.provider_priority, idx, dir);
      },

      moveEditProviderPriority: function (idx, dir) {
        this.editAgentData.provider_priority = _reorderArray(this.editAgentData.provider_priority, idx, dir);
      },

      toggleProviderPriority: function (name) {
        this.newAgent.provider_priority = _toggleInArray(this.newAgent.provider_priority, name);
      },

      toggleEditProviderPriority: function (name) {
        this.editAgentData.provider_priority = _toggleInArray(this.editAgentData.provider_priority, name);
      },

      // ── Load agent list ──
      loadAgents: function () {
        var self = this;
        Alpine.store('api').get('/api/agents').then(function (resp) {
          self.agentCreateResult = null;
          self.agents = resp.agents || [];
        }).catch(function () {
          self.agents = [];
        });

        Alpine.store('api').get('/api/tenants').then(function (tResp) {
          self.availableTenants = tResp.tenants || [];
        }).catch(function () {
          // ignore
        });
      },

      // ── Create agent ──
      createAgent: function () {
        if (!this.newAgent.name || !/^[a-z][a-z0-9_-]*$/.test(this.newAgent.name)) {
          this.agentCreateResult = { error: this.__('agent.namePatternHint') };
          Alpine.store('notify').error(this.__('agent.namePatternHint'));
          return;
        }
        this.creatingAgent = true;
        this.agentCreateResult = null;

        var self = this;
        var body = {
          name: this.newAgent.name,
          description: this.newAgent.description,
          tenant_ids: this.newAgent.tenant_ids_selected || [],
          provider_priority: this.newAgent.provider_priority || [],
          system_prompt: this.newAgent.system_prompt || null,
        };

        Alpine.store('api').post('/api/agents', body).then(function (result) {
          self.agentCreateResult = result;
          self.showNewAgentForm = false;
          self.newAgent = { name: '', description: '', tenant_ids_selected: [], provider_priority: [], system_prompt: null };
          Alpine.store('notify').success('Agent "' + body.name + '" created');
          Alpine.store('events').emit('agents:created', body.name);
          return self.loadAgents();
        }).catch(function (e) {
          self.agentCreateResult = { error: e.message };
          Alpine.store('notify').error(e.message);
        }).finally(function () {
          self.creatingAgent = false;
        });
      },

      // ── Edit agent modal ──
      editAgent: function (agent) {
        var vc = agent.voice_config || {};

        this.editAgentData = {
          name: agent.name,
          description: agent.description || '',
          tenant_ids: [].concat(agent.tenant_ids || []),
          provider_priority: [].concat(agent.provider_priority || []),
          system_prompt: agent.system_prompt || '',
          voice_config_enabled: vc.enabled != null ? vc.enabled : true,
          voice_input_disabled: vc.voice_input_disabled || false,
          voice_output_disabled: vc.voice_output_disabled || false,
          voice_stt_provider: vc.stt_provider || '',
          voice_tts_provider: vc.tts_provider || '',
          _sttProviders: [],
          _ttsProviders: [],
        };

        this.loadLlmProviderStoreList();
        this.editingAgent = true;

        // Load voice providers for dropdown selects
        var self = this;
        Alpine.store('api').get('/api/voice-config').then(function (vcResp) {
          self.editAgentData._sttProviders = vcResp.stt_providers || [];
          self.editAgentData._ttsProviders = vcResp.tts_providers || [];
        }).catch(function () {
          self.editAgentData._sttProviders = [];
          self.editAgentData._ttsProviders = [];
        });
      },

      // ── Update agent ──
      updateAgent: function () {
        this.savingAgent = true;

        var voiceConfig = {};
        if (this.editAgentData.voice_config_enabled !== undefined) {
          voiceConfig.enabled = this.editAgentData.voice_config_enabled;
        }
        if (this.editAgentData.voice_input_disabled) {
          voiceConfig.voice_input_disabled = true;
        }
        if (this.editAgentData.voice_output_disabled) {
          voiceConfig.voice_output_disabled = true;
        }
        if (this.editAgentData.voice_stt_provider) {
          voiceConfig.stt_provider = this.editAgentData.voice_stt_provider;
        }
        if (this.editAgentData.voice_tts_provider) {
          voiceConfig.tts_provider = this.editAgentData.voice_tts_provider;
        }

        var body = {
          description: this.editAgentData.description,
          tenant_ids: this.editAgentData.tenant_ids,
          provider_priority: this.editAgentData.provider_priority || [],
          system_prompt: this.editAgentData.system_prompt || null,
          voice_config: Object.keys(voiceConfig).length > 0 ? voiceConfig : null,
        };

        var self = this;
        Alpine.store('api').put('/api/agents/' + encodeURIComponent(this.editAgentData.name), body).then(function () {
          self.editingAgent = false;
          Alpine.store('notify').success('Agent "' + self.editAgentData.name + '" updated');
          Alpine.store('events').emit('agents:updated', self.editAgentData.name);
          return self.loadAgents();
        }).catch(function (e) {
          Alpine.store('notify').error(e.message);
        }).finally(function () {
          self.savingAgent = false;
        });
      },

      // ── Delete agent ──
      deleteAgent: function (name) {
        if (!confirm(this.__('confirm.deleteAgent') + ' "' + name + '"?')) return;

        var self = this;
        Alpine.store('api').del('/api/agents/' + encodeURIComponent(name)).then(function () {
          Alpine.store('notify').success('Agent "' + name + '" deleted');
          Alpine.store('events').emit('agents:deleted', name);
          return self.loadAgents();
        }).catch(function (e) {
          Alpine.store('notify').error(e.message);
        });
      },
    };
  },
};
