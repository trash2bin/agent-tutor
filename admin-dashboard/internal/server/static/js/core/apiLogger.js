// apiLogger — Alpine store для лога всех HTTP запросов
// Содержит:
//   entries[] — последние 50 запросов
//   showPanel — флаг отображения debug панели
//   selectedEntry — выбранный запрос для просмотра тела
//   apiToasts[] — всплывающие уведомления о запросах

document.addEventListener('alpine:init', function () {
  Alpine.store('apiLogger', {
    entries: [],
    apiToasts: [],
    showPanel: false,
    selectedEntry: null,
    _toastCounter: 0,

    // Вызывается из apiClient.js после каждого запроса
    _push: function (entry) {
      // Добавляем в общий лог
      this.entries = [entry].concat(this.entries).slice(0, 50);

      // Показываем toast-уведомление для мутаций (PUT, POST, DELETE)
      if (entry.method !== 'GET') {
        this._showApiToast(entry);
      }
    },

    // Toast-уведомление о выполненном запросе
    _showApiToast: function (entry) {
      var id = ++this._toastCounter;
      var isOk = entry.status >= 200 && entry.status < 300;
      var icon = isOk ? '✓' : '✗';
      var colorClass = isOk ? 'api-toast-ok' : 'api-toast-err';

      this.apiToasts.push({
        id: id,
        text: icon + ' [' + entry.status + '] ' + entry.method + ' ' + entry.path,
        class: colorClass,
        entryId: entry.id,
      });

      // Авто-удаление через 4 секунды
      var self = this;
      setTimeout(function () {
        self.apiToasts = self.apiToasts.filter(function (t) {
          return t.id !== id;
        });
      }, 4000);
    },

    // Закрыть toast
    dismissToast: function (id) {
      this.apiToasts = this.apiToasts.filter(function (t) {
        return t.id !== id;
      });
    },

    // Toggle debug панели
    togglePanel: function () {
      this.showPanel = !this.showPanel;
    },

    // Выбрать запрос для просмотра деталей
    selectEntry: function (id) {
      for (var i = 0; i < this.entries.length; i++) {
        if (this.entries[i].id === id) {
          this.selectedEntry = this.entries[i];
          return;
        }
      }
    },

    closeDetail: function () {
      this.selectedEntry = null;
    },

    // Догнать запросы, выполненные до загрузки Alpine
    _catchUp: function () {
      if (window.__apiLog && window.__apiLog.length > 0) {
        var _self = this;
        for (var i = window.__apiLog.length - 1; i >= 0; i--) {
          var e = window.__apiLog[i];
          var found = false;
          for (var j = 0; j < this.entries.length; j++) {
            if (this.entries[j].id === e.id) { found = true; break; }
          }
          if (!found) {
            // register in entries, but don't toast (they're page-load calls)
            this.entries = [e].concat(this.entries).slice(0, 50);
          }
        }
      }
    },
  });

  // Catch up with requests that happened before Alpine loaded
  Alpine.store('apiLogger')._catchUp();
});
