/**
 * Helperium — Embeddable Chat Widget
 * ======================================
 * Vanilla JS, no dependencies. Shadow DOM isolation.
 *
 * Usage:
 *   <script src="/embed/embed.js"
 *           data-agent="support-agent"
 *           data-api-base="https://your-server.com"
 *           data-title="Assistant"
 *           data-greeting="How can I help?"
 *           data-accent="#0f766e"
 *           data-position="right">
 *   </script>
 *
 * SSE endpoint: POST {api-base}/api/chat/{agent}
 * Body: {"message": "...", "session_id": "..."}
 * Response: text/event-stream with data: {json} events
 */
(function () {
  'use strict';

  /* ─── Configuration ─── */
  var script = document.currentScript;
  if (!script) {
    script = document.querySelector('script[data-agent]');
  }
  if (!script) return;

  var CONFIG = {
    agent: script.getAttribute('data-agent') || '',
    apiBase: script.getAttribute('data-api-base') || window.location.origin,
    title: script.getAttribute('data-title') || 'Assistant',
    greeting: script.getAttribute('data-greeting') || 'How can I help?',
    accent: script.getAttribute('data-accent') || '#0f766e',
    position: script.getAttribute('data-position') === 'left' ? 'left' : 'right',
    lang: script.getAttribute('data-lang') || (navigator.language.startsWith('ru') ? 'ru' : 'en'),
    placeholder: script.getAttribute('data-placeholder') || 'Ask a question...',
    width: script.getAttribute('data-width') || 'min(380px, calc(100vw - 28px))',
    height: script.getAttribute('data-height') || 'min(620px, calc(100vh - 44px))',
    triggerOffsetBottom: script.getAttribute('data-trigger-offset-bottom') || '16px',
    headerColor: script.getAttribute('data-header-color') || '',
    showHeader: script.getAttribute('data-show-header') !== 'false',
    botBubbleColor: script.getAttribute('data-bot-bubble-color') || '#eef3f4',
    botBubbleText: script.getAttribute('data-bot-bubble-text') || 'var(--ink)',
    voiceInput: script.getAttribute('data-voice-input') !== 'false',
    voiceOutput: script.getAttribute('data-voice-output') !== 'false'
  };

  if (!CONFIG.agent) {
    console.error('[Helperium Widget] Missing data-agent attribute');
    return;
  }

  /* ─── Global API bridge: allows app.js to switch agent at runtime ─── */
  window.__agentTutorSetAgent = null;
  /* ─── State ─── */
  var state = {
    sessionId: null,
    open: false,
    messages: []
  };
  var STORAGE_KEY = 'at_messages_' + CONFIG.agent;
  var SESSION_KEY = 'at_session_' + CONFIG.agent;

  /* ─── CSS (embedded for Shadow DOM) ─── */
  function getWidgetCSS(cfg) {
    var headerBg = cfg.headerColor || cfg.accent;
    var headDisplay = cfg.showHeader ? '' : 'display: none;';
    return [
    ':host {',
    '  all: initial;',
    '  --accent: ' + cfg.accent + ';',
    '  --accent-strong: ' + cfg.accent + ';',
    '  --ink: #1e293b;',
    '  --ink-light: #475569;',
    '  --muted: #94a3b8;',
    '  --line: #e2e8f0;',
    '  --panel: #ffffff;',
    '  --rose: #e11d48;',
    '  --blue: #2563eb;',
    '  --shadow-panel: 0 20px 60px rgba(23, 32, 38, 0.18);',
    '  --shadow-trigger: 0 4px 16px rgba(15, 118, 110, 0.35);',
    '  --radius: 10px;',
    '  --radius-lg: 14px;',
    '  --trigger-offset-bottom: ' + cfg.triggerOffsetBottom + ';',
    '  --panel-width: ' + cfg.width + ';',
    '  --panel-height: ' + cfg.height + ';',
    '  --header-bg: ' + headerBg + ';',
    '  --bot-bubble-bg: ' + cfg.botBubbleColor + ';',
    '  --bot-bubble-text: ' + cfg.botBubbleText + ';',
    '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;',
    '}',
    '',
    '.at-root {',
    '  all: initial;',
    '  display: block;',
    '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;',
    '  font-size: 14px;',
    '  line-height: 1.45;',
    '  color: #1e293b;',
    '}',
    '',
    /* ── Trigger Button ── */
    '.at-trigger {',
    '  position: fixed;',
    '  bottom: var(--trigger-offset-bottom);',
    '  width: 56px;',
    '  height: 56px;',
    '  border: 0;',
    '  border-radius: 50%;',
    '  background: var(--accent);',
    '  color: white;',
    '  cursor: pointer;',
    '  box-shadow: var(--shadow-trigger);',
    '  z-index: 2147483647;',
    '  font-size: 24px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s;',
    '  padding: 0;',
    '}',
    '.at-trigger::after {',
    '  content: "";',
    '  position: absolute;',
    '  inset: -3px;',
    '  border-radius: 50%;',
    '  background: var(--accent);',
    '  opacity: 0;',
    '  animation: at-pulse-ring 2.5s ease-out infinite;',
    '}',
    '@keyframes at-pulse-ring {',
    '  0% { transform: scale(1); opacity: 0.35; }',
    '  70% { transform: scale(1.35); opacity: 0; }',
    '  100% { transform: scale(1.35); opacity: 0; }',
    '}',
    '.at-trigger:hover { transform: scale(1.08) translateY(-1px); box-shadow: 0 6px 24px rgba(15, 118, 110, 0.45); }',
    '.at-trigger.at-right { right: var(--trigger-offset-bottom); }',
    '.at-trigger.at-left { left: var(--trigger-offset-bottom); }',
    '.at-trigger svg { width: 26px; height: 26px; position: relative; z-index: 1; }',
    '',
    /* ── Chat Panel ── */
    '.at-panel {',
    '  position: fixed;',
    '  bottom: var(--trigger-offset-bottom);',
    '  width: var(--panel-width);',
    '  height: var(--panel-height);',
    '  display: flex;',
    '  flex-direction: column;',
    '  overflow: hidden;',
    '  background: var(--panel);',
    '  border: 1px solid var(--line);',
    '  border-radius: var(--radius-lg);',
    '  box-shadow: var(--shadow-panel);',
    '  z-index: 2147483646;',
    '  transition: opacity 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);',
    '  transform-origin: bottom var(--position, right);',
    '}',
    '.at-panel.at-right { right: var(--trigger-offset-bottom); --position: right; }',
    '.at-panel.at-left { left: var(--trigger-offset-bottom); --position: left; }',
    '.at-panel.at-hidden {',
    '  opacity: 0;',
    '  transform: translateY(12px) scale(0.94);',
    '  pointer-events: none;',
    '}',
    '',
    /* ── Header ── */
    '.at-head {',
    '  display: flex;',
    '  justify-content: space-between;',
    '  gap: 12px;',
    '  align-items: center;',
    '  padding: 14px 14px 12px;',
    '  background: var(--header-bg);',
    '  color: white;',
    '  flex-shrink: 0;',
    '  ' + headDisplay,
    '}',
    '.at-head-info strong { display: block; font-size: 15px; font-weight: 600; }',
    '.at-head-info span { display: block; margin-top: 2px; font-size: 12px; opacity: 0.75; }',
    '.at-head-status {',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 5px;',
    '  margin-top: 2px;',
    '  font-size: 11px;',
    '  opacity: 0.85;',
    '}',
    '.at-head-status .at-dot {',
    '  width: 7px; height: 7px;',
    '  border-radius: 50%;',
    '  background: #22c55e;',
    '  animation: at-dot-pulse 2s ease-in-out infinite;',
    '}',
    '@keyframes at-dot-pulse {',
    '  0%, 100% { opacity: 1; transform: scale(1); }',
    '  50% { opacity: 0.5; transform: scale(0.85); }',
    '}',
    '.at-close {',
    '  width: 30px; height: 30px;',
    '  border: 0; border-radius: 50%;',
    '  background: rgba(255,255,255,0.18);',
    '  color: white;',
    '  cursor: pointer;',
    '  display: flex; align-items: center; justify-content: center;',
    '  flex-shrink: 0; padding: 0;',
    '  transition: background 0.15s;',
    '}',
    '.at-close:hover { background: rgba(255,255,255,0.3); }',
    '.at-close svg { width: 16px; height: 16px; }',
    '',
    /* ── Messages Area ── */
    '.at-messages {',
    '  flex: 1;',
    '  min-height: 0;',
    '  overflow-y: auto;',
    '  overflow-x: hidden;',
    '  padding: 14px;',
    '  display: flex;',
    '  flex-direction: column;',
    '  gap: 2px;',
    '}',
    '.at-messages::-webkit-scrollbar { width: 4px; }',
    '.at-messages::-webkit-scrollbar-track { background: transparent; }',
    '.at-messages::-webkit-scrollbar-thumb { background: var(--line); border-radius: 4px; }',
    '.at-messages::-webkit-scrollbar-thumb:hover { background: var(--muted); }',
    '',
    '.at-msg-row {',
    '  display: flex;',
    '  flex-direction: column;',
    '  align-items: flex-start;',
    '  margin-bottom: 4px;',
    '  animation: at-msg-in 0.22s ease-out;',
    '}',
    '',
    '.at-avatar {',
    '  width: 28px; height: 28px;',
    '  border-radius: 50%;',
    '  background: linear-gradient(135deg, var(--accent), var(--accent-strong));',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  color: white;',
    '  font-size: 10px;',
    '  font-weight: 700;',
    '  margin-left: 12px;',
    '  margin-top: -14px;',
    '  position: relative;',
    '  z-index: 1;',
    '  border: 2px solid var(--panel);',
    '}',
    '',
    /* ── Message Bubbles ── */
    '.at-msg {',
    '  min-width: 0;',
    '  max-width: 92%;',
    '  flex: 0 0 auto;',
    '  padding: 10px 13px;',
    '  font-size: 14px;',
    '  line-height: 1.45;',
    '  white-space: pre-wrap;',
    '  overflow-wrap: anywhere;',
    '  animation: at-msg-in 0.22s ease-out;',
    '}',
    '@keyframes at-msg-in {',
    '  from { opacity: 0; transform: translateY(6px); }',
    '  to { opacity: 1; transform: translateY(0); }',
    '}',
    '.at-msg.at-user {',
    '  align-self: flex-end;',
    '  background: var(--accent);',
    '  color: white;',
    '  border-radius: var(--radius) var(--radius) 4px var(--radius);',
    '  box-shadow: 0 1px 3px rgba(0,0,0,0.08);',
    '}',
    '.at-msg.at-assistant {',
    '  align-self: flex-start;',
    '  background: linear-gradient(135deg, var(--bot-bubble-bg), #f4f8fa);',
    '  color: var(--bot-bubble-text);',
    '  white-space: normal;',
    '  margin-top: -3px;',
    '  border-radius: var(--radius) var(--radius) var(--radius) 4px;',
    '  box-shadow: 0 1px 2px rgba(0,0,0,0.04);',
    '}',
    '.at-msg.at-assistant.at-thinking {',
    '  padding: 16px 18px 12px;',
    '  min-height: 36px;',
    '  display: flex;',
    '  align-items: center;',
    '}',
    '.at-msg.at-error { background: #fef2f2; color: var(--rose); border: 1px solid #fecaca; border-radius: var(--radius); }',
    '',
    /* ── Typing Dots ── */
    '.at-thinking-dots {',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 5px;',
    '}',
    '.at-thinking-dots span {',
    '  width: 8px; height: 8px;',
    '  border-radius: 50%;',
    '  background: var(--muted);',
    '  animation: at-dot-bounce 1.4s ease-in-out infinite both;',
    '}',
    '.at-thinking-dots span:nth-child(1) { animation-delay: -0.32s; }',
    '.at-thinking-dots span:nth-child(2) { animation-delay: -0.16s; }',
    '.at-thinking-dots span:nth-child(3) { animation-delay: 0s; }',
    '@keyframes at-dot-bounce {',
    '  0%, 80%, 100% { transform: translateY(0) scale(0.8); opacity: 0.4; }',
    '  40% { transform: translateY(-6px) scale(1); opacity: 0.8; }',
    '}',
    '',
    /* ── Typing Cursor ── */
    '.at-typing-cursor::after {',
    '  content: "\u258C";',
    '  display: inline;',
    '  animation: at-cursor-blink 0.8s step-end infinite;',
    '  color: var(--muted);',
    '  font-size: 14px;',
    '  margin-left: 1px;',
    '}',
    '@keyframes at-cursor-blink {',
    '  50% { opacity: 0; }',
    '}',
    '.at-msg.at-assistant p { margin: 0 0 5px; }',
    '.at-msg.at-assistant p:last-child, .at-msg.at-assistant ul:last-child, .at-msg.at-assistant ol:last-child { margin-bottom: 0; }',
    '.at-msg.at-assistant ul, .at-msg.at-assistant ol { margin: 0 0 10px; padding-left: 20px; }',
    '.at-msg.at-assistant li { margin: 3px 0; }',
    '.at-msg.at-assistant strong { font-weight: 750; }',
    '.at-msg.at-assistant code {',
    '  padding: 1px 5px;',
    '  border-radius: 5px;',
    '  background: rgba(15, 118, 110, 0.1);',
    '  color: var(--accent-strong);',
    '  font-size: 0.92em;',
    '}',
    '',
    /* ── Tool Strip ── */
    '.at-tool-strip {',
    '  align-self: flex-start;',
    '  max-width: 92%;',
    '  display: flex;',
    '  flex-wrap: wrap;',
    '  gap: 5px;',
    '  margin-bottom: 1px;',
    '  animation: at-msg-in 0.22s ease-out;',
    '}',
    '.at-tool-strip span {',
    '  display: inline-flex;',
    '  align-items: center;',
    '  min-height: 22px;',
    '  padding: 2px 9px;',
    '  border-radius: 999px;',
    '  background: linear-gradient(135deg, #eff6ff, #f0f9ff);',
    '  color: var(--blue);',
    '  font-size: 11px;',
    '  font-weight: 700;',
    '  letter-spacing: 0.01em;',
    '}',
    '',
    /* ── Markdown Table ── */
    '.at-table-wrap {',
    '  max-width: 100%;',
    '  overflow-x: auto;',
    '  margin: 8px 0 12px;',
    '  border: 1px solid var(--line);',
    '  border-radius: var(--radius);',
    '  background: white;',
    '}',
    '.at-table-wrap table { min-width: 520px; width: 100%; border-collapse: collapse; }',
    '.at-table-wrap th, .at-table-wrap td {',
    '  padding: 9px 10px;',
    '  border-bottom: 1px solid var(--line);',
    '  font-size: 12px;',
    '  line-height: 1.35;',
    '}',
    '.at-table-wrap th { background: #f9fbfb; color: var(--muted); font-weight: 600; text-align: left; }',
    '.at-table-wrap tr:last-child td { border-bottom: 0; }',
    '',
    /* ── Form ── */
    '.at-form {',
    '  padding: 6px 10px 10px;',
    '  border-top: 1px solid var(--line);',
    '  background: #fafbfc;',
    '  flex-shrink: 0;',
    '}',
    '.at-form-row {',
    '  display: flex;',
    '  gap: 6px;',
    '  align-items: flex-end;',
    '}',
    '.at-form textarea {',
    '  flex: 1;',
    '  resize: none;',
    '  min-height: 40px;',
    '  max-height: 120px;',
    '  border: 1px solid var(--line);',
    '  border-radius: 12px;',
    '  padding: 9px 12px;',
    '  font-family: inherit;',
    '  font-size: 14px;',
    '  line-height: 1.4;',
    '  outline: none;',
    '  color: var(--ink);',
    '  background: var(--panel);',
    '  transition: border-color 0.15s, box-shadow 0.15s;',
    '}',
    '.at-form textarea:focus {',
    '  border-color: var(--accent);',
    '  box-shadow: 0 0 0 2px rgba(15, 118, 110, 0.1);',
    '}',
    '.at-form textarea::placeholder { color: var(--muted); }',
    '',
    /* ── Mic Button ── */
    '.at-mic-btn {',
    '  width: 36px; height: 36px;',
    '  border: 0;',
    '  border-radius: 50%;',
    '  background: #f1f5f9;',
    '  color: var(--ink-light);',
    '  cursor: pointer;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  padding: 0;',
    '  flex-shrink: 0;',
    '  transition: background 0.15s, color 0.15s, transform 0.15s, box-shadow 0.15s;',
    '}',
    '.at-mic-btn:hover { background: #e2e8f0; color: var(--ink); transform: scale(1.08); }',
    '.at-mic-btn.at-mic-recording {',
    '  background: var(--rose);',
    '  color: white;',
    '  transform: scale(1.1);',
    '  animation: at-mic-pulse 1.2s infinite;',
    '}',
    '.at-mic-btn.at-mic-disabled {',
    '  opacity: 0.25;',
    '  cursor: not-allowed;',
    '  transform: none;',
    '}',
    '@keyframes at-mic-pulse {',
    '  0% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0.35); }',
    '  70% { box-shadow: 0 0 0 8px rgba(225, 29, 72, 0); }',
    '  100% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0); }',
    '}',
    '',
    /* ── Send Button ── */
    '.at-send-btn {',
    '  width: 36px; height: 36px;',
    '  border: 0;',
    '  border-radius: 50%;',
    '  background: var(--accent);',
    '  color: white;',
    '  cursor: pointer;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  padding: 0;',
    '  flex-shrink: 0;',
    '  transition: background 0.15s, transform 0.15s, opacity 0.2s;',
    '}',
    '.at-send-btn:hover { transform: scale(1.08); }',
    '.at-send-btn:active { transform: scale(0.92); }',
    '.at-send-btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }',
    '.at-send-btn svg { width: 18px; height: 18px; }',
    '',
    /* ── Mic Timer ── */
    '.at-mic-timer {',
    '  text-align: center;',
    '  color: var(--rose);',
    '  font-size: 12px;',
    '  font-weight: 700;',
    '  padding: 4px 0 2px;',
    '  letter-spacing: 0.02em;',
    '  display: none;',
    '}',
    '.at-mic-timer-visible { display: block; }',
    '',
    /* ── Retry ── */
    '.at-msg.at-retry-countdown {',
    '  align-self: center;',
    '  background: transparent;',
    '  color: var(--muted);',
    '  font-size: 12px;',
    '  text-align: center;',
    '  max-width: 100%;',
    '}',
    '.at-retry-btn {',
    '  display: inline-block;',
    '  margin-top: 8px;',
    '  padding: 6px 16px;',
    '  border: 1px solid var(--accent);',
    '  border-radius: 8px;',
    '  background: var(--panel);',
    '  color: var(--accent);',
    '  cursor: pointer;',
    '  font-size: 13px;',
    '  font-family: inherit;',
    '  outline: none;',
    '  transition: all 0.15s;',
    '}',
    '.at-retry-btn:hover { background: var(--accent); color: white; }',
    '',
    /* ── Responsive ── */
    '@media (max-width: 480px) {',
    '  .at-panel {',
    '    width: 100vw; height: 100vh;',
    '    bottom: 0; right: 0 !important; left: 0 !important;',
    '    border-radius: 0; border: 0;',
    '  }',
    '  .at-trigger { bottom: 12px; }',
    '  .at-trigger.at-right { right: 12px; }',
    '  .at-trigger.at-left { left: 12px; }',
    '  .at-head { padding: 12px 12px 10px; }',
    '}'
  ].join('\n');
  }
  var WIDGET_CSS = getWidgetCSS(CONFIG);

  /* ─── Utilities ─── */

  function escapeHtml(val) {
    return String(val)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getSessionId() {
    try {
      var stored = sessionStorage.getItem(SESSION_KEY);
      if (stored) return stored;
    } catch (_e) { /* ignore */ }
    var id = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : 'sess-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
    try {
      sessionStorage.setItem(SESSION_KEY, id);
    } catch (_e) { /* ignore */ }
    return id;
  }

  function loadStoredMessages() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_e) { return []; }
  }

  function saveStoredMessages(msgs) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(msgs));
    } catch (_e) { /* ignore */ }
  }

  function scrollToBottom(el) {
    if (el) el.scrollTop = el.scrollHeight;
  }

  function _isScrolledNearBottom(el) {
    return el && (el.scrollHeight - el.scrollTop - el.clientHeight < 48);
  }

  /* ─── Markdown Renderer ─── */

  function renderMarkdown(text) {
    var chunks = [];
    var lines = (text || '').split('\n');
    var i = 0;

    while (i < lines.length) {
      // Table
      if (isTableStart(lines, i)) {
        var tableLines = [];
        while (i < lines.length && lines[i].trim().charAt(0) === '|') {
          tableLines.push(lines[i]);
          i++;
        }
        chunks.push(renderTable(tableLines));
        continue;
      }
      // Unordered list
      if (/^\s*[-*]\s+/.test(lines[i])) {
        var items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
          i++;
        }
        chunks.push('<ul>' + items.map(function (item) {
          return '<li>' + inlineMarkdown(item) + '</li>';
        }).join('') + '</ul>');
        continue;
      }
      // Ordered list
      if (/^\s*\d+\.\s+/.test(lines[i])) {
        var oitems = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          oitems.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
          i++;
        }
        chunks.push('<ol>' + oitems.map(function (item) {
          return '<li>' + inlineMarkdown(item) + '</li>';
        }).join('') + '</ol>');
        continue;
      }
      // Paragraph
      var para = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !isTableStart(lines, i) &&
        !/^\s*[-*]\s+/.test(lines[i]) &&
        !/^\s*\d+\.\s+/.test(lines[i])
      ) {
        para.push(lines[i]);
        i++;
      }
      if (para.length) {
        chunks.push('<p>' + inlineMarkdown(para.join('\n')).replace(/\n/g, '<br>') + '</p>');
      }
      // Empty line — skip
      if (i < lines.length && !lines[i].trim()) i++;
    }

    return chunks.join('');
  }

  function isTableStart(lines, idx) {
    var line = lines[idx];
    var next = lines[idx + 1];
    if (!line || !next) return false;
    return line.trim().charAt(0) === '|' && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?/.test(next);
  }

  function renderTable(lines) {
    var dataRows = [];
    for (var j = 0; j < lines.length; j++) {
      if (/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(lines[j])) continue;
      var cells = lines[j].trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (c) { return c.trim(); });
      dataRows.push(cells);
    }
    if (!dataRows.length) return '';
    var head = dataRows[0];
    var body = dataRows.slice(1);
    return '<div class="at-table-wrap"><table><thead><tr>' +
      head.map(function (c) { return '<th>' + inlineMarkdown(c) + '</th>'; }).join('') +
      '</tr></thead><tbody>' +
      body.map(function (row) {
        return '<tr>' + row.map(function (c) { return '<td>' + inlineMarkdown(c) + '</td>'; }).join('') + '</tr>';
      }).join('') +
      '</tbody></table></div>';
  }

  function inlineMarkdown(val) {
    return escapeHtml(val)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  /* ─── SVG Icons ─── */

  var ICONS = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>',
    micOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
    thinking: '<div class="at-thinking-dots"><span></span><span></span><span></span></div>'
  };

  /* ─── DOM Builder ─── */

  function buildWidget(host) {
    var pos = CONFIG.position;
    var posClass = pos === 'left' ? 'at-left' : 'at-right';

    // ── Trigger Button ──
    var trigger = document.createElement('button');
    trigger.className = 'at-trigger ' + posClass;
    trigger.innerHTML = ICONS.chat;
    host.appendChild(trigger);

    // ── Panel ──
    var panel = document.createElement('div');
    panel.className = 'at-panel ' + posClass + ' at-hidden';

    // Header
    var head = document.createElement('div');
    head.className = 'at-head';
    head.innerHTML = '<div class="at-head-info"><strong>' + escapeHtml(CONFIG.title) + '</strong><span>' + escapeHtml(CONFIG.agent) + '</span></div>';
    // Online status indicator
    var statusEl = document.createElement('div');
    statusEl.className = 'at-head-status';
    statusEl.innerHTML = '<span class="at-dot"></span> ' + (CONFIG.lang === 'ru' ? 'Online' : 'Online');
    head.querySelector('.at-head-info').appendChild(statusEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'at-close';
    closeBtn.innerHTML = ICONS.close;
    head.appendChild(closeBtn);
    panel.appendChild(head);

    // Messages area
    var messages = document.createElement('div');
    messages.className = 'at-messages';
    panel.appendChild(messages);

    // Form
    var form = document.createElement('form');
    form.className = 'at-form';

    var textarea = document.createElement('textarea');
    textarea.rows = 1;
    textarea.placeholder = CONFIG.placeholder;

    var micBtn = document.createElement('button');
    micBtn.type = 'button';
    micBtn.className = 'at-mic-btn';
    micBtn.innerHTML = ICONS.mic;
    micBtn.title = CONFIG.lang === 'ru' ? 'Голосовое сообщение' : 'Voice message';
    micBtn.style.display = CONFIG.voiceInput && navigator.mediaDevices && navigator.mediaDevices.getUserMedia ? 'flex' : 'none';

    var sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.className = 'at-send-btn';
    sendBtn.innerHTML = ICONS.send;

    // Build row: [textarea][mic][send]
    var formRow = document.createElement('div');
    formRow.className = 'at-form-row';
    formRow.appendChild(textarea);
    formRow.appendChild(micBtn);
    formRow.appendChild(sendBtn);
    form.appendChild(formRow);

    // Mic timer (above form row)
    var micTimer = document.createElement('div');
    micTimer.className = 'at-mic-timer';
    form.insertBefore(micTimer, formRow);

    panel.appendChild(form);
    host.appendChild(panel);

    return { trigger: trigger, panel: panel, messages: messages, form: form, textarea: textarea, closeBtn: closeBtn, sendBtn: sendBtn, head: head, micBtn: micBtn, micTimer: micTimer };
  }

  /* ─── Chat Logic ─── */

  function runChat(ui) {
    var messagesEl = ui.messages;
    var headEl = ui.head;
    var sessionId = getSessionId();

    // ── Pending retry state ──
    var _pendingMessage = null;
    var retryAttempts = {};
    var MAX_RETRIES = 3;

    // ── Set global bridge so app.js can switch agent ──
    window.__agentTutorSetAgent = function __agentTutorSetAgent(name) {
      if (!name) return;
      CONFIG.agent = name;
      STORAGE_KEY = 'at_messages_' + CONFIG.agent;
      SESSION_KEY = 'at_session_' + CONFIG.agent;
      state.sessionId = null;
      state.messages = [];
      sessionId = getSessionId();
      state.sessionId = sessionId;
      var infoEl = headEl.querySelector('.at-head-info');
      if (infoEl) {
        infoEl.innerHTML = '<strong>' + escapeHtml(CONFIG.title) + '</strong><span>' + escapeHtml(CONFIG.agent) + '</span>';
      }
      messagesEl.innerHTML = '';
      restoreHistory();
    };

    // Helper to get first letter of agent name for avatar
    function getAgentInitial() {
      return CONFIG.title ? CONFIG.title.charAt(0).toUpperCase() : 'A';
    }

    // Sync with already-selected agent on page load
    try {
      var storedAgent = window.localStorage.getItem('agentTutorAgentId');
      if (storedAgent && CONFIG.agent !== storedAgent) {
        window.__agentTutorSetAgent(storedAgent);
      }
    } catch(_e) {}

    // ── Session storage helpers ──
    function readStored() {
      var stored = loadStoredMessages();
      return stored.filter(function (m) {
        return m.sessionId === sessionId;
      }).map(function (m) {
        return { kind: m.kind, text: m.text, tools: m.tools || [] };
      });
    }

    function appendStored(kind, text, tools) {
      var stored = loadStoredMessages();
      stored.push({
        sessionId: sessionId,
        kind: kind,
        text: String(text || ''),
        tools: tools || [],
        ts: Date.now()
      });
      var filtered = stored.filter(function (m) { return m.sessionId === sessionId; });
      if (filtered.length > 100) {
        var extra = filtered.length - 100;
        var removed = 0;
        stored = stored.filter(function (m) {
          if (m.sessionId === sessionId && removed < extra) {
            removed++;
            return false;
          }
          return true;
        });
      }
      saveStoredMessages(stored);
    }

    // ── Message rendering ──
    function addMessage(kind, text, opts) {
      opts = opts || {};

      if (kind === 'assistant') {
        // Wrap in a row: [avatar] [bubble]
        var row = document.createElement('div');
        row.className = 'at-msg-row';

        var avatar = document.createElement('div');
        avatar.className = 'at-avatar';
        avatar.textContent = 'AI';

        var node = document.createElement('div');
        node.className = 'at-msg at-assistant';

        if (opts.thinking) {
          node.dataset.raw = '';
          node.innerHTML = ICONS.thinking;
        } else {
          node.dataset.raw = text || '';
          node.innerHTML = renderMarkdown(text || '');
        }

        row.appendChild(node);
        row.appendChild(avatar);

        if (opts.before) {
          messagesEl.insertBefore(row, opts.before);
        } else {
          messagesEl.appendChild(row);
        }
      } else {
        var node = document.createElement('div');
        node.className = 'at-msg at-user';
        node.textContent = text || '';

        if (opts.before) {
          messagesEl.insertBefore(node, opts.before);
        } else {
          messagesEl.appendChild(node);
        }
      }

      if (opts.persist) {
        appendStored(kind, text, opts.tools);
      }

      if (opts.scroll !== false) {
        scrollToBottom(messagesEl);
      }

      return node;
    }

    function restoreHistory() {
      var stored = readStored();
      if (!stored.length) {
        addMessage('assistant', CONFIG.greeting, { persist: false, scroll: false });
        return;
      }

      messagesEl.innerHTML = '';
      var pendingToolNames = [];

      stored.forEach(function (msg) {
        if (msg.kind === 'user') {
          addMessage('user', msg.text, { persist: false, scroll: false });
        } else if (msg.kind === 'assistant') {
          var tools = (msg.tools || []).filter(Boolean);
          var text = String(msg.text || '');

          if (!text.trim() && tools.length > 0) {
            pendingToolNames = pendingToolNames.concat(tools);
            return;
          }

          var mergedTools = pendingToolNames.concat(tools);
          pendingToolNames = [];

          if (mergedTools.length > 0) {
            messagesEl.appendChild(makeToolStrip(mergedTools));
          }

          var row = document.createElement('div');
          row.className = 'at-msg-row';

          var avatar = document.createElement('div');
          avatar.className = 'at-avatar';
          avatar.textContent = 'AI';

          var node = document.createElement('div');
          node.className = 'at-msg at-assistant';
          node.dataset.raw = text;
          node.innerHTML = renderMarkdown(text);

          row.appendChild(node);
          row.appendChild(avatar);
          messagesEl.appendChild(row);
        }
      });

      if (pendingToolNames.length > 0) {
        messagesEl.appendChild(makeToolStrip(pendingToolNames));
      }

      scrollToBottom(messagesEl);
    }

    function makeToolStrip(toolNames, displayNames) {
      displayNames = displayNames || {};
      var unique = [];
      toolNames.forEach(function (n) {
        if (unique.indexOf(n) === -1) unique.push(n);
      });
      if (!unique.length) return null;
      var el = document.createElement('div');
      el.className = 'at-tool-strip';
      el.innerHTML = unique.map(function (name) {
        var display = displayNames[name] || name;
        var icon = getToolIcon(display);
        return '<span>' + icon + ' ' + escapeHtml(display) + '</span>';
      }).join('');
      return el;
    }

    function getToolIcon(displayText) {
      var lower = displayText.toLowerCase();
      if (lower.indexOf('поиск') !== -1 || lower.indexOf('найти') !== -1 || lower.indexOf('find') !== -1 || lower.indexOf('search') !== -1) return '\uD83D\uDD0D';
      if (lower.indexOf('чтение') !== -1 || lower.indexOf('get') !== -1 || lower.indexOf('получени') !== -1) return '\uD83D\uDCCB';
      if (lower.indexOf('запрос') !== -1 || lower.indexOf('query') !== -1) return '\uD83D\uDCCA';
      if (lower.indexOf('list') !== -1 || lower.indexOf('список') !== -1) return '\uD83D\uDCCB';
      return '\u26A1';
    }

    var TYPEWRITER_INTERVAL = 20;
    var TYPEWRITER_BURST = 3;

    function appendToken(target, text) {
      var raw = target.dataset.raw || '';
      target.dataset.raw = raw + text;
      // Typewriter: accumulate and reveal gradually
      if (!target.dataset.typewriterRunning) {
        target.dataset.typewriterRunning = '1';
        target.dataset.typewriterBuffer = raw + text;
        target.dataset.typewriterDisplayed = raw;
        revealTypewriter(target);
      } else {
        target.dataset.typewriterBuffer = (target.dataset.typewriterBuffer || '') + text;
      }
    }

    function revealTypewriter(target) {
      var buffer = target.dataset.typewriterBuffer || '';
      var displayed = target.dataset.typewriterDisplayed || '';

      if (displayed.length >= buffer.length) {
        target.dataset.typewriterRunning = '';
        target.innerHTML = renderMarkdown(buffer);
        scrollToBottom(messagesEl);
        return;
      }

      var charsToReveal = Math.min(TYPEWRITER_BURST, buffer.length - displayed.length);
      displayed = buffer.slice(0, displayed.length + charsToReveal);
      target.dataset.typewriterDisplayed = displayed;

      var rendered = renderMarkdown(displayed);
      if (displayed.length < buffer.length) {
        target.classList.add('at-typing-cursor');
        target.innerHTML = rendered;
      } else {
        target.classList.remove('at-typing-cursor');
        target.innerHTML = rendered;
        target.dataset.typewriterRunning = '';
        scrollToBottom(messagesEl);
        return;
      }

      if (_isScrolledNearBottom(messagesEl)) {
        scrollToBottom(messagesEl);
      }

      setTimeout(function () {
        revealTypewriter(target);
      }, TYPEWRITER_INTERVAL);
    }

    function setFinalText(target, text) {
      target.classList.remove('at-thinking');
      target.dataset.raw = text;
      target.innerHTML = renderMarkdown(text);
    }

    // ── Retry / Rate Limit Handling ──

    function scheduleRetry(message, delayMs) {
      var remaining = Math.ceil(delayMs / 1000);

      var countdownMsg = document.createElement('div');
      countdownMsg.className = 'at-msg at-retry-countdown';
      countdownMsg.textContent = '\u23F3 ' + (CONFIG.lang === 'ru' ? 'Повтор через' : 'Retry in') + ' ' + remaining + 's...';
      messagesEl.appendChild(countdownMsg);
      scrollToBottom(messagesEl);

      var interval = setInterval(function() {
        remaining--;
        if (remaining <= 0) {
          clearInterval(interval);
          countdownMsg.remove();
          retryChat(message);
        } else {
          countdownMsg.textContent = '\u23F3 ' + (CONFIG.lang === 'ru' ? 'Повтор через' : 'Retry in') + ' ' + remaining + 's...';
        }
      }, 1000);
    }

    function findMsgNode(n) {
      // targetNode might be inside .at-msg-row — find the actual .at-msg bubble
      if (n.classList.contains('at-msg-row')) return n.querySelector('.at-msg');
      if (n.classList.contains('at-msg')) return n;
      return n;
    }

    function removeMsgRow(targetNode) {
      // Remove the whole row (.at-msg-row) if target is inside one
      var row = targetNode.closest('.at-msg-row');
      if (row) { row.remove(); return; }
      targetNode.remove();
    }

    function retryChat(message) {
      var answerNode = addMessage('assistant', '', { thinking: true, persist: false, scroll: false });
      streamChat(message, findMsgNode(answerNode));
    }

    // ── SSE Streaming ──

    function _pumpSSE(response, targetNode) {
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function pump() {
        return reader.read().then(function (result) {
          if (result.done) return;

          buffer += decoder.decode(result.value, { stream: true });
          var parts = buffer.split('\n\n');
          buffer = parts.pop();

          parts.forEach(function (chunk) {
            var line = chunk.split('\n').find(function (l) { return l.indexOf('data:') === 0; });
            if (!line) return;

            try {
              var payload = JSON.parse(line.slice(5).trim());
            } catch (_e) { return; }

            if (targetNode.classList.contains('at-thinking')) {
              targetNode.classList.remove('at-thinking');
            }

            if (payload.type === 'token') {
              appendToken(targetNode, payload.text || '');
            } else if (payload.type === 'final') {
              setFinalText(targetNode, payload.text || '');
            } else if (payload.type === 'tool_call') {
              var tools = JSON.parse(targetNode.dataset.tools || '[]');
              var displayNames = JSON.parse(targetNode.dataset.displayNames || '{}');
              if (tools.indexOf(payload.name) === -1) {
                tools.push(payload.name);
                targetNode.dataset.tools = JSON.stringify(tools);
              }
              if (payload.display_name && !displayNames[payload.name]) {
                displayNames[payload.name] = payload.display_name;
                targetNode.dataset.displayNames = JSON.stringify(displayNames);
              }
              ensureToolStrip(targetNode, tools, displayNames);
            } else if (payload.type === 'audio') {
              if (CONFIG.voiceOutput && payload.data) {
                playAudioBase64(payload.data);
              }
            } else if (payload.type === 'done') {
              if (targetNode.classList.contains('at-error')) return;
              var raw = targetNode.dataset.raw || '';
              if (!raw.trim()) {
                setFinalText(targetNode, CONFIG.lang === 'ru'
                  ? 'Не удалось получить ответ.' : 'No response.');
              }
              var toolNames = [];
              try { toolNames = JSON.parse(targetNode.dataset.tools || '[]'); } catch (_e) { /* ignore */ }
              appendStored('assistant', targetNode.dataset.raw || '', toolNames);
              targetNode.dataset.saved = 'true';
              scrollToBottom(messagesEl);
            } else if (payload.type === 'error') {
              targetNode.classList.remove('at-thinking');
              targetNode.classList.add('at-error');
              targetNode.textContent = payload.text || (CONFIG.lang === 'ru'
                ? 'Произошла ошибка.' : 'An error occurred.');
            }
          });

          return pump();
        });
      }

      return pump();
    }

    function streamChat(message, targetNode) {
      targetNode.classList.add('at-thinking');

      var url = CONFIG.apiBase + '/api/chat/' + encodeURIComponent(CONFIG.agent);

      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: sessionId })
      }).then(function (response) {
        if (response.status === 429) {
          targetNode.classList.remove('at-thinking');
          removeMsgRow(targetNode);

          var retryAfter = response.headers.get('Retry-After');
          var delay = 5;
          if (retryAfter) {
            var parsed = parseInt(retryAfter, 10);
            if (!isNaN(parsed) && parsed > 0) delay = parsed;
          }

          retryAttempts[message] = (retryAttempts[message] || 0) + 1;
          var attempts = retryAttempts[message];

          if (attempts >= MAX_RETRIES) {
            var failMsg = document.createElement('div');
            failMsg.className = 'at-msg at-assistant at-error';
            failMsg.innerHTML = '\u26A0\uFE0F Server overloaded.';
            var retryBtn = document.createElement('button');
            retryBtn.className = 'at-retry-btn';
            retryBtn.textContent = 'Retry';
            failMsg.appendChild(retryBtn);
            messagesEl.appendChild(failMsg);
            scrollToBottom(messagesEl);
            retryBtn.addEventListener('click', function() {
              delete retryAttempts[message];
              failMsg.remove();
              retryChat(message);
            });
            return;
          }

          var rateMsg = document.createElement('div');
          rateMsg.className = 'at-msg at-assistant';
          rateMsg.textContent = '\u26A0\uFE0F ' + (CONFIG.lang === 'ru'
            ? 'Сервер перегружен. Повтор через' : 'Server overloaded. Retry in') + ' ' + delay + 's.';
          messagesEl.appendChild(rateMsg);
          scrollToBottom(messagesEl);

          _pendingMessage = message;
          scheduleRetry(message, delay * 1000);
          return;
        }

        if (!response.ok) {
          targetNode.classList.remove('at-thinking');
          targetNode.classList.add('at-error');
          targetNode.textContent = 'Error: ' + response.status;
          return;
        }

        return _pumpSSE(response, targetNode);
      }).catch(function (err) {
        targetNode.classList.remove('at-thinking');
        targetNode.classList.add('at-error');
        targetNode.innerHTML = '\u26A0\uFE0F ' + (CONFIG.lang === 'ru'
          ? 'Нет соединения с сервером.' : 'No connection to server.')
          + '<br><button class="at-retry-btn">' + (CONFIG.lang === 'ru' ? 'Повторить' : 'Retry') + '</button>';
        var btn = targetNode.querySelector('.at-retry-btn');
        if (btn) {
          btn.addEventListener('click', function() {
            targetNode.classList.remove('at-error');
            targetNode.innerHTML = ICONS.thinking;
            streamChat(message, targetNode);
          });
        }
      });
    }

    function ensureToolStrip(targetNode, toolNames, displayNames) {
      displayNames = displayNames || {};
      var unique = [];
      toolNames.forEach(function (n) {
        if (unique.indexOf(n) === -1) unique.push(n);
      });
      if (!unique.length) return;

      // Get the row element that contains targetNode (or targetNode itself for non-row)
      var ref = targetNode.closest ? (targetNode.closest('.at-msg-row') || targetNode) : targetNode;
      var prev = ref.previousElementSibling;

      if (prev && prev.className === 'at-tool-strip') {
        prev.innerHTML = unique.map(function (name) {
          var display = displayNames[name] || name;
          var icon = getToolIcon(display);
          return '<span>' + icon + ' ' + escapeHtml(display) + '</span>';
        }).join('');
        return;
      }
      var strip = makeToolStrip(unique, displayNames);
      if (strip) messagesEl.insertBefore(strip, ref);
    }

    // ── Event Bindings ──

    ui.trigger.addEventListener('click', function () {
      state.open = true;
      ui.panel.classList.remove('at-hidden');
      ui.trigger.style.display = 'none';
      ui.textarea.focus();
      scrollToBottom(messagesEl);
    });

    ui.closeBtn.addEventListener('click', function () {
      state.open = false;
      ui.panel.classList.add('at-hidden');
      ui.trigger.style.display = 'flex';
    });

    // ── Submit logic ──
    function handleSubmit() {
      var text = ui.textarea.value.trim();
      if (!text) return;
      ui.textarea.value = '';
      // Auto-reset height
      ui.textarea.style.height = 'auto';
      addMessage('user', text, { persist: true });
      var answerNode = addMessage('assistant', '', { thinking: true, persist: false, scroll: false });
      streamChat(text, answerNode);
    }

    // Textarea auto-resize
    ui.textarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    // Enter to send, Shift+Enter for newline
    ui.textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    });

    ui.form.addEventListener('submit', function (e) {
      e.preventDefault();
      handleSubmit();
    });

    // ── Voice Input ──
    var mediaRecorder = null;
    var micChunks = [];
    var _micStream = null;
    var micTimerInterval = null;
    var micStartTime = 0;
    var micDuration = 0;
    var MAX_RECORDING_SEC = 120;

    function updateMicTimer() {
      micDuration = Math.floor((Date.now() - micStartTime) / 1000);
      var m = Math.floor(micDuration / 60);
      var s = micDuration % 60;
      ui.micTimer.textContent = (m > 0 ? m + 'm ' : '') + s + 's';
    }

    function startVoiceRecording() {
      if (mediaRecorder && mediaRecorder.state === 'recording') return;

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        ui.micBtn.classList.add('at-mic-disabled');
        return;
      }

      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
          _micStream = stream;
          micChunks = [];

          var mimeType = 'audio/webm;codecs=opus';
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = 'audio/webm';
          }

          mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });

          mediaRecorder.ondataavailable = function (e) {
            if (e.data.size > 0) micChunks.push(e.data);
          };

          mediaRecorder.onstop = function () {
            stream.getTracks().forEach(function (t) { t.stop(); });
            _micStream = null;
            ui.micBtn.classList.remove('at-mic-recording');
            ui.micTimer.classList.remove('at-mic-timer-visible');
            if (micTimerInterval) { clearInterval(micTimerInterval); micTimerInterval = null; }

            var blob = new Blob(micChunks, { type: mimeType });
            if (blob.size === 0) return;

            var durStr = ui.micTimer.textContent || (micDuration + 's');
            addMessage('user', '\uD83C\uDFA4 ' + durStr, { persist: true });

            var answerNode = addMessage('assistant', '', { thinking: true, persist: false, scroll: false });
            streamVoiceChat(blob, answerNode);
          };

          mediaRecorder.start();
          ui.micBtn.innerHTML = ICONS.micOff;
          ui.micBtn.classList.add('at-mic-recording');
          ui.micTimer.classList.add('at-mic-timer-visible');
          micStartTime = Date.now();
          micDuration = 0;
          updateMicTimer();
          micTimerInterval = setInterval(updateMicTimer, 1000);

          if (MAX_RECORDING_SEC > 0) {
            setTimeout(function () {
              if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
              }
            }, MAX_RECORDING_SEC * 1000);
          }
        })
        .catch(function (err) {
          if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            addMessage('assistant', (CONFIG.lang === 'ru'
              ? '\u274C Разрешите доступ к микрофону в настройках браузера'
              : '\u274C Please allow microphone access in browser settings'),
              { persist: false });
          } else {
            ui.micBtn.classList.add('at-mic-disabled');
          }
        });
    }

    function stopVoiceRecording() {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      }
    }

    if (CONFIG.voiceInput && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      ui.micBtn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        if (ui.micBtn.classList.contains('at-mic-recording')) {
          stopVoiceRecording();
        } else {
          startVoiceRecording();
        }
      });
    }

    function streamVoiceChat(blob, targetNode) {
      targetNode.classList.add('at-thinking');

      var url = CONFIG.apiBase + '/api/chat/voice';
      var formData = new FormData();
      formData.append('audio', blob, 'voice.webm');
      formData.append('session_id', sessionId);
      formData.append('agent', CONFIG.agent);
      formData.append('lang', CONFIG.lang);

      fetch(url, {
        method: 'POST',
        body: formData
      }).then(function (response) {
        if (response.status === 429) {
          targetNode.classList.remove('at-thinking');
          targetNode.remove();
          var msg = document.createElement('div');
          msg.className = 'at-msg at-assistant';
          msg.textContent = CONFIG.lang === 'ru'
            ? '\u26A0\uFE0F Сервер перегружен. Попробуйте позже.'
            : '\u26A0\uFE0F Server overloaded. Try again later.';
          messagesEl.appendChild(msg);
          scrollToBottom(messagesEl);
          return;
        }

        if (!response.ok) {
          targetNode.classList.remove('at-thinking');
          targetNode.classList.add('at-error');
          targetNode.textContent = 'Error: ' + response.status;
          return;
        }

        return _pumpSSE(response, targetNode);
      }).catch(function () {
        targetNode.classList.remove('at-thinking');
        targetNode.classList.add('at-error');
        targetNode.innerHTML = '\u26A0\uFE0F ' + (CONFIG.lang === 'ru'
          ? 'Ошибка соединения.' : 'Connection error.');
      });
    }

    // ── Audio playback for TTS ──
    function playAudioBase64(b64data) {
      try {
        var binaryStr = atob(b64data);
        var byteArray = new Uint8Array(binaryStr.length);
        for (var i = 0; i < binaryStr.length; i++) {
          byteArray[i] = binaryStr.charCodeAt(i);
        }
        var blob = new Blob([byteArray], { type: 'audio/mpeg' });
        var url = URL.createObjectURL(blob);
        var audio = new Audio(url);
        audio.play().catch(function () {});
      } catch (_e) {}
    }

    // ── Init ──
    restoreHistory();
  }

  function init() {
    state.sessionId = getSessionId();
    buildUI();
  }

  function buildUI() {
    var host = document.createElement('div');
    host.id = 'helperium-widget-' + CONFIG.agent.replace(/[^a-zA-Z0-9_-]/g, '');

    var shadow = host.attachShadow({ mode: 'open' });

    var style = document.createElement('style');
    style.textContent = WIDGET_CSS;
    shadow.appendChild(style);

    var root = document.createElement('div');
    root.className = 'at-root';
    shadow.appendChild(root);

    var ui = buildWidget(root);
    runChat(ui);

    document.body.appendChild(host);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
