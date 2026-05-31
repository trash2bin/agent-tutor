const apiBase = window.DEMO_API_BASE || "http://127.0.0.1:8081";
const sessionId = getSessionId();
const chatHistoryKey = "agentTutorMessages";

const state = {
  data: null,
  tab: "students",
  filter: ""
};

const configs = {
  students: {
    title: "Студенты",
    columns: [
      ["name", "ФИО"],
      ["group_name", "Группа"],
      ["speciality", "Специальность"],
      ["course", "Курс"]
    ]
  },
  schedule: {
    title: "Расписание",
    columns: [
      ["group_name", "Группа"],
      ["day", "День"],
      ["lessons", "Пары"]
    ],
    format: {
      lessons: lessons => lessons.map(item => `${item.discipline_name}, ${item.teacher_name}, ауд. ${item.room}`).join("\n")
    }
  },
  disciplines: {
    title: "Дисциплины",
    columns: [
      ["name", "Название"],
      ["description", "Описание"]
    ]
  },
  teachers: {
    title: "Преподаватели",
    columns: [
      ["name", "ФИО"],
      ["disciplines", "Дисциплины"]
    ],
    format: {
      disciplines: value => value.join(", ")
    }
  },
  documents: {
    title: "Документы",
    columns: [
      ["title", "Название"],
      ["discipline_name", "Дисциплина"],
      ["mime_type", "Тип"],
      ["created_at", "Добавлен"]
    ]
  },
  grades: {
    title: "Оценки",
    columns: [
      ["student_name", "Студент"],
      ["discipline_name", "Дисциплина"],
      ["grade", "Оценка"],
      ["date", "Дата"]
    ]
  }
};

const metrics = [
  ["students", "студентов"],
  ["teachers", "преподавателей"],
  ["disciplines", "дисциплин"],
  ["documents", "документов"],
  ["grades", "оценок"],
  ["schedule", "дней расписания"]
];

const $ = selector => document.querySelector(selector);

async function init() {
  restoreChatHistory();
  bindTabs();
  bindChat();
  await Promise.all([loadData(), checkHealth()]);
}

async function checkHealth() {
  const status = $("#status");
  try {
    const response = await fetch(`${apiBase}/health`);
    const data = await response.json();
    status.textContent = data.ollama?.status === "ok" ? `API: ${data.ollama.model}` : "API: Ollama недоступна";
    status.style.background = data.ollama?.status === "ok" ? "#eaf7f5" : "#fff7ed";
    status.style.color = data.ollama?.status === "ok" ? "#0b5f59" : "#a15c07";
  } catch {
    status.textContent = "API: недоступен";
    status.style.background = "#fff1f3";
    status.style.color = "#b4235a";
  }
}

async function loadData() {
  const response = await fetch(`${apiBase}/api/data`);
  state.data = await response.json();
  renderMetrics();
  renderTable();
}

function renderMetrics() {
  const root = $("#metrics");
  root.innerHTML = metrics.map(([key, label]) => `
    <div class="metric">
      <b>${state.data.stats[key] ?? 0}</b>
      <span>${label}</span>
    </div>
  `).join("");
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach(button => {
    button.addEventListener("click", () => {
      state.tab = button.dataset.tab;
      state.filter = "";
      $("#filter").value = "";
      document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item === button));
      renderTable();
    });
  });

  $("#filter").addEventListener("input", event => {
    state.filter = event.target.value.toLowerCase();
    renderTable();
  });
}

function renderTable() {
  if (!state.data) {
    return;
  }
  const config = configs[state.tab];
  const rows = (state.data[state.tab] || []).filter(row => {
    return JSON.stringify(row).toLowerCase().includes(state.filter);
  });

  $("#tableTitle").textContent = config.title;
  $("#tableHead").innerHTML = `<tr>${config.columns.map(([, title]) => `<th>${escapeHtml(title)}</th>`).join("")}</tr>`;
  $("#tableBody").innerHTML = rows.map(row => {
    const cells = config.columns.map(([key]) => {
      const formatter = config.format?.[key];
      const value = formatter ? formatter(row[key] || []) : row[key];
      return `<td>${escapeHtml(value ?? "—")}</td>`;
    });
    return `<tr>${cells.join("")}</tr>`;
  }).join("");
}

function bindChat() {
  const form = $("#chatForm");
  const input = $("#chatInput");
  const widget = $("#chatWidget");
  const open = $("#openChat");

  $("#collapseChat").addEventListener("click", () => {
    widget.classList.add("hidden");
    open.classList.remove("hidden");
  });

  open.addEventListener("click", () => {
    widget.classList.remove("hidden");
    open.classList.add("hidden");
    input.focus();
  });

  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) {
      return;
    }
    input.value = "";
    addMessage("user", text, {persist: true});
    const answer = addMessage("assistant", "", {persist: false});
    await streamChat(text, answer);
  });
}

async function streamChat(message, target) {
  target.dataset.raw = "";
  target.innerHTML = '<span class="typing">Думаю и проверяю данные...</span>';
  try {
    const response = await fetch(`${apiBase}/api/chat`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message, session_id: sessionId})
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const {done, value} = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, {stream: true});
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        handleEventChunk(chunk, target);
      }
    }
  } catch (error) {
    target.classList.add("error");
    target.textContent = `Ошибка: ${error.message}`;
  }
}

