// Voice Config domain — STT/TTS providers management
// window.Voice = { state, methods }
// state: плоский объект (мерджится в dashboard state)
// methods: function() → объект методов (инжектится в dashboard через Object.assign)

window.Voice = {
  state: {
    voiceConfig: {
      enabled: true,
      stt_providers: [],
      tts_providers: [],
      stt_fallback_enabled: true,
      tts_fallback_enabled: true,
      max_voice_message_size: 10485760,
      min_voice_interval_seconds: 10,
      max_voice_duration_seconds: 120,
    },
    voiceError: '',
    voiceSaveMsg: '',
    voiceSaveSuccess: false,
    voiceSaving: false,
    showAddSttProvider: false,
    showAddTtsProvider: false,
    editingSttIndex: -1,
    editingTtsIndex: -1,
    voiceSttForm: {
      name: '',
      provider: 'litellm',
      model: 'whisper-1',
      api_key: '',
      api_base: '',
      enabled: true,
    },
    voiceTtsForm: {
      name: '',
      provider: 'litellm',
      model: 'tts-1',
      voice: 'alloy',
      api_key: '',
      api_base: '',
      enabled: true,
    },
  },

  methods: function () {
    return {
      // ── Load ──
      loadVoiceConfig: async function () {
        this.voiceError = '';
        try {
          this.voiceConfig = await Alpine.store('api').get('/api/voice-config');
          Alpine.store('events').emit('voice:loaded', this.voiceConfig);
        } catch (e) {
          var msg = e.message || 'Failed to load voice config';
          this.voiceError = msg;
          Alpine.store('notify').error(msg);
        }
      },

      // ── Save ──
      saveVoiceConfig: async function () {
        this.voiceSaving = true;
        this.voiceSaveMsg = '';
        this.voiceSaveSuccess = false;
        try {
          await Alpine.store('api').put('/api/voice-config', this.voiceConfig);
          this.voiceSaveMsg = this.__('msg.saved');
          this.voiceSaveSuccess = true;
          Alpine.store('notify').success(this.__('msg.saved'));
          var self = this;
          setTimeout(function () { self.voiceSaveMsg = ''; }, 3000);
          await this.loadVoiceConfig();
          Alpine.store('events').emit('voice:saved', this.voiceConfig);
        } catch (e) {
          var msg = e.message || this.__('msg.failed');
          this.voiceSaveMsg = msg;
          this.voiceSaveSuccess = false;
          Alpine.store('notify').error(msg);
        } finally {
          this.voiceSaving = false;
        }
      },

      // ── Form reset ──
      cancelVoiceEdit() {
        this.showAddSttProvider = false;
        this.showAddTtsProvider = false;
        this.editingSttIndex = -1;
        this.editingTtsIndex = -1;
        this.voiceSttForm = { name: '', provider: 'litellm', model: 'whisper-1', api_key: '', api_base: '', enabled: true };
        this.voiceTtsForm = { name: '', provider: 'litellm', model: 'tts-1', voice: 'alloy', api_key: '', api_base: '', enabled: true };
      },

      // ── STT Provider CRUD ──
      editSttProvider(idx) {
        var prov = this.voiceConfig && this.voiceConfig.stt_providers && this.voiceConfig.stt_providers[idx];
        if (!prov) return;
        this.editingSttIndex = idx;
        this.showAddSttProvider = true;
        this.showAddTtsProvider = false;
        this.voiceSttForm = {
          name: prov.name,
          provider: prov.provider,
          model: prov.model,
          api_key: prov.api_key || '',
          api_base: prov.api_base || '',
          enabled: prov.enabled !== false,
        };
      },

      deleteSttProvider(idx) {
        if (!confirm(this.__('voice.deleteConfirmMsg') + '?')) return;
        if (!this.voiceConfig || !this.voiceConfig.stt_providers) return;
        this.voiceConfig.stt_providers.splice(idx, 1);
        this.saveVoiceConfig();
      },

      saveSttProvider() {
        if (!this.voiceConfig) return;
        if (!this.voiceConfig.stt_providers) this.voiceConfig.stt_providers = [];
        var body = {
          name: this.voiceSttForm.name,
          provider: this.voiceSttForm.provider,
          model: this.voiceSttForm.model,
          api_key: this.voiceSttForm.api_key || '',
          api_base: this.voiceSttForm.api_base || '',
          enabled: this.voiceSttForm.enabled,
        };
        if (this.editingSttIndex >= 0 && this.editingSttIndex < this.voiceConfig.stt_providers.length) {
          this.voiceConfig.stt_providers[this.editingSttIndex] = body;
        } else {
          this.voiceConfig.stt_providers.push(body);
        }
        this.cancelVoiceEdit();
        this.saveVoiceConfig();
      },

      // ── TTS Provider CRUD ──
      editTtsProvider(idx) {
        var prov = this.voiceConfig && this.voiceConfig.tts_providers && this.voiceConfig.tts_providers[idx];
        if (!prov) return;
        this.editingTtsIndex = idx;
        this.showAddTtsProvider = true;
        this.showAddSttProvider = false;
        this.voiceTtsForm = {
          name: prov.name,
          provider: prov.provider,
          model: prov.model,
          voice: prov.voice || 'alloy',
          api_key: prov.api_key || '',
          api_base: prov.api_base || '',
          enabled: prov.enabled !== false,
        };
      },

      deleteTtsProvider(idx) {
        if (!confirm(this.__('voice.deleteConfirmMsg') + '?')) return;
        if (!this.voiceConfig || !this.voiceConfig.tts_providers) return;
        this.voiceConfig.tts_providers.splice(idx, 1);
        this.saveVoiceConfig();
      },

      saveTtsProvider() {
        if (!this.voiceConfig) return;
        if (!this.voiceConfig.tts_providers) this.voiceConfig.tts_providers = [];
        var body = {
          name: this.voiceTtsForm.name,
          provider: this.voiceTtsForm.provider,
          model: this.voiceTtsForm.model,
          voice: this.voiceTtsForm.voice || 'alloy',
          api_key: this.voiceTtsForm.api_key || '',
          api_base: this.voiceTtsForm.api_base || '',
          enabled: this.voiceTtsForm.enabled,
        };
        if (this.editingTtsIndex >= 0 && this.editingTtsIndex < this.voiceConfig.tts_providers.length) {
          this.voiceConfig.tts_providers[this.editingTtsIndex] = body;
        } else {
          this.voiceConfig.tts_providers.push(body);
        }
        this.cancelVoiceEdit();
        this.saveVoiceConfig();
      },
    };
  },
};
