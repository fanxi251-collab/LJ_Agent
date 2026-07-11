<script setup>
import { ref } from "vue";
import AssistantAnswer from "./AssistantAnswer.vue";

defineProps({
  answer: { type: String, required: true },
  confidence: { type: String, required: true },
  isLoading: { type: Boolean, required: true },
  serviceState: { type: String, required: true },
});

const agentMode = defineModel("agentMode", { type: Boolean, default: true });
const emit = defineEmits(["ask", "clear-context"]);
const question = ref("");

function submitQuestion() {
  const value = question.value.trim();
  if (!value) {
    return;
  }
  emit("ask", value);
  question.value = "";
}
</script>

<template>
  <section class="chat-main" aria-label="景区 AI 导游问答">
    <header class="chat-topbar">
      <div>
        <p class="brand-mark">LingJing AI</p>
        <h1>景区 AI 导游</h1>
      </div>
      <div class="topbar-actions">
        <span class="status-pill">{{ serviceState }}</span>
        <button class="ghost-button" type="button" @click="$emit('clear-context')">
          清空上下文
        </button>
      </div>
    </header>

    <div class="welcome-block">
      <div class="brand-badge">AI</div>
      <h2>使用智能导游开始对话</h2>
      <div class="mode-switch" role="group" aria-label="问答模式">
        <button
          type="button"
          :class="{ active: agentMode }"
          @click="agentMode = true"
        >
          智能体模式
        </button>
        <button
          type="button"
          :class="{ active: !agentMode }"
          @click="agentMode = false"
        >
          RAG 模式
        </button>
      </div>
    </div>

    <section class="answer-card" aria-live="polite">
      <div class="answer-card-head">
        <span>回答</span>
        <strong>置信度 {{ confidence }}</strong>
      </div>
      <AssistantAnswer :answer="answer" />
    </section>

    <form class="composer-card" @submit.prevent="submitQuestion">
      <label class="sr-only" for="questionInput">输入问题</label>
      <textarea
        id="questionInput"
        v-model="question"
        name="question"
        rows="3"
        placeholder="给 LingJing AI 发送消息，例如：灵山胜境适合老人怎么玩？"
        required
      ></textarea>
      <div class="composer-actions">
        <span>{{ agentMode ? "智能体会优先调用工具和知识库" : "RAG 会先检索资料再回答" }}</span>
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? "检索中" : "发送" }}
        </button>
      </div>
    </form>
  </section>
</template>
