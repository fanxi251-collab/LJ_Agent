<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import Live2DAvatarRenderer from "../renderers/Live2DAvatarRenderer.vue";
import {
  NEUTRAL_EXPRESSION,
  createExpressionDebouncer,
  resolveLive2DExpression,
} from "../lib/live2dExpression.js";

const props = defineProps({
  state: { type: String, default: "idle" },
  audioLevel: { type: Number, default: 0 },
  transcript: { type: String, default: "" },
  emotionText: { type: String, default: "" },
});

const rendererKey = ref(0);
const rendererReady = ref(false);
const rendererError = ref("");
const expression = ref(NEUTRAL_EXPRESSION);
const expressionDebouncer = createExpressionDebouncer((nextExpression) => {
  expression.value = nextExpression;
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

onBeforeUnmount(() => expressionDebouncer.dispose());
</script>

<template>
  <section :class="['digital-human-stage', `is-${state}`]" aria-label="数字人导游舞台">
    <div class="avatar-halo"></div>
    <Live2DAvatarRenderer
      v-if="!rendererError"
      :key="rendererKey"
      :state="state"
      :audio-level="audioLevel"
      :expression="expression"
      @ready="markRendererReady"
      @error="markRendererFailed"
    />
    <div v-if="!rendererReady && !rendererError" class="avatar-loading" role="status">
      正在加载本地 Live2D 形象…
    </div>
    <div v-if="rendererError" class="avatar-error" role="alert">
      <strong>数字人形象加载失败</strong>
      <span>{{ rendererError }}</span>
      <button type="button" @click="retryRenderer">重新加载形象</button>
    </div>
    <div class="avatar-state-pill"><span></span>{{ stateLabel }}</div>
    <small class="avatar-attribution">Mao Pro sample © Live2D Inc.</small>
    <p class="avatar-transcript">{{ transcript || "按住下方按钮开始说话，也可以使用文字输入。" }}</p>
  </section>
</template>

<style scoped>
.digital-human-stage {
  position: relative;
  width: min(820px, 100%);
  min-height: 480px;
  justify-self: center;
  display: grid;
  place-items: center;
  align-content: center;
  overflow: hidden;
  border: 1px solid #dce7e2;
  border-radius: 24px;
  background: radial-gradient(circle at 50% 32%, #eff9f5, #e8f1ed 58%, #dfeae5);
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
  background: #2f766d;
}

.avatar-attribution {
  position: absolute;
  z-index: 3;
  top: 22px;
  right: 20px;
  color: #6b7e78;
  font-size: 10px;
}

.avatar-transcript {
  position: absolute;
  bottom: 18px;
  width: min(620px, calc(100% - 36px));
  border-radius: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.86);
  color: #465b55;
  text-align: center;
  line-height: 1.55;
}

@keyframes avatar-breathe {
  50% { transform: scale(1.07); opacity: 0.72; }
}

@media (max-width: 680px) {
  .digital-human-stage { min-height: 430px; }
  .avatar-attribution { top: 58px; }
}
</style>
