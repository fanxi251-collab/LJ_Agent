import { computed, ref } from "vue";
import { findSuccessfulRouteSource } from "../lib/routeSummary.js";

export function useChat({ agentMode, currentSessionId, visitorId, onSessionChanged }) {
  const answer = ref("");
  const confidence = ref("--");
  const sources = ref([]);
  const serviceState = ref("智能体在线");
  const isLoading = ref(false);
  const chatHistory = ref([]);
  const latestStreamIsAnswered = ref(false);

  const hasRouteSource = computed(() => {
    return Boolean(findSuccessfulRouteSource(sources.value));
  });

  async function ask(question) {
    isLoading.value = true;
    answer.value = "";
    confidence.value = "--";
    sources.value = [];
    serviceState.value = "正在分析问题";
    try {
      await streamChat(question, activeEndpoints().stream);
    } catch (error) {
      try {
        await requestChat(question, activeEndpoints().chat);
      } catch (fallbackError) {
        await requestChat(question, "/api/rag/chat");
      }
    } finally {
      isLoading.value = false;
    }
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
    appendConversationTurn(question, answer.value);
    await onSessionChanged?.();
  }

  function handleStreamEvent(rawEvent) {
    const line = rawEvent.split("\n").find((item) => item.startsWith("data: "));
    if (!line) {
      return;
    }
    const event = JSON.parse(line.slice(6));
    if (event.type === "meta") {
      updateCurrentSession(event);
      latestStreamIsAnswered.value = Boolean(event.is_answered);
      confidence.value = formatConfidence(event.confidence);
      sources.value = event.sources || [];
      serviceState.value = event.is_answered ? "生成中" : "资料不足";
      return;
    }
    if (event.type === "status") {
      serviceState.value = event.message || "智能体处理中";
      return;
    }
    if (event.type === "token") {
      answer.value += event.content || "";
      return;
    }
    if (event.type === "done") {
      updateCurrentSession(event);
      serviceState.value = latestStreamIsAnswered.value ? "已回答" : "资料不足";
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
    answer.value = data.answer || "未返回回答。";
    confidence.value = formatConfidence(data.confidence);
    sources.value = data.sources || [];
    serviceState.value = data.is_answered ? "已回答" : "资料不足";
    appendConversationTurn(question, answer.value);
    await onSessionChanged?.();
  }

  function buildChatPayload(question) {
    return {
      question,
      history: chatHistory.value.slice(-12),
      visitor_id: visitorId,
      session_id: currentSessionId.value,
      persist_history: true,
    };
  }

  function activeEndpoints() {
    if (agentMode.value) {
      return {
        stream: "/api/agent/chat/stream",
        chat: "/api/agent/chat",
      };
    }
    return {
      stream: "/api/rag/chat/stream",
      chat: "/api/rag/chat",
    };
  }

  function updateCurrentSession(data) {
    if (!data?.session_id) {
      return;
    }
    currentSessionId.value = data.session_id;
    localStorage.setItem("lingjing_current_session_id", currentSessionId.value);
  }

  function appendConversationTurn(question, assistantAnswer) {
    const userText = String(question || "").trim();
    const assistantText = String(assistantAnswer || "").trim();
    if (!userText || !assistantText) {
      return;
    }
    chatHistory.value.push({ role: "user", content: userText });
    chatHistory.value.push({ role: "assistant", content: assistantText.slice(0, 800) });
    chatHistory.value = chatHistory.value.slice(-12);
  }

  function restoreMessages(messages) {
    chatHistory.value = (messages || [])
      .map((message) => ({ role: message.role, content: String(message.content || "").slice(0, 800) }))
      .slice(-12);
    const lastAssistant = [...(messages || [])].reverse().find((message) => message.role === "assistant");
    if (lastAssistant) {
      answer.value = lastAssistant.content || "";
      sources.value = lastAssistant.sources || [];
      confidence.value = "--";
      serviceState.value = "历史会话已载入";
    }
  }

  function clearContext() {
    chatHistory.value = [];
    serviceState.value = "上下文已清空";
  }

  function resetConversation(message) {
    chatHistory.value = [];
    answer.value = message;
    confidence.value = "--";
    sources.value = [];
    serviceState.value = "智能体在线";
  }

  function markKnowledgeUpdated() {
    serviceState.value = "资料已更新";
  }

  return {
    answer,
    confidence,
    sources,
    serviceState,
    isLoading,
    hasRouteSource,
    ask,
    clearContext,
    restoreMessages,
    resetConversation,
    markKnowledgeUpdated,
  };
}

function formatConfidence(value) {
  const number = Number(value);
  return Number.isNaN(number) ? "--" : `${Math.round(number * 100)}%`;
}
