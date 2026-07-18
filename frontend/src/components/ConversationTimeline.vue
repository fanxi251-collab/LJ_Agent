<script setup>
import { nextTick, ref, watch } from "vue";
import AssistantAnswer from "./AssistantAnswer.vue";

const props = defineProps({ messages: { type: Array, required: true } });
const emit = defineEmits(["retry", "show-sources"]);
const timeline = ref(null);

watch(
  () => props.messages.map((message) => message.content).join("|"),
  async () => {
    await nextTick();
    if (timeline.value) timeline.value.scrollTop = timeline.value.scrollHeight;
  },
);
</script>

<template>
  <section ref="timeline" class="conversation-timeline" aria-live="polite">
    <div v-if="!messages.length" class="conversation-empty">
      <span class="brand-badge">AI</span>
      <h2>今天想了解哪个景区？</h2>
      <p>可以询问景点特色、开放时间、门票、天气和路线。</p>
    </div>
    <article v-for="message in messages" :key="message.id" :class="['message-row', message.role]">
      <div class="message-avatar">{{ message.role === "user" ? "你" : "AI" }}</div>
      <div class="message-bubble">
        <p v-if="message.role === 'user'">{{ message.content }}</p>
        <AssistantAnswer v-else :answer="message.content" />
        <span v-if="message.pending" class="typing-indicator">正在生成…</span>
        <div v-if="message.error" class="message-error">
          {{ message.error }}
          <button
            v-if="message.retryable && message.retryQuestion"
            type="button"
            @click="emit('retry', message.retryQuestion)"
          >重试</button>
        </div>
        <button
          v-if="message.role === 'assistant' && message.sources?.length"
          class="citation-link"
          type="button"
          @click="emit('show-sources', message.sources)"
        >
          查看 {{ message.sources.length }} 条引用
        </button>
      </div>
    </article>
  </section>
</template>
