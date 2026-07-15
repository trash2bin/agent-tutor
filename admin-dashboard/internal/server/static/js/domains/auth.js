// Auth — login/logout, token management
// Контракт: localStorage only (no backend endpoints)

window.Auth = {
  state: {
    tokenSet: !!localStorage.getItem('admin_token'),
    tokenInput: '',
  },

  methods: function () {
    return {
      login: function () {
        var token = this.tokenInput.trim();
        if (!token) {
          Alpine.store('notify').error(window.__('error.enterToken'));
          return;
        }
        localStorage.setItem('admin_token', token);
        this.tokenSet = true;
        this.init();
      },

      logout: function () {
        localStorage.removeItem('admin_token');
        location.reload();
      },
    };
  },
};
