<script setup>
import { computed } from "vue";

const props = defineProps({
  state: { type: String, default: "idle" },
  audioLevel: { type: Number, default: 0 },
});

const mouthScale = computed(() => 0.25 + Math.min(1, Math.max(0, props.audioLevel)) * 1.6);
</script>

<template>
  <svg
    :class="['digital-human-svg', `avatar-${state}`]"
    viewBox="0 0 360 460"
    role="img"
    aria-label="灵境数字人导游"
  >
    <defs>
      <linearGradient id="guideCoat" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#3c8e82" />
        <stop offset="1" stop-color="#163f38" />
      </linearGradient>
    </defs>
    <path d="M82 452c7-102 35-148 98-148s91 46 98 148" fill="url(#guideCoat)" />
    <path d="M129 313l51 64 51-64" fill="#f7e9d8" opacity=".95" />
    <ellipse cx="180" cy="206" rx="91" ry="112" fill="#f1c9a8" />
    <path d="M92 207c-9-81 26-143 92-143 68 0 102 49 88 134-25-50-72-64-137-43-12 32-25 50-43 52z" fill="#263d39" />
    <path d="M135 209q17-12 34 0M194 209q17-12 34 0" fill="none" stroke="#3e3936" stroke-width="5" stroke-linecap="round" />
    <ellipse cx="152" cy="214" rx="5" ry="7" fill="#273732" />
    <ellipse cx="211" cy="214" rx="5" ry="7" fill="#273732" />
    <path d="M176 225q-5 20 6 23" fill="none" stroke="#c68f70" stroke-width="3" stroke-linecap="round" />
    <ellipse class="avatar-mouth" cx="181" cy="270" rx="18" :ry="8 * mouthScale" fill="#9f4e4e" />
    <path d="M92 364q-30 27-45 77M268 364q30 27 45 77" fill="none" stroke="#24675d" stroke-width="36" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
.digital-human-svg {
  position: relative;
  width: 230px;
  height: 300px;
  filter: drop-shadow(0 20px 22px rgba(25, 65, 55, 0.18));
}
</style>
