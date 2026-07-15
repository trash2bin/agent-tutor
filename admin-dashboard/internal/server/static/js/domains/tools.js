// Tools — MCP tools approval & manifest
// Использование:
//   В app.js init(): Object.assign(this, window.Tools.methods())
window.Tools = {
  state: {
    pendingTools: { tools: [], mode: 'read_only' },
    manifest: null,
  },

  methods: function () {
    return {
      loadPendingTools: async function (tenantId) {
        if (!tenantId) return;
        try {
          this.pendingTools = await Alpine.store('api').get('/api/tenants/' + tenantId + '/tools/pending');
        } catch (e) {
          this.pendingTools = null;
          Alpine.store('notify').error(e.message);
        }
      },

      loadManifest: async function (tenantId) {
        if (!tenantId) return;
        try {
          this.manifest = await Alpine.store('api').get('/api/tenants/' + tenantId + '/manifest');
        } catch (e) {
          this.manifest = null;
        }
      },

      approveTool: async function (tenantId, toolName) {
        if (!tenantId || !toolName) return;
        try {
          await Alpine.store('api').post('/api/tenants/' + tenantId + '/tools/' + toolName + '/approve');
          Alpine.store('notify').success('Tool approved: ' + toolName);
          await this.loadPendingTools(tenantId);
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      findEndpoint: function (endpointPath) {
        var eps = (this.manifest && this.manifest.endpoints) || null;
        if (!eps) return null;
        for (var i = 0; i < eps.length; i++) {
          if (eps[i].path === endpointPath) {
            return eps[i];
          }
        }
        return null;
      },

      // saveToolDisplayNames — мерджит display_name из manifest в config.mcp_tools
      // tenantId, config — нужны т.к. config.js теперь отдельный домен
      // callback fn — например saveConfig из домена config
      saveToolDisplayNames: async function (tenantId, config, saveConfigFn) {
        if (!tenantId || !this.manifest || !this.manifest.mcp_tools) return;
        if (!config) config = {};
        if (!config.mcp_tools) {
          config.mcp_tools = [];
        }

        for (var i = 0; i < this.manifest.mcp_tools.length; i++) {
          var mt = this.manifest.mcp_tools[i];
          var found = null;
          for (var j = 0; j < config.mcp_tools.length; j++) {
            if (config.mcp_tools[j].name === mt.name) {
              found = config.mcp_tools[j];
              break;
            }
          }
          if (found) {
            found.display_name = mt.display_name || '';
          } else {
            config.mcp_tools.push({
              name: mt.name,
              endpoint: mt.endpoint,
              description: mt.description,
              params: mt.params || [],
              display_name: mt.display_name || '',
            });
          }
        }

        if (typeof saveConfigFn === 'function') {
          try {
            await saveConfigFn(config);
            Alpine.store('notify').success('Display names saved');
          } catch (e) {
            Alpine.store('notify').error(e.message);
          }
        }
      },
    };
  },
};
