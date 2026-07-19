import { ref } from "vue";
import { getOrCreateVisitorId } from "../lib/visitorIdentity";

export function useSessions() {
  const visitorId = getOrCreateVisitorId();
  const currentSessionId = ref(localStorage.getItem("lingjing_current_session_id") || "");
  const sessions = ref([]);
  const status = ref("正在加载历史");

  async function loadSessions() {
    try {
      const response = await fetch("/api/visitor/sessions?visitor_id=" + encodeURIComponent(visitorId));
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      sessions.value = data.sessions || [];
      status.value = sessions.value.length ? "点击会话继续提问" : "暂无历史会话";
    } catch (error) {
      status.value = `历史加载失败：${error.message}`;
    }
  }

  async function loadSessionMessages(sessionId) {
    try {
      const response = await fetch(`/api/visitor/sessions/${sessionId}/messages?visitor_id=${encodeURIComponent(visitorId)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      currentSessionId.value = sessionId;
      localStorage.setItem("lingjing_current_session_id", currentSessionId.value);
      await loadSessions();
      return data.messages || [];
    } catch (error) {
      status.value = `载入失败：${error.message}`;
      return [];
    }
  }

  function startNewSession() {
    currentSessionId.value = "";
    localStorage.removeItem("lingjing_current_session_id");
    status.value = "已切换到新会话";
  }

  async function deleteCurrentSession() {
    if (!currentSessionId.value) {
      status.value = "当前没有可删除的历史会话";
      return false;
    }
    if (!window.confirm("确定删除当前会话吗？")) {
      return false;
    }
    try {
      const response = await fetch(`/api/visitor/sessions/${currentSessionId.value}?visitor_id=${encodeURIComponent(visitorId)}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      currentSessionId.value = "";
      localStorage.removeItem("lingjing_current_session_id");
      await loadSessions();
      status.value = "会话已删除";
      return true;
    } catch (error) {
      status.value = `删除失败：${error.message}`;
      return false;
    }
  }

  loadSessions();

  return {
    visitorId,
    currentSessionId,
    sessions,
    status,
    loadSessions,
    loadSessionMessages,
    startNewSession,
    deleteCurrentSession,
  };
}
