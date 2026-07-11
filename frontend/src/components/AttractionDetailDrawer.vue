<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({ attraction: { type: Object, default: null } });
const emit = defineEmits(["close"]);
const router = useRouter();
const images = computed(() => props.attraction?.images || []);

function openMap() {
  router.push({ path: "/visitor/map", query: { attraction: props.attraction.attraction_id } });
}

function askGuide() {
  router.push({ path: "/visitor/guide", query: { q: `请详细介绍${props.attraction.name}，并给出游览建议。` } });
}
</script>

<template>
  <div v-if="attraction" class="drawer-backdrop" @click.self="emit('close')">
    <aside class="attraction-drawer" role="dialog" aria-modal="true" :aria-label="`${attraction.name}详情`">
      <button class="drawer-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
      <div class="drawer-gallery">
        <img v-for="image in images" :key="image.image_id" :src="image.url" :alt="attraction.name" />
        <div v-if="!images.length" class="image-placeholder">灵山胜境</div>
      </div>
      <div class="drawer-content">
        <p class="section-kicker">{{ attraction.category || "景点介绍" }}</p>
        <h2>{{ attraction.name }}</h2>
        <p class="drawer-summary">{{ attraction.summary }}</p>
        <div class="attraction-facts">
          <span>开放：{{ attraction.opening_hours || "以现场公告为准" }}</span>
          <span>建议游玩：{{ attraction.suggested_duration_minutes || "--" }} 分钟</span>
          <span>地址：{{ attraction.address || "灵山胜境景区内" }}</span>
        </div>
        <p class="drawer-description">{{ attraction.description }}</p>
        <div class="tag-row"><span v-for="tag in attraction.tags" :key="tag">{{ tag }}</span></div>
        <div class="drawer-actions">
          <button type="button" @click="openMap">在地图中查看</button>
          <button class="secondary-button" type="button" @click="askGuide">询问 AI 导游</button>
        </div>
      </div>
    </aside>
  </div>
</template>
