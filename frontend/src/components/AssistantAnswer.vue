<script setup>
import { computed } from "vue";

const props = defineProps({
  answer: { type: String, required: true },
});

const blocks = computed(() => parseAnswer(props.answer));

function parseAnswer(text) {
  const lines = String(text || "").split(/\r?\n/);
  const items = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      items.push({ type: "p", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list && list.items.length) {
      items.push(list);
    }
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      items.push({ type: "h3", text: line.replace(/^###\s+/, "") });
      continue;
    }
    if (line.startsWith("- ")) {
      flushParagraph();
      if (!list) {
        list = { type: "ul", items: [] };
      }
      list.items.push(line.replace(/^-\s+/, ""));
      continue;
    }
    if (line.startsWith("依据：")) {
      flushParagraph();
      flushList();
      // Source data still powers retrieval and routes, but visitor answers intentionally omit attribution UI.
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return items;
}
</script>

<template>
  <div class="answer-text">
    <template v-if="blocks.length">
      <template v-for="(block, index) in blocks" :key="index">
        <h3 v-if="block.type === 'h3'">{{ block.text }}</h3>
        <p v-else-if="block.type === 'p'">{{ block.text }}</p>
        <ul v-else-if="block.type === 'ul'">
          <li v-for="item in block.items" :key="item">{{ item }}</li>
        </ul>
      </template>
    </template>
    <p v-else class="empty-answer">请输入景区相关问题，我会先检索资料，再基于资料回答。</p>
  </div>
</template>
