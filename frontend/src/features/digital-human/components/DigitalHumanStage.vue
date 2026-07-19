<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import DigitalHumanAnswerPanel from "./DigitalHumanAnswerPanel.vue";
import Live2DAvatarRenderer from "../renderers/Live2DAvatarRenderer.vue";
import {
  avatarExpression,
  resolveAvatarProfile,
} from "../lib/live2dCharacters.js";
import {
  NEUTRAL_EXPRESSION,
  createExpressionDebouncer,
  resolveLive2DExpression,
} from "../lib/live2dExpression.js";

const props = defineProps({
  avatarId: { type: String, default: "mao_pro" },
  state: { type: String, default: "idle" },
  audioLevel: { type: Number, default: 0 },
  answerText: { type: String, default: "" },
  emotionText: { type: String, default: "" },
});

const rendererKey = ref(0);
const rendererReady = ref(false);
const rendererError = ref("");
const semanticExpression = ref(NEUTRAL_EXPRESSION);
const currentProfile = computed(() => resolveAvatarProfile(props.avatarId));
const expression = computed(() => avatarExpression(props.avatarId, semanticExpression.value));
const expressionDebouncer = createExpressionDebouncer((nextExpression) => {
  semanticExpression.value = nextExpression;
});

const stateLabel = computed(() => ({
  idle: "待机",
  listening: "正在聆听",
  thinking: "正在思考",
  speaking: "正在讲解",
  error: "服务异常",
}[props.state] || "待机"));

watch(
  () => resolveLive2DExpression({ state: props.state, assistantText: props.emotionText }),
  (nextExpression) => {
    if (nextExpression === NEUTRAL_EXPRESSION) expressionDebouncer.reset();
    else expressionDebouncer.update(nextExpression);
  },
  { immediate: true },
);

function markRendererReady() {
  rendererReady.value = true;
  rendererError.value = "";
}

function markRendererFailed(error) {
  rendererReady.value = false;
  rendererError.value = error?.message || "Live2D资源加载失败。";
}

function retryRenderer() {
  // Remount from a clean instance because partially initialized WebGL resources cannot be reused safely.
  rendererReady.value = false;
  rendererError.value = "";
  rendererKey.value += 1;
}

watch(() => props.avatarId, () => {
  rendererReady.value = false;
  rendererError.value = "";
  expressionDebouncer.reset();
});

onBeforeUnmount(() => expressionDebouncer.dispose());
</script>

<template>
  <section :class="['digital-human-stage', `is-${state}`]" aria-label="数字人导游舞台">
    <div class="avatar-visual">
      <div class="avatar-halo"></div>
      <Live2DAvatarRenderer
        v-if="!rendererError"
        :key="`${avatarId}_${rendererKey}`"
        :avatar-id="avatarId"
        :state="state"
        :audio-level="audioLevel"
        :expression="expression"
        @ready="markRendererReady"
        @error="markRendererFailed"
      />
      <div v-if="!rendererReady && !rendererError" class="avatar-loading" role="status">
        正在加载{{ currentProfile.roleLabel }}形象…
      </div>
      <div v-if="rendererError" class="avatar-error" role="alert">
        <strong>数字人形象加载失败</strong>
        <span>{{ rendererError }}</span>
        <button type="button" @click="retryRenderer">重新加载形象</button>
      </div>
      <div class="avatar-state-pill"><span></span>{{ stateLabel }}</div>
      <small class="avatar-attribution">{{ currentProfile.attribution }}</small>
    </div>
    <DigitalHumanAnswerPanel :answer-text="answerText" :state="state" />
  </section>
</template>

<style scoped>
.digital-human-stage {
  position: relative;
  width: min(980px, 100%);
  min-height: 480px;
  justify-self: center;
  display: grid;
  grid-template-columns: minmax(300px, 42%) minmax(0, 58%);
  align-items: stretch;
  gap: 24px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 24px;
  background: transparent;
  box-shadow: 0 22px 56px rgba(15, 52, 58, 0.16);
  backdrop-filter: none;
}

.avatar-visual {
  position: relative;
  min-width: 0;
  min-height: 480px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 24px;
}

.avatar-loading,
.avatar-error {
  position: relative;
  z-index: 2;
  display: grid;
  justify-items: center;
  gap: 10px;
  max-width: 360px;
  border-radius: 16px;
  padding: 18px 22px;
  background: rgba(255, 255, 255, 0.9);
  color: #465b55;
  text-align: center;
}

.avatar-error strong { color: #9f3f38; }
.avatar-error span { font-size: 12px; }
.avatar-error button {
  border: 0;
  border-radius: 999px;
  padding: 8px 14px;
  background: #2f766d;
  color: white;
  cursor: pointer;
}

.avatar-halo {
  position: absolute;
  width: 330px;
  height: 330px;
  border-radius: 50%;
  background: rgba(47, 118, 109, 0.12);
  filter: blur(3px);
  animation: avatar-breathe 3.4s ease-in-out infinite;
}

.is-listening .avatar-halo { background: rgba(79, 117, 255, 0.18); animation-duration: 1.2s; }
.is-thinking .avatar-halo { background: rgba(221, 178, 92, 0.2); animation-duration: 0.9s; }
.is-speaking .avatar-halo { background: rgba(47, 118, 109, 0.24); animation-duration: 0.55s; }
.is-error .avatar-halo { background: rgba(177, 69, 61, 0.16); }

.avatar-state-pill {
  position: absolute;
  top: 18px;
  left: 18px;
  display: flex;
  align-items: center;
  gap: 7px;
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.86);
  color: #38564f;
  font-size: 12px;
  font-weight: 800;
}

.avatar-state-pill span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--guide-accent, #2f7d78);
}

.avatar-attribution {
  position: absolute;
  z-index: 3;
  top: 22px;
  right: 20px;
  color: #6b7e78;
  font-size: 10px;
}

@keyframes avatar-breathe {
  50% { transform: scale(1.07); opacity: 0.72; }
}

@media (max-width: 900px) {
  .digital-human-stage {
    width: 100%;
    height: 100%;
    min-height: 0;
    grid-template-columns: 1fr;
    grid-template-rows: minmax(260px, 1fr) minmax(132px, auto);
    gap: 12px;
  }

  .avatar-visual { min-height: 260px; }
}

@media (max-width: 680px) {
  .avatar-attribution { top: 16px; }
}
</style>
