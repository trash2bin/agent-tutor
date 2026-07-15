// Notify — toast-уведомления
// Использование:
//   Alpine.store('notify').success('Сохранено!')
//   Alpine.store('notify').error('Ошибка: ...')
//   Alpine.store('notify').warn('Внимание: ...')
//
// В шаблоне:
//   <template x-for="n in $store.notify.items" :key="n.id">
//     <div x-text="n.text" :class="'toast toast-' + n.type"></div>
//   </template>

document.addEventListener('alpine:init', function () {
  Alpine.store('notify', {
    items: [],
    _counter: 0,

    success: function (msg) {
      this._add(msg, 'success', 3000);
    },

    error: function (msg) {
      this._add(msg, 'error', 5000);
    },

    warn: function (msg) {
      this._add(msg, 'warn', 4000);
    },

    _add: function (text, type, ttl) {
      var id = ++this._counter;
      var item = { id: id, text: text, type: type };
      this.items.push(item);

      if (ttl > 0) {
        var self = this;
        setTimeout(function () {
          self.items = self.items.filter(function (i) {
            return i.id !== id;
          });
        }, ttl);
      }
    },

    clear: function () {
      this.items = [];
    },
  });
});
