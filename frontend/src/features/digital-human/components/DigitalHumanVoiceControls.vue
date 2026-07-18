<script setup>
defineProps({
  microphoneState: { type: String, default: "idle" },
  inputQuality: { type: String, default: "good" },
  autoGainState: { type: String, default: "unknown" },
});

const emit = defineEmits(["start-recording", "stop-recording"]);
</script>

<template>
  <div class="digital-human-voice-controls">
    <span v-if="microphoneState === 'denied'">麦克风不可用，可继续使用文字输入</span>
    <span v-else-if="microphoneState === 'finishing'">正在保护句尾，请稍候</span>
    <span v-else-if="inputQuality === 'loud'">音量过大，请稍微远离麦克风</span>
    <span v-else-if="inputQuality === 'quiet'">请靠近麦克风</span>
    <span v-else-if="microphoneState === 'recording'">音量合适</span>
    <span v-else-if="autoGainState === 'unsupported'">浏览器不支持自动增益，仍可正常录音</span>
    <span v-else>文字提问也会由数字人朗读</span>
    <div class="voice-buttons">
      <button
        class="hold-to-talk"
        type="button"
        @pointerdown.prevent="emit('start-recording')"
        @pointerup.prevent="emit('stop-recording')"
        @pointercancel.prevent="emit('stop-recording')"
        @pointerleave="['starting', 'recording'].includes(microphoneState) && emit('stop-recording')"
        :disabled="microphoneState === 'finishing'"
      >
        {{ microphoneState === "recording" ? "松开发送" : microphoneState === "finishing" ? "正在补全句尾" : "按住说话" }}
      </button>
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
.digital-human-voice-controls {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.voice-buttons { display: flex; gap: 8px; }

.hold-to-talk {
  min-width: 108px;
  color: #2f675d;
  background: #e8f2ee;
  touch-action: none;
}

@media (max-width: 760px) {
  .digital-human-voice-controls {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
