// EventBus — cross-domain pub/sub
// Использование:
//   Alpine.store('events').on('config:saved', function(data) { ... })
//   Alpine.store('events').emit('config:saved', { id: 'autoparts' })
//   Alpine.store('events').off('config:saved', fn)

document.addEventListener('alpine:init', function () {
  Alpine.store('events', {
    _listeners: {},

    on: function (event, fn) {
      if (!this._listeners[event]) {
        this._listeners[event] = [];
      }
      this._listeners[event].push(fn);
    },

    off: function (event, fn) {
      if (!this._listeners[event]) return;
      if (!fn) {
        delete this._listeners[event];
        return;
      }
      this._listeners[event] = this._listeners[event].filter(function (f) {
        return f !== fn;
      });
    },

    emit: function (event, data) {
      var fns = this._listeners[event];
      if (!fns) return;
      for (var i = 0; i < fns.length; i++) {
        try {
          fns[i](data);
        } catch (e) {
          console.error('[eventBus] Error in handler for "' + event + '":', e);
        }
      }
    },
  });
});
