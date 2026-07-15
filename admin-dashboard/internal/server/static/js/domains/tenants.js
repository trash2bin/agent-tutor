// Tenants — tenant CRUD
// Контракт: admin-endpoints.json (Go proxy)

window.Tenants = {
  state: {
    tenants: [],
    selectedTenant: '',
    showNewTenantForm: false,
    newTenant: { tenant_id: '', driver: 'sqlite3', dsn: '' },
    newTenantUploadFile: null,
    creating: false,
    createResult: null,
  },

  methods: function () {
    return {
      loadTenants: async function () {
        try {
          var resp = await Alpine.store('api').get('/api/tenants');
          this.tenants = resp.tenants || [];
        } catch (e) {
          // error handled in apiClient
        }
      },

      selectTenant: async function (id) {
        this.selectedTenant = id;
        Alpine.store('ui').page = 'config';
        Alpine.store('events').emit('tenant:selected', { id: id });
      },

      deleteTenant: async function (id) {
        if (!confirm(window.__('confirm.deleteTenant') + ' "' + id + '"?')) return;
        try {
          await Alpine.store('api').del('/api/tenants/' + id);
          await this.loadTenants();
          if (this.selectedTenant === id) {
            this.selectedTenant = '';
            this.config = {};
            this.pendingTools = null;
          }
          Alpine.store('notify').success('Tenant "' + id + '" deleted');
          Alpine.store('events').emit('tenant:deleted', { id: id });
        } catch (e) {
          Alpine.store('notify').error(e.message);
        }
      },

      createTenantWithUpload: async function () {
        this.creating = true;
        this.createResult = null;
        try {
          if (this.newTenant.driver === 'sqlite3' && this.newTenantUploadFile) {
            var fd = new FormData();
            fd.append('file', this.newTenantUploadFile);
            fd.append('tenant_id', this.newTenant.tenant_id);
            fd.append('driver', 'sqlite3');

            var token = localStorage.getItem('admin_token');
            var headers = {};
            if (token) headers['Authorization'] = 'Bearer ' + token;

            var res = await fetch('/api/tenants/upload-sqlite', {
              method: 'POST',
              headers: headers,
              body: fd,
            });
            this.createResult = await res.json();
            if (!res.ok) {
              this.createResult = { error: this.createResult.message || this.createResult.error || res.statusText };
            }
          } else {
            this.createResult = await Alpine.store('api').post('/api/tenants', this.newTenant);
          }
          this.showNewTenantForm = false;
          this.newTenant = { tenant_id: '', driver: 'sqlite3', dsn: '' };
          this.newTenantUploadFile = null;
          await this.loadTenants();
          await this.refreshDashboard();
        } catch (e) {
          this.createResult = { error: e.message };
        } finally {
          this.creating = false;
        }
      },
    };
  },
};
