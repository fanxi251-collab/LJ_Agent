const chatForm = document.querySelector("#chatForm");
const uploadForm = document.querySelector("#uploadForm");
const documentInput = document.querySelector("#documentInput");
const uploadButton = document.querySelector("#uploadButton");
const uploadStatus = document.querySelector("#uploadStatus");
const uploadSuccessNotice = document.querySelector("#uploadSuccessNotice");
const questionInput = document.querySelector("#questionInput");
const submitButton = document.querySelector("#submitButton");
const answerText = document.querySelector("#answerText");
const confidenceText = document.querySelector("#confidenceText");
const sourcesList = document.querySelector("#sourcesList");
const sourceCount = document.querySelector("#sourceCount");
const serviceState = document.querySelector("#serviceState");
const agentModeInput = document.querySelector("#agentModeInput");
const clearContextButton = document.querySelector("#clearContextButton");
const newSessionButton = document.querySelector("#newSessionButton");
const deleteSessionButton = document.querySelector("#deleteSessionButton");
const sessionList = document.querySelector("#sessionList");
const routePanel = document.querySelector("#routePanel");
const routeMap = document.querySelector("#routeMap");
const routeSummary = document.querySelector("#routeSummary");
const routeNotice = document.querySelector("#routeNotice");
const routeSteps = document.querySelector("#routeSteps");
let latestStreamIsAnswered = false;
let latestAnswerMarkdown = "";
let chatHistory = [];
const visitorId = getOrCreateVisitorId();
let currentSessionId = localStorage.getItem("lingjing_current_session_id") || "";
let amapLoadPromise = null;
let amapMap = null;

loadVisitorSessions();

if (clearContextButton) {
  clearContextButton.addEventListener("click", () => {
    chatHistory = [];
    setStatus("上下文已清空", "idle");
  });
}

if (newSessionButton) {
  newSessionButton.addEventListener("click", () => {
    currentSessionId = "";
    localStorage.removeItem("lingjing_current_session_id");
    chatHistory = [];
    latestAnswerMarkdown = "";
    renderMarkdownAnswer("已开启新会话，请输入新的问题。");
    renderSources([]);
    confidenceText.textContent = "--";
    setStatus("新会话已创建", "idle");
    renderSessionList([]);
    loadVisitorSessions();
  });
}

