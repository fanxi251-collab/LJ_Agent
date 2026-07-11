<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import ChatMain from "../components/ChatMain.vue";
import SessionSidebar from "../components/SessionSidebar.vue";
import SourcePanel from "../components/SourcePanel.vue";
import UploadPanel from "../components/UploadPanel.vue";
import RoutePanel from "../components/RoutePanel.vue";
import { useChat } from "../composables/useChat";
import { useSessions } from "../composables/useSessions";

const route = useRoute();
const router = useRouter();
const agentMode = ref(true);
const activeToolPanel = ref("sources");
const sessionsApi = useSessions();
const chatApi = useChat({
  agentMode,
  currentSessionId: sessionsApi.currentSessionId,
  visitorId: sessionsApi.visitorId,
  onSessionChanged: sessionsApi.loadSessions,
});

const toolTabs = computed(() => [
  { id: "sources", label: `引用 ${chatApi.sources.value.length}` },
  { id: "upload", label: "资料上传" },
  { id: "route", label: chatApi.hasRouteSource.value ? "路线地图" : "路线" },
]);

async function loadSession(sessionId) {
  const messages = await sessionsApi.loadSessionMessages(sessionId);
  chatApi.restoreMessages(messages);
}

function startNewSession() {
  sessionsApi.startNewSession();
  chatApi.resetConversation("已开启新会话，请输入新的问题。");
}

async function deleteCurrentSession() {
  const deleted = await sessionsApi.deleteCurrentSession();
  if (deleted) chatApi.resetConversation("当前会话已删除，可以开始新的提问。");
}

onMounted(async () => {
  const question = String(route.query.q || "").trim();
  if (!question) return;
  // 从景点详情跳转时自动提问，让“询问 AI”成为完整闭环而不是只切换页面。
  await router.replace({ path: "/visitor/guide" });
  await chatApi.ask(question);
});
</script>

<template>
  <main class="visitor-layout guide-view">
    <section class="chat-area">
      <ChatMain
        v-model:agent-mode="agentMode"
        :answer="chatApi.answer.value"
        :confidence="chatApi.confidence.value"
        :is-loading="chatApi.isLoading.value"
        :service-state="chatApi.serviceState.value"
        @ask="chatApi.ask"
        @clear-context="chatApi.clearContext"
      />
      <section class="tool-dock" aria-label="辅助信息">
        <div class="tool-tabs">
          <button v-for="tab in toolTabs" :key="tab.id" type="button" :class="{ active: activeToolPanel === tab.id }" @click="activeToolPanel = tab.id">
            {{ tab.label }}
          </button>
        </div>
        <SourcePanel v-show="activeToolPanel === 'sources'" :sources="chatApi.sources.value" />
        <UploadPanel v-show="activeToolPanel === 'upload'" @uploaded="chatApi.markKnowledgeUpdated" />
        <RoutePanel v-show="activeToolPanel === 'route'" :sources="chatApi.sources.value" />
      </section>
    </section>
    <aside class="history-side" aria-label="历史会话">
      <SessionSidebar
        :sessions="sessionsApi.sessions.value"
        :current-session-id="sessionsApi.currentSessionId.value"
        :status="sessionsApi.status.value"
        @new-session="startNewSession"
        @load-session="loadSession"
        @delete-current-session="deleteCurrentSession"
      />
    </aside>
  </main>
</template>
