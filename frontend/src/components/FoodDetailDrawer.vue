<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({ food: { type: Object, default: null } });
const emit = defineEmits(["close"]);
const router = useRouter();
const images = computed(() => props.food?.images || []);

function openMap() {
  router.push({ path: "/visitor/map", query: { food: props.food.food_id } });
}

function askGuide() {
  router.push({ path: "/visitor/guide", query: { q: `请介绍${props.food.name}，并推荐适合游客的招牌菜。` } });
}
</script>

<template>
  <div v-if="food" class="drawer-backdrop" @click.self="emit('close')">
    <aside class="attraction-drawer food-detail-drawer" role="dialog" aria-modal="true" :aria-label="`${food.name}详情`">
      <button class="drawer-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
      <div class="drawer-gallery">
        <img v-for="image in images" :key="image.image_id" :src="image.url" :alt="`${food.name}菜品氛围示意`" />
        <div v-if="!images.length" class="image-placeholder">灵山风味</div>
      </div>
      <div class="drawer-content">
        <p class="section-kicker">{{ food.scope === "inside" ? "景区内餐饮" : "灵山周边" }} · {{ food.category }}</p>
        <h2>{{ food.name }}</h2>
        <p class="drawer-summary">{{ food.summary }}</p>
        <div class="attraction-facts food-facts">
          <span>预算：{{ "¥".repeat(food.price_level || 1) }}</span>
          <span>营业：{{ food.opening_hours || "以现场当日信息为准" }}</span>
          <span>地址：{{ food.address }}</span>
          <span>信息核验：{{ food.verified_at || "待更新" }}</span>
        </div>
        <p class="drawer-description">{{ food.description }}</p>
        <div class="signature-block"><strong>推荐品尝</strong><span v-for="dish in food.signature_dishes" :key="dish">{{ dish }}</span></div>
        <div class="tag-row"><span v-for="tag in food.taste_tags" :key="tag">{{ tag }}</span><span v-if="food.vegetarian_friendly">素食友好</span></div>
        <p class="food-information-note">图片为菜品氛围示意，营业与供应信息请以现场当日公告为准。</p>
        <div class="drawer-actions">
          <button type="button" @click="openMap">在地图中查看</button>
          <button class="secondary-button" type="button" @click="askGuide">询问 AI 导游</button>
        </div>
      </div>
    </aside>
  </div>
</template>

