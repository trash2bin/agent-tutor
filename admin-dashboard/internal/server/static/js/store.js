document.addEventListener('alpine:init', function () {
  Alpine.store('api', {
    get: function (path) { return window.apiClient.get(path); },
    put: function (path, data) { return window.apiClient.put(path, data); },
    post: function (path, data) { return window.apiClient.post(path, data); },
    del: function (path) { return window.apiClient.del(path); },
  });

  Alpine.store('ui', {
    tokenSet: !!localStorage.getItem('admin_token'),
    role: localStorage.getItem('admin_role') || '',
    tokenInput: '',
    page: 'dashboard',
    error: '',
    loading: false,
    dataService: '',
    isViewer: function () { return this.role === 'viewer'; },
    isAdmin: function () { return this.role === 'admin'; },

    login: function () {
      var token = this.tokenInput.trim();
      if (!token) return;
      localStorage.setItem('admin_token', token);
      this.tokenSet = true;
      this.error = '';

      // Fetch role from dashboard endpoint
      var self = this;
      window.apiClient.get('/api/dashboard').then(function (data) {
        self.role = data.role || 'admin';
        localStorage.setItem('admin_role', self.role);
        document.documentElement.dataset.role = self.role;
      }).catch(function (err) {
        self.role = 'admin';
        localStorage.setItem('admin_role', 'admin');
        document.documentElement.dataset.role = 'admin';
      });
    },

    logout: function () {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_role');
      delete document.documentElement.dataset.role;
      location.reload();
    },

    navigate: function (pageName) {
      this.page = pageName;
    },
  });
});
