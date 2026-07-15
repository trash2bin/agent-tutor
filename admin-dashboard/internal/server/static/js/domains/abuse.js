// Anti-Abuse domain module
// Контракты: api.openapi.yaml (GET/PUT /api/abuse-settings, GET/PUT /api/agents/{name}/abuse)
//            admin-contracts.json (POST /api/admin/abuse-config/reload)

window.Abuse = {
  state: {
    abuseTab: 'global',
    abuseGlobal: {
      rps: null,
      burst: null,
      max_message_length: null,
      min_interval_ms: null,
      max_messages_per_session: null,
      token_budget: null,
      block_empty_user_agent: null,
      blocked_user_agents: [],
      _ua_text: '',
      history_turns: null,
      history_content_chars: null,
      max_iterations: null,
      max_empty_rounds: null,
      max_turn_tokens: null,
      session_ttl_hours: null,
    },
    abuseAgent: null,
    abuseAgentName: '',
    abuseAgentOverrides: {},
    abuseSaving: false,
    abuseSaveMsg: '',
    abuseReloading: false,
    abuseReloadMsg: '',
    abuseAgentList: [],
  },

  methods: function () {
    return {
      loadAbuseSettings: async function () {
        try {
          var resp = await Alpine.store('api').get('/api/abuse-settings');
          this.abuseGlobal = resp;
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      saveAbuseGlobal: async function () {
        this.abuseSaving = true;
        this.abuseSaveMsg = '';
        try {
          await Alpine.store('api').put('/api/abuse-settings', this.abuseGlobal);
          Alpine.store('notify').success('Abuse settings saved');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.abuseSaving = false;
        }
      },

      reloadAbuseOnApi: async function () {
        this.abuseReloading = true;
        this.abuseReloadMsg = '';
        try {
          await Alpine.store('api').post('/api/admin/abuse-config/reload');
          Alpine.store('notify').success('Abuse config reloaded');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.abuseReloading = false;
        }
      },

      selectAbuseAgent: async function (name) {
        this.abuseAgentName = name;
        try {
          var resp = await Alpine.store('api').get('/api/agents/' + name + '/abuse');
          this.abuseAgent = resp;
        } catch (e) {
          this.abuseAgent = null;
          Alpine.store('notify').error(e.message);
        }
      },

      saveAbuseAgent: async function () {
        this.abuseSaving = true;
        try {
          await Alpine.store('api').put('/api/agents/' + this.abuseAgentName + '/abuse', this.abuseAgent);
          Alpine.store('notify').success('Agent abuse settings saved');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.abuseSaving = false;
        }
      },
    };
  },
};
