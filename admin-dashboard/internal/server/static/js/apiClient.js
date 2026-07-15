(function () {
  'use strict';

  function getToken() { return localStorage.getItem('admin_token'); }

  // ── API Logger ──
  window.__apiLog = [];
  var _logId = 0;

  function logEntry(method, path, status, resBody, reqBody, durationMs) {
    var entry = {
      id: ++_logId,
      method: method,
      path: path,
      status: status,
      reqBody: reqBody,
      resBody: typeof resBody === 'string' ? resBody : JSON.stringify(resBody, null, 2),
      durationMs: durationMs,
      ts: new Date().toISOString(),
    };
    window.__apiLog.push(entry);
    if (window.__apiLog.length > 50) window.__apiLog.shift();

    // Push to Alpine store (if loaded)
    if (typeof Alpine !== 'undefined' && Alpine.store('apiLogger')) {
      Alpine.store('apiLogger')._push(entry);
    }
  }

  async function request(path, options) {
    options = options || {};
    var method = (options.method || 'GET').toUpperCase();
    var reqBody = options.body || null;
    var start = performance.now();

    var headers = { 'Content-Type': 'application/json' };
    var token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;

    var res, body;
    try {
      res = await fetch(path, Object.assign({}, options, { headers: headers }));
    } catch (netErr) {
      var dur = Math.round(performance.now() - start);
      logEntry(method, path, 0, netErr.message, reqBody, dur);
      throw new Error('Network error: ' + netErr.message);
    }

    if (res.status === 401) {
      var dur = Math.round(performance.now() - start);
      logEntry(method, path, 401, 'Unauthorized', reqBody, dur);
      throw new Error('Unauthorized');
    }

    var contentType = res.headers.get('content-type') || '';
    if (contentType.indexOf('application/json') !== -1) {
      try {
        body = await res.json();
      } catch (_jsonErr) {
        var text = await res.text();
        body = text ? { error: text } : {};
      }
    } else {
      var text = await res.text();
      body = text ? { error: text } : {};
    }

    var dur = Math.round(performance.now() - start);

    if (!res.ok) {
      var msg = body.message || body.error || res.statusText;
      if (body.detail && Array.isArray(body.detail)) {
        var d = body.detail[0];
        msg = d.msg || msg;
        if (d.input !== undefined) msg += ' (got: ' + JSON.stringify(d.input) + ')';
      } else if (body.detail && typeof body.detail === 'string') {
        msg = body.detail;
      }
      logEntry(method, path, res.status, body, reqBody, dur);
      throw new Error(msg);
    }

    logEntry(method, path, res.status, body, reqBody, dur);
    return body;
  }

  window.apiClient = {
    get: function (path) { return request(path); },
    put: function (path, data) { return request(path, { method: 'PUT', body: JSON.stringify(data) }); },
    post: function (path, data) {
      var opts = { method: 'POST' };
      if (data !== undefined) opts.body = JSON.stringify(data);
      return request(path, opts);
    },
    del: function (path) { return request(path, { method: 'DELETE' }); },
  };
})();
