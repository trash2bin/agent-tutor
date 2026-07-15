// RAG — health, documents, settings
// Использование:
//   В app.js init(): Object.assign(this, window.RAG.methods())
window.RAG = {
  state: {
    ragHealth: {},
    ragHealthData: null,
    ragDocs: [],
    ragDocsCount: 0,
    ragImport: { title: '', discipline_id: '' },
    ragUploadFile: null,
    ragImporting: false,
    ragImportResult: null,
    ragSettings: {
      embedding_provider: '',
      embedding_model: '',
      embedding_api_key: '',
      embedding_api_base: '',
      embedding_dimensions: 1536,
      chunker_type: 'recursive',
      chunk_size: 768,
      chunk_overlap: 160,
      reranker_enabled: false,
      reranker_k1: 1.5,
      reranker_b: 0.75,
      cache_enabled: false,
      cache_ttl: 300,
      cache_maxsize: 256,
    },
    ragStats: null,
    ragSettingsLoading: false,
    ragSettingsSaving: false,
    ragSettingsSaveMsg: '',
    ragStatsLoading: false,
    ragTab: 'docs',
  },

  methods: function () {
    return {
      refreshRag: async function () {
        try {
          this.ragHealth = await Alpine.store('api').get('/api/rag/health');
        } catch (e) {
          this.ragHealth = { status: 'error', error: e.message };
        }
        try {
          var docsResp = await Alpine.store('api').post('/api/rag/documents/list', { limit: 100 });
          this.ragDocs = docsResp.documents || [];
          this.ragDocsCount = docsResp.count != null ? docsResp.count : this.ragDocs.length;
        } catch (e) {
          this.ragDocs = [];
          this.ragDocsCount = 0;
        }
      },

      loadRagSettings: async function () {
        this.ragSettingsLoading = true;
        this.ragSettingsSaveMsg = '';
        try {
          this.ragSettings = await Alpine.store('api').get('/api/rag/config');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.ragSettingsLoading = false;
        }
      },

      loadRagStats: async function () {
        this.ragStatsLoading = true;
        try {
          this.ragStats = await Alpine.store('api').get('/api/rag/stats');
        } catch (e) {
          Alpine.store('notify').error(e.message);
        } finally {
          this.ragStatsLoading = false;
        }
      },

      saveRagSettings: async function () {
        this.ragSettingsSaving = true;
        this.ragSettingsSaveMsg = '';
        try {
          await Alpine.store('api').put('/api/rag/config', this.ragSettings);
          this.ragSettingsSaveMsg = 'saved';
          Alpine.store('notify').success('RAG settings saved');
          var self = this;
          setTimeout(function () { self.ragSettingsSaveMsg = ''; }, 3000);
        } catch (e) {
          this.ragSettingsSaveMsg = 'error';
          Alpine.store('notify').error(e.message);
        } finally {
          this.ragSettingsSaving = false;
        }
      },

      ragDropFile: function (event) {
        var dt = event.dataTransfer;
        var file = dt && dt.files && dt.files[0];
        if (file) {
          this.ragUploadFile = file;
        }
      },

      uploadRagDoc: async function () {
        if (!this.ragUploadFile) return;
        this.ragImporting = true;
        this.ragImportResult = null;
        try {
          var fd = new FormData();
          fd.append('file', this.ragUploadFile);
          if (this.ragImport.title) fd.append('title', this.ragImport.title);
          if (this.ragImport.discipline_id) fd.append('discipline_id', this.ragImport.discipline_id);

          var token = localStorage.getItem('admin_token');
          var headers = {};
          if (token) headers['Authorization'] = 'Bearer ' + token;

          // Raw fetch (not Alpine.store('api')) — multipart/form-data can't go through JSON client
          var res = await fetch('/api/rag/documents/upload', {
            method: 'POST',
            headers: headers,
            body: fd,
          });
          var result = await res.json();
          if (!res.ok) {
            this.ragImportResult = { error: result.message || result.error || res.statusText };
            Alpine.store('notify').error(this.ragImportResult.error);
          } else {
            this.ragImportResult = result;
            this.ragUploadFile = null;
            this.ragImport = { title: '', discipline_id: '' };
            Alpine.store('notify').success('Document uploaded');
            await this.refreshRag();
          }
        } catch (e) {
          this.ragImportResult = { error: e.message };
          Alpine.store('notify').error(e.message);
        } finally {
          this.ragImporting = false;
        }
      },

      deleteRagDoc: async function (doc) {
        var docId = doc.id || doc.document_id;
        var docPath = doc.source_path || doc.path;
        var docName = doc.title || docId;
        if (!confirm('Delete document "' + docName + '"?')) return;
        try {
          var body = docId ? { document_id: docId } : { path: docPath };
          await Alpine.store('api').post('/api/rag/documents/delete', body);
          Alpine.store('notify').success('Document deleted');
          await this.refreshRag();
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },
    };
  },
};
