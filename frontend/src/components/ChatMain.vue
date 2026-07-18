<script setup>
import { ref } from "vue";
import ConversationTimeline from "./ConversationTimeline.vue";
import {
  DigitalHumanStage,
  DigitalHumanVoiceControls,
  TranscriptConfirmation,
} from "../features/digital-human";

const props = defineProps({
  messages: { type: Array, required: true },
  isLoading: { type: Boolean, required: true },
  serviceState: { type: String, required: true },
  avatarState: { type: String, required: true },
  audioLevel: { type: Number, required: true },
  inputLevel: { type: Number, default: 0 },
  inputQuality: { type: String, default: "good" },
  autoGainState: { type: String, default: "unknown" },
  transcript: { type: String, default: "" },
  emotionText: { type: String, default: "" },
  microphoneState: { type: String, default: "idle" },
  transcriptConfirmation: { type: Object, default: null },
  correctionNotice: { type: String, default: "" },
});
const mode = defineModel("mode", { type: String, default: "text" });
const emit = defineEmits([
  "ask",
  "mode-change",
  "start-recording",
  "stop-recording",
  "cancel",
  "show-sources",
  "confirm-transcript",
]);
const question = ref("");

function setMode(nextMode) {
  emit("mode-change", nextMode);
}

function submitQuestion() {
  const value = question.value.trim();
  if (!value) return;
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
        <div class="mode-switch" role="group" aria-label="交互模式">
          <button type="button" :class="{ active: mode === 'text' }" @click="setMode('text')">常规模式</button>
          <button type="button" :class="{ active: mode === 'avatar' }" @click="setMode('avatar')">数字人模式</button>
        </div>
        <span class="status-pill">{{ serviceState }}</span>
        <button v-if="isLoading" class="ghost-button" type="button" @click="emit('cancel')">停止</button>
      </div>
    </header>

    <ConversationTimeline
      v-if="mode === 'text'"
      :messages="messages"
      @retry="emit('ask', $event)"
      @show-sources="emit('show-sources', $event)"
    />
    <DigitalHumanStage
      v-else
      :state="avatarState"
      :audio-level="audioLevel"
      :transcript="transcript"
      :emotion-text="emotionText"
    />

    <TranscriptConfirmation
      v-if="transcriptConfirmation"
      :confirmation="transcriptConfirmation"
      @confirm="emit('confirm-transcript', $event)"
    />
    <p v-if="correctionNotice" class="correction-notice">{{ correctionNotice }}</p>

    <form class="composer-card" @submit.prevent="submitQuestion">
      <label class="sr-only" for="questionInput">输入问题</label>
      <textarea
        id="questionInput"
        v-model="question"
        name="question"
        rows="2"
        placeholder="给 LingJing AI 发送消息，例如：灵山胜境适合老人怎么玩？"
        @keydown.enter.exact.prevent="submitQuestion"
      ></textarea>
      <div class="composer-actions">
        <template v-if="mode === 'text'">
          <span>常规模式仅请求文字输出，不产生语音输出费用</span>
          <div class="composer-buttons">
            <button type="submit">发送</button>
          </div>
        </template>
        <DigitalHumanVoiceControls
          v-else
          :microphone-state="microphoneState"
          :input-quality="inputQuality"
          :auto-gain-state="autoGainState"
          @start-recording="emit('start-recording')"
          @stop-recording="emit('stop-recording')"
        >
          <button type="submit">发送</button>
        </DigitalHumanVoiceControls>
      </div>
    </form>
  </section>
</template>
