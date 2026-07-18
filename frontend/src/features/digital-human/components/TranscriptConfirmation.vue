<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  confirmation: { type: Object, required: true },
});
const emit = defineEmits(["confirm"]);
const confirmationText = ref("");

watch(
  () => props.confirmation,
  (value) => { confirmationText.value = value?.text || ""; },
  { immediate: true },
);

function submit(value = confirmationText.value) {
  const normalized = String(value || "").trim();
  if (normalized) emit("confirm", normalized);
}
</script>

<template>
  <section class="transcript-confirmation" aria-live="polite">
    <strong>转写结果需要确认</strong>
    <p>请选择景区词候选，或直接修改后确认。本轮在确认前不会生成回答。</p>
    <div class="transcript-candidates">
      <button
        v-for="candidate in confirmation.candidates"
        :key="candidate"
        type="button"
        @click="submit(candidate)"
      >{{ candidate }}</button>
    </div>
    <div class="transcript-edit-row">
      <input v-model="confirmationText" aria-label="编辑转写文本" />
      <button type="button" @click="submit()">确认并继续</button>
    </div>
  </section>
</template>

<style scoped>
.transcript-confirmation {
  margin: 0 18px 12px;
  padding: 14px;
  border: 1px solid rgba(199, 151, 55, 0.38);
  border-radius: 14px;
  background: #fff9e9;
  color: #5f4b26;
}

p { margin: 6px 0 10px; font-size: 13px; }
.transcript-candidates { display: flex; flex-wrap: wrap; gap: 8px; }
.transcript-candidates button { border: 1px solid #d7bd7f; background: white; color: #6d5427; }
.transcript-edit-row { display: flex; gap: 8px; margin-top: 10px; }
.transcript-edit-row input { flex: 1; min-width: 0; border: 1px solid #d8c89f; border-radius: 9px; padding: 9px 11px; }
</style>
