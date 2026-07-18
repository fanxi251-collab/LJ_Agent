<script setup>
import { computed } from "vue";
import SvgAvatarRenderer from "../renderers/SvgAvatarRenderer.vue";

const props = defineProps({
  state: { type: String, default: "idle" },
  audioLevel: { type: Number, default: 0 },
  transcript: { type: String, default: "" },
});

const stateLabel = computed(() => ({
  idle: "待机",
  listening: "正在聆听",
  thinking: "正在思考",
  speaking: "正在讲解",
  error: "服务异常",
}[props.state] || "待机"));
</script>

<template>
  <section :class="['digital-human-stage', `is-${state}`]" aria-label="数字人导游舞台">
    <div class="avatar-halo"></div>
    <SvgAvatarRenderer :state="state" :audio-level="audioLevel" />
    <div class="avatar-state-pill"><span></span>{{ stateLabel }}</div>
    <p class="avatar-transcript">{{ transcript || "按住下方按钮开始说话，也可以使用文字输入。" }}</p>
  </section>
</template>

<style scoped>
.digital-human-stage {
  position: relative;
  width: min(820px, 100%);
  min-height: 390px;
  justify-self: center;
  display: grid;
  place-items: center;
  align-content: center;
  overflow: hidden;
  border: 1px solid #dce7e2;
  border-radius: 24px;
  background: radial-gradient(circle at 50% 32%, #eff9f5, #e8f1ed 58%, #dfeae5);
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
</style>
