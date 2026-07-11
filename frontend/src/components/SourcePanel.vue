<script setup>
import { computed } from "vue";

const props = defineProps({
  sources: { type: Array, required: true },
});

const groupedSources = computed(() => {
  const grouped = new Map();
  for (const source of props.sources || []) {
    const key = source.document_id || source.document_name || "unknown";
    const existing = grouped.get(key);
    if (existing) {
      existing.count += 1;
      existing.score = Math.max(existing.score, Number(source.score) || 0);
      if (!existing.content_preview && source.content_preview) {
        existing.content_preview = source.content_preview;
      }
      continue;
    }
    grouped.set(key, {
      document_name: source.document_name || "未知资料",
      content_preview: source.content_preview || "无摘要",
      score: Number(source.score) || 0,
      count: 1,
    });
  }
  return Array.from(grouped.values());
});

function formatConfidence(value) {
  const number = Number(value);
  return Number.isNaN(number) ? "--" : `${Math.round(number * 100)}%`;
}
</script>

<template>
  <section class="source-panel">
    <div class="panel-heading">
      <h2>引用来源</h2>
      <span>{{ sources.length }} 个片段，来自 {{ groupedSources.length }} 份资料</span>
    </div>
    <ul class="sources-list">
      <li v-if="!groupedSources.length" class="empty-source">
        暂无来源，提交问题后显示检索结果。
      </li>
      <li v-for="source in groupedSources" :key="source.document_name" class="source-card">
        <div class="source-title">
          <span>{{ source.document_name }}</span>
          <strong>{{ formatConfidence(source.score) }}</strong>
        </div>
        <div class="source-meta">引用 {{ source.count }} 个片段</div>
        <p>{{ source.content_preview }}</p>
      </li>
    </ul>
  </section>
</template>
