document.addEventListener('alpine:init', function () {
  Alpine.store('api', {
    get: function (path) { return window.apiClient.get(path); },
    put: function (path, data) { return window.apiClient.put(path, data); },
    post: function (path, data) { return window.apiClient.post(path, data); },
    del: function (path) { return window.apiClient.del(path); },
  });

  Alpine.store('ui', {
    tokenSet: !!localStorage.getItem('admin_token'),
    tokenInput: '',
    page: 'dashboard',
    error: '',
    loading: false,
    dataService: '',

    login: function () {
      var token = this.tokenInput.trim();
      if (!token) return;
      localStorage.setItem('admin_token', token);
      this.tokenSet = true;
      this.error = '';
    },

    logout: function () {
      localStorage.removeItem('admin_token');
      location.reload();
    },

    navigate: function (pageName) {
      this.page = pageName;
    },
  });
});
