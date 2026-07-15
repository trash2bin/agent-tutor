// Emergency Panel domain module
// Контракты: admin-contracts.json (GET /api/emergency-status, POST /api/abuse-preset/{preset})

window.Emergency = {
  state: {
    emergencyStatus: {
      rps: null,
      burst: null,
      token_budget: null,
      max_messages: null,
      min_interval_ms: null,
    },
    emergencyActive: false,
    emergencyCurrentPreset: 'normal',
    emergencyApplying: false,
    emergencyTimer: null,
    emergencyConflicting: false,
  },

  methods: function () {
    return {
      loadEmergencyStatus: async function () {
        try {
          var resp = await Alpine.store('api').get('/api/emergency-status');
          this.emergencyStatus = resp;
          this.emergencyCurrentPreset = resp.current_preset || 'normal';
          this.emergencyActive = resp.current_preset === 'lockdown';
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      applyEmergencyPreset: async function (preset) {
        this.emergencyApplying = true;
        try {
          await Alpine.store('api').post('/api/abuse-preset/' + preset);
          this.emergencyCurrentPreset = preset;
          this.emergencyActive = preset === 'lockdown';
          Alpine.store('notify').success('Emergency preset: ' + preset);
          Alpine.store('events').emit('emergency:preset-changed', preset);
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.emergencyApplying = false;
        }
      },

      toggleEmergencyMode: function () {
        if (this.emergencyCurrentPreset === 'lockdown') {
          this.applyEmergencyPreset('normal');
        } else {
          this.applyEmergencyPreset('lockdown');
        }
      },
    };
  },
};