if (deleteSessionButton) {
  deleteSessionButton.addEventListener("click", async () => {
    if (!currentSessionId) {
      setStatus("当前没有可删除的历史会话", "idle");
      return;
    }
    if (!window.confirm("确定删除当前会话吗？")) {
      return;
    }
    try {
      const response = await fetch(`/api/visitor/sessions/${currentSessionId}?visitor_id=${encodeURIComponent(visitorId)}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      currentSessionId = "";
      localStorage.removeItem("lingjing_current_session_id");
      chatHistory = [];
      latestAnswerMarkdown = "";
      renderMarkdownAnswer("当前会话已删除，可以开始新的提问。");
      renderSources([]);
      confidenceText.textContent = "--";
      setStatus("会话已删除", "idle");
      await loadVisitorSessions();
    } catch (error) {
      setStatus(`删除失败：${error.message}`, "idle");
    }
  });
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = documentInput.files[0];
  if (!file) {
    uploadStatus.textContent = "请先选择一个 .txt 或 .md 资料文件。";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  setUploading(true);
  hideUploadSuccess();
  uploadStatus.textContent = "正在上传并解析资料...";

  try {
    const response = await fetch("/api/rag/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    uploadStatus.textContent = `导入成功：${data.document_name}，新增 ${data.indexed_chunks} 个知识片段。`;
    showUploadSuccess(data);
    serviceState.textContent = "资料已更新";
  } catch (error) {
    hideUploadSuccess();
    uploadStatus.textContent = `导入失败：${error.message}`;
    serviceState.textContent = "上传异常";
  } finally {
    setUploading(false);
  }
});

documentInput.addEventListener("change", () => {
  hideUploadSuccess();
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    setStatus("请输入问题", "idle");
    return;
  }

  setLoading(true);
  latestAnswerMarkdown = "";
  renderMarkdownAnswer("");
  confidenceText.textContent = "--";
  renderSources([]);

  try {
    await streamChat(question, activeEndpoints().stream);
  } catch (error) {
    try {
      await requestChat(question, activeEndpoints().chat);
    } catch (fallbackError) {
      try {
        await streamChat(question, "/api/rag/chat/stream");
      } catch (ragStreamError) {
        try {
          await requestChat(question, "/api/rag/chat");
        } catch (ragError) {
          answerText.textContent = `请求失败：${ragError.message}`;
          confidenceText.textContent = "--";
          renderSources([]);
          setStatus("接口异常", "idle");
        }
      }
    }
  } finally {
    setLoading(false);
  }
});

function activeEndpoints() {
  if (agentModeInput && agentModeInput.checked) {
    return {
      stream: "/api/agent/chat/stream",
      chat: "/api/agent/chat",
      label: "智能体模式",
    };
  }
  return {
    stream: "/api/rag/chat/stream",
    chat: "/api/rag/chat",
    label: "RAG 模式",
  };
}

async function streamChat(question, endpoint) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildChatPayload(question)),
  });
  if (!response.ok || !response.body) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      handleStreamEvent(part);
    }
  }
  if (buffer.trim()) {
    handleStreamEvent(buffer);
  }
  appendConversationTurn(question, latestAnswerMarkdown);
  await loadVisitorSessions();
}

function handleStreamEvent(rawEvent) {
  const line = rawEvent
    .split("\n")
    .find((item) => item.startsWith("data: "));
  if (!line) {
    return;
  }
  const event = JSON.parse(line.slice(6));
  if (event.type === "meta") {
    updateCurrentSession(event);
    latestStreamIsAnswered = Boolean(event.is_answered);
    confidenceText.textContent = formatConfidence(event.confidence);
    renderSources(event.sources || []);
    setStatus(event.is_answered ? "生成中" : "资料不足", "idle");
    return;
  }
  if (event.type === "status") {
    setStatus(event.message || "智能体处理中", "idle");
    return;
  }
  if (event.type === "token") {
    latestAnswerMarkdown += event.content || "";
    renderMarkdownAnswer(latestAnswerMarkdown);
    return;
  }
  if (event.type === "done") {
    updateCurrentSession(event);
    setStatus(latestStreamIsAnswered ? "已回答" : "资料不足", "idle");
    return;
  }
  if (event.type === "error") {
    throw new Error(event.message || "流式接口异常");
  }
}

async function requestChat(question, endpoint) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildChatPayload(question)),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const data = await response.json();
  updateCurrentSession(data);
  latestAnswerMarkdown = data.answer || "未返回回答。";
  renderMarkdownAnswer(latestAnswerMarkdown);
  confidenceText.textContent = formatConfidence(data.confidence);
  renderSources(data.sources || []);
  setStatus(data.is_answered ? "已回答" : "资料不足", "idle");
  appendConversationTurn(question, latestAnswerMarkdown);
  await loadVisitorSessions();
}

function buildChatPayload(question) {
  return {
    question,
    history: chatHistory.slice(-12),
    visitor_id: visitorId,
    session_id: currentSessionId,
    persist_history: true,
  };
}

function getOrCreateVisitorId() {
  const storageKey = "lingjing_visitor_id";
  const existing = localStorage.getItem(storageKey);
  if (existing) {
    return existing;
  }
  const randomPart = window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID().replaceAll("-", "")
    : `${Date.now()}${Math.random().toString(16).slice(2)}`;
  const visitor = `visitor_${randomPart}`;
  localStorage.setItem(storageKey, visitor);
  return visitor;
}

function updateCurrentSession(data) {
  if (!data || !data.session_id) {
    return;
  }
  currentSessionId = data.session_id;
  localStorage.setItem("lingjing_current_session_id", currentSessionId);
}

async function loadVisitorSessions() {
  if (!sessionList) {
    return;
  }
  try {
    const response = await fetch("/api/visitor/sessions?visitor_id=" + encodeURIComponent(visitorId));
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderSessionList(data.sessions || []);
  } catch (error) {
    sessionList.innerHTML = "";
    const item = document.createElement("button");
    item.className = "session-item";
    item.type = "button";
    item.textContent = "历史加载失败";
    sessionList.appendChild(item);
  }
}

function renderSessionList(sessions) {
  if (!sessionList) {
    return;
  }
  sessionList.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("button");
    empty.className = `session-item${currentSessionId ? "" : " active"}`;
    empty.type = "button";
    empty.textContent = "当前新会话";
    empty.addEventListener("click", () => {
      currentSessionId = "";
      localStorage.removeItem("lingjing_current_session_id");
      chatHistory = [];
      setStatus("已切换到新会话", "idle");
      renderSessionList([]);
    });
    sessionList.appendChild(empty);
    return;
  }
  for (const session of sessions) {
    const item = document.createElement("button");
    item.className = `session-item${session.session_id === currentSessionId ? " active" : ""}`;
    item.type = "button";
    item.title = session.title || "历史会话";
    item.textContent = session.title || "历史会话";
    item.addEventListener("click", () => loadSessionMessages(session.session_id));
    sessionList.appendChild(item);
  }
}

async function loadSessionMessages(sessionId) {
  try {
    const response = await fetch(`/api/visitor/sessions/${sessionId}/messages?visitor_id=${encodeURIComponent(visitorId)}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    currentSessionId = sessionId;
    localStorage.setItem("lingjing_current_session_id", currentSessionId);
    chatHistory = (data.messages || [])
      .map((message) => ({ role: message.role, content: String(message.content || "").slice(0, 800) }))
      .slice(-12);
    const lastAssistant = [...(data.messages || [])].reverse().find((message) => message.role === "assistant");
    if (lastAssistant) {
      latestAnswerMarkdown = lastAssistant.content || "";
      renderMarkdownAnswer(latestAnswerMarkdown);
      renderSources(lastAssistant.sources || []);
      confidenceText.textContent = "--";
    }
    await loadVisitorSessions();
    setStatus("历史会话已载入", "idle");
  } catch (error) {
    setStatus(`载入失败：${error.message}`, "idle");
  }
}

function appendConversationTurn(question, answer) {
  const userText = String(question || "").trim();
  const assistantText = String(answer || "").trim();
  if (!userText || !assistantText) {
    return;
  }
  chatHistory.push({ role: "user", content: userText });
  chatHistory.push({ role: "assistant", content: assistantText.slice(0, 800) });
  if (chatHistory.length > 12) {
    chatHistory = chatHistory.slice(-12);
  }
}

function setUploading(isUploading) {
  uploadButton.disabled = isUploading;
  uploadButton.textContent = isUploading ? "解析中" : "上传入库";
}

function showUploadSuccess(data) {
  uploadSuccessNotice.hidden = false;
  uploadSuccessNotice.textContent = `资料上传成功，已自动解析入库，可立即提问。文件：${data.document_name}；新增 ${data.indexed_chunks} 个知识片段。`;
}

function hideUploadSuccess() {
  uploadSuccessNotice.hidden = true;
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitButton.textContent = isLoading ? "检索中" : "发送";
  const label = activeEndpoints().label;
  serviceState.textContent = isLoading ? "正在分析问题" : `${label}在线`;
}

function setStatus(text) {
  serviceState.textContent = text;
}

function formatConfidence(value) {
  const number = Number(value);
  if (Number.isNaN(number)) {
    return "--";
  }
  return `${Math.round(number * 100)}%`;
}

function renderSources(sources) {
  renderRoutePanel(sources);
  const groupedSources = groupSourcesByDocument(sources);
  sourceCount.textContent = `${sources.length} 个片段，来自 ${groupedSources.length} 份资料`;
  sourcesList.innerHTML = "";

  if (groupedSources.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-source";
    empty.textContent = "暂无来源，提交问题后显示检索结果。";
    sourcesList.appendChild(empty);
    return;
  }

  for (const source of groupedSources) {
    const item = document.createElement("li");
    item.className = "source-card";

    const title = document.createElement("div");
    title.className = "source-title";

    const name = document.createElement("span");
    name.textContent = source.document_name || "未知资料";

    const score = document.createElement("span");
    score.textContent = formatConfidence(source.score);

    const meta = document.createElement("div");
    meta.className = "source-meta";
    meta.textContent = `引用 ${source.count} 个片段`;

    const preview = document.createElement("p");
    preview.className = "source-preview";
    preview.textContent = source.content_preview || "无摘要";

    title.append(name, score);
    item.append(title, meta, preview);
    sourcesList.appendChild(item);
  }
}

async function renderRoutePanel(sources) {
  const routeSource = findRouteSource(sources);
  if (!routeSource || !routePanel) {
    hideRoutePanel();
    return;
  }

  const summary = routeSource.metadata.route_summary || routeSource.metadata;
  routePanel.hidden = false;
  routeSummary.textContent = `${summary.mode_text || "路线"} ${summary.distance_text || "--"}，预计${summary.duration_text || "--"}`;
  routeNotice.textContent = "正在加载高德地图...";
  renderRouteSteps(summary.steps || []);

  try {
    const config = await fetchMapConfig();
    if (!config.enabled || !config.js_api_key) {
      routeNotice.textContent = "未配置 MAP_JS_API，暂只显示文字路线。";
      return;
    }
    await loadAmapScript(config.js_api_key);
    drawAmapRoute(summary);
    routeNotice.textContent = "路线由高德地图绘制，实际通行请以现场交通为准。";
  } catch (error) {
    routeNotice.textContent = `地图加载失败：${error.message}`;
  }
}

function findRouteSource(sources) {
  return (sources || []).find((source) => {
    const metadata = source.metadata || {};
    return metadata.source_type === "amap_route" && (metadata.route_summary || metadata.polyline);
  });
}

function hideRoutePanel() {
  if (!routePanel) {
    return;
  }
  routePanel.hidden = true;
  if (routeSteps) {
    routeSteps.innerHTML = "";
  }
}

async function fetchMapConfig() {
  const response = await fetch("/api/tools/map/config");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function loadAmapScript(jsApiKey) {
  if (window.AMap) {
    return Promise.resolve();
  }
  if (amapLoadPromise) {
    return amapLoadPromise;
  }
  amapLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(jsApiKey)}`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("高德 JS API 加载失败"));
    document.head.appendChild(script);
  });
  return amapLoadPromise;
}

function drawAmapRoute(summary) {
  if (!routeMap || !window.AMap) {
    return;
  }
  const path = (summary.polyline || []).map(parseLngLat).filter(Boolean);
  if (path.length < 2) {
    routeNotice.textContent = "路线坐标不足，暂无法绘制地图。";
    return;
  }
  if (!amapMap) {
    amapMap = new window.AMap.Map(routeMap, {
      zoom: 11,
      center: path[0],
      viewMode: "2D",
    });
  }
  amapMap.clearMap();
  new window.AMap.Marker({ map: amapMap, position: path[0], title: summary.origin || "起点" });
  new window.AMap.Marker({ map: amapMap, position: path[path.length - 1], title: summary.destination || "终点" });
  new window.AMap.Polyline({
    map: amapMap,
    path,
    strokeColor: "#237468",
    strokeWeight: 7,
    strokeOpacity: 0.9,
  });
  amapMap.setFitView();
}

function renderRouteSteps(steps) {
  if (!routeSteps) {
    return;
  }
  routeSteps.innerHTML = "";
  if (!steps.length) {
    const item = document.createElement("li");
    item.textContent = "高德未返回详细步骤。";
    routeSteps.appendChild(item);
    return;
  }
  for (const step of steps.slice(0, 8)) {
    const item = document.createElement("li");
    item.textContent = step.instruction || "继续前行";
    routeSteps.appendChild(item);
  }
}

function parseLngLat(point) {
  const [lng, lat] = String(point || "").split(",").map(Number);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
    return null;
  }
  return [lng, lat];
}

function groupSourcesByDocument(sources) {
  const grouped = new Map();
  for (const source of sources) {
    const key = source.document_id || source.document_name || "unknown";
    const existing = grouped.get(key);
    if (existing) {
      existing.count += 1;
      existing.score = Math.max(existing.score, Number(source.score) || 0);
      if (!existing.content_preview && source.content_preview) {
        existing.content_preview = source.content_preview;
      }
      continue;
    }
    grouped.set(key, {
      document_id: source.document_id,
      document_name: source.document_name || "未知资料",
      content_preview: source.content_preview || "",
      score: Number(source.score) || 0,
      count: 1,
    });
  }
  return Array.from(grouped.values());
}

function renderMarkdownAnswer(markdown) {
  answerText.innerHTML = "";
  const lines = markdown.split(/\r?\n/);
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length === 0) {
      return;
    }
    const p = document.createElement("p");
    p.textContent = paragraph.join(" ");
    answerText.appendChild(p);
    paragraph = [];
  };

  const flushList = () => {
    if (list) {
      answerText.appendChild(list);
      list = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      const heading = document.createElement("h3");
      heading.textContent = line.replace(/^###\s+/, "");
      answerText.appendChild(heading);
      continue;
    }
    if (line.startsWith("- ")) {
      flushParagraph();
      if (!list) {
        list = document.createElement("ul");
      }
      const item = document.createElement("li");
      item.textContent = line.replace(/^-\s+/, "");
      list.appendChild(item);
      continue;
    }
    if (line.startsWith("依据：")) {
      flushParagraph();
      flushList();
      const source = document.createElement("p");
      source.className = "answer-source";
      source.textContent = line;
      answerText.appendChild(source);
      continue;
    }
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
}