function getSessionId() {
  const storageKey = "agentTutorSessionId";
  try {
    const existing = window.sessionStorage.getItem(storageKey);
    if (existing) {
      return existing;
    }
    const generated = createSessionId();
    window.sessionStorage.setItem(storageKey, generated);
    return generated;
  } catch {
    return createSessionId();
  }
}

function createSessionId() {
  return window.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function handleEventChunk(chunk, target) {
  const line = chunk.split("\n").find(item => item.startsWith("data:"));
  if (!line) {
    return;
  }
  const payload = JSON.parse(line.slice(5).trim());
  if (payload.type === "token") {
    const messages = $("#messages");
    const shouldStickToBottom = isScrolledNearBottom(messages);
    appendAssistantToken(target, payload.text);
    if (shouldStickToBottom) {
      scrollMessagesToBottom(messages);
    }
  }
  if (payload.type === "done" && !(target.dataset.raw || "").trim()) {
    const fallback = "Модель не вернула текст. Попробуйте уточнить запрос.";
    target.dataset.raw = fallback;
    target.textContent = fallback;
  }
  if (payload.type === "done") {
    saveAssistantMessage(target);
  }
  if (payload.type === "error") {
    target.classList.add("error");
    target.textContent = `Ошибка: ${payload.text}`;
  }
}

function appendAssistantToken(target, text) {
  const raw = `${target.dataset.raw || ""}${text}`;
  target.dataset.raw = raw;
  target.innerHTML = renderAssistantMarkup(raw);
}

function renderAssistantMarkup(raw) {
  const toolNames = [];
  let text = raw.replace(/\n*\[tool:([^\]]+)]\n*/g, (_, name) => {
    toolNames.push(name);
    return "\n";
  }).trim();

  const chunks = [];
  if (toolNames.length) {
    const uniqueTools = [...new Set(toolNames)];
    chunks.push(`<div class="tool-strip">${uniqueTools.map(name => `<span>tool: ${escapeHtml(name)}</span>`).join("")}</div>`);
  }

  if (!text) {
    return chunks.join("");
  }

  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    if (isTableStart(lines, i)) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i]);
        i += 1;
      }
      chunks.push(renderMarkdownTable(tableLines));
      continue;
    }

    if (/^\s*[-*]\s+/.test(lines[i])) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i += 1;
      }
      chunks.push(`<ul>${items.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(lines[i])) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i += 1;
      }
      chunks.push(`<ol>${items.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ol>`);
      continue;
    }

    const paragraph = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !isTableStart(lines, i) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      paragraph.push(lines[i]);
      i += 1;
    }
    if (paragraph.length) {
      chunks.push(`<p>${inlineMarkdown(paragraph.join("\n")).replaceAll("\n", "<br>")}</p>`);
    }
    i += 1;
  }

  return chunks.join("");
}

function isTableStart(lines, index) {
  return Boolean(
    lines[index]?.trim().startsWith("|") &&
    lines[index + 1]?.includes("---")
  );
}

function renderMarkdownTable(lines) {
  const rows = lines
    .filter(line => !/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line))
    .map(line => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim()));

  if (!rows.length) {
    return "";
  }

  const [head, ...body] = rows;
  return `
    <div class="markdown-table">
      <table>
        <thead><tr>${head.map(cell => `<th>${inlineMarkdown(cell)}</th>`).join("")}</tr></thead>
        <tbody>${body.map(row => `<tr>${row.map(cell => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
      </table>
    </div>
  `;
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function addMessage(kind, text, options = {}) {
  const node = document.createElement("div");
  node.className = `message ${kind}`;
  if (kind === "assistant") {
    node.dataset.raw = text;
    node.innerHTML = text ? renderAssistantMarkup(text) : "";
  } else {
    node.textContent = text;
  }
  const messages = $("#messages");
  messages.appendChild(node);
  if (options.persist) {
    appendStoredMessage(kind, text);
  }
  if (options.scroll !== false) {
    scrollMessagesToBottom(messages);
  }
  return node;
}

function restoreChatHistory() {
  const storedMessages = readStoredMessages();
  if (!storedMessages.length) {
    return;
  }

  const messages = $("#messages");
  messages.innerHTML = "";
  storedMessages.forEach(message => {
    addMessage(message.kind, message.text, {persist: false, scroll: false});
  });
  scrollMessagesToBottom(messages);
}

function saveAssistantMessage(target) {
  if (target.dataset.saved === "true") {
    return;
  }
  const text = target.dataset.raw || target.textContent || "";
  appendStoredMessage("assistant", text);
  target.dataset.saved = "true";
}

function appendStoredMessage(kind, text) {
  const value = String(text || "").trim();
  if (!value) {
    return;
  }
  const messages = readStoredMessages();
  messages.push({kind, text: value});
  writeStoredMessages(messages);
}

function readStoredMessages() {
  try {
    const raw = window.sessionStorage.getItem(chatHistoryKey);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isStoredMessage);
  } catch {
    return [];
  }
}

function writeStoredMessages(messages) {
  try {
    window.sessionStorage.setItem(chatHistoryKey, JSON.stringify(messages));
  } catch {
    // If browser storage is unavailable, the visible chat still works for the current page.
  }
}

function isStoredMessage(value) {
  return (
    value &&
    ["user", "assistant"].includes(value.kind) &&
    typeof value.text === "string"
  );
}

function isScrolledNearBottom(node) {
  return node.scrollHeight - node.scrollTop - node.clientHeight < 48;
}

function scrollMessagesToBottom(node = $("#messages")) {
  node.scrollTop = node.scrollHeight;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

init();
