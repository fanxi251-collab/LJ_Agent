<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import AttractionDetailDrawer from "../components/AttractionDetailDrawer.vue";
import { useInteractiveMap } from "../composables/useInteractiveMap";

const route = useRoute();
const attractions = ref([]);
const selected = ref(null);
const drawerAttraction = ref(null);
const originId = ref("");
const destinationId = ref("");
const routeMode = ref("walking");
const routeSummary = ref(null);
const routeStatus = ref("请选择起点和终点。 ");
const interactiveMap = useInteractiveMap("interactiveMap");

async function loadAttractions() {
  const response = await fetch("/api/visitor/attractions");
  const data = await response.json();
  attractions.value = response.ok ? (data.attractions || []) : [];
  await nextTick();
  await interactiveMap.initialize(attractions.value, selectAttraction);
  const requested = String(route.query.attraction || "");
  const initial = attractions.value.find((item) => item.attraction_id === requested) || attractions.value[0];
  if (initial) selectAttraction(initial);
}

function selectAttraction(item) {
  selected.value = item;
  destinationId.value ||= item.attraction_id;
  interactiveMap.selectAttraction(item);
}

async function planRoute() {
  if (!originId.value || !destinationId.value) return void (routeStatus.value = "请选择起点和终点。 ");
  if (originId.value === destinationId.value) return void (routeStatus.value = "起点和终点不能相同。 ");
  const origin = attractions.value.find((item) => item.attraction_id === originId.value);
  const destination = attractions.value.find((item) => item.attraction_id === destinationId.value);
  const params = new URLSearchParams({
    origin: origin.name,
    destination: destination.name,
    origin_location: `${origin.longitude},${origin.latitude}`,
    destination_location: `${destination.longitude},${destination.latitude}`,
    mode: routeMode.value,
  });
  routeStatus.value = "正在规划路线...";
  try {
    const response = await fetch(`/api/tools/map/route?${params}`);
    const data = await response.json();
    if (!response.ok || data.status !== "ok") throw new Error(data.message || `HTTP ${response.status}`);
    routeSummary.value = data.data?.route_summary || data.data || null;
    interactiveMap.renderRoute(routeSummary.value);
    routeStatus.value = `${routeSummary.value?.mode_text || "路线"} ${routeSummary.value?.distance_text || ""}，预计 ${routeSummary.value?.duration_text || "--"}`;
  } catch (error) {
    routeStatus.value = `路线规划失败：${error.message}`;
  }
}

watch(selected, (item) => interactiveMap.selectAttraction(item));
onMounted(loadAttractions);
</script>

<template>
  <main class="content-view map-view">
    <section class="map-intro">
      <div><p class="section-kicker">INTERACTIVE MAP</p><h1>互动地图</h1><p>查看景点分布，规划景区内的步行或驾车路线。</p></div>
      <span>{{ attractions.length }} 个景点已标记</span>
    </section>
    <section class="interactive-map-layout">
      <aside class="map-sidebar">
        <div class="route-planner">
          <h2>路线规划</h2>
          <label>起点<select v-model="originId"><option value="">请选择</option><option v-for="item in attractions" :key="item.attraction_id" :value="item.attraction_id">{{ item.name }}</option></select></label>
          <label>终点<select v-model="destinationId"><option value="">请选择</option><option v-for="item in attractions" :key="item.attraction_id" :value="item.attraction_id">{{ item.name }}</option></select></label>
          <div class="route-mode-switch"><button type="button" :class="{ active: routeMode === 'walking' }" @click="routeMode = 'walking'">步行</button><button type="button" :class="{ active: routeMode === 'driving' }" @click="routeMode = 'driving'">驾车</button></div>
          <button class="primary-button" type="button" @click="planRoute">开始规划</button>
          <p class="view-notice">{{ routeStatus }}</p>
        </div>
        <div class="map-attraction-list">
          <button v-for="item in attractions" :key="item.attraction_id" type="button" :class="{ active: selected?.attraction_id === item.attraction_id }" @click="selectAttraction(item)">
            <img :src="item.cover_image_url || '/static/attraction-placeholder.svg'" :alt="item.name" />
            <span><strong>{{ item.name }}</strong><small>{{ item.category }} · {{ item.suggested_duration_minutes }} 分钟</small></span>
          </button>
        </div>
      </aside>
      <section class="map-canvas-panel">
        <div id="interactiveMap" class="interactive-map-canvas" aria-label="灵山胜境互动地图"></div>
        <p class="map-notice">{{ interactiveMap.notice.value }}</p>
        <article v-if="selected" class="map-selected-card">
          <img :src="selected.cover_image_url || '/static/attraction-placeholder.svg'" :alt="selected.name" />
          <div><small>{{ selected.category }}</small><h2>{{ selected.name }}</h2><p>{{ selected.summary }}</p><button type="button" @click="drawerAttraction = selected">查看详情</button></div>
        </article>
        <ol v-if="routeSummary?.steps?.length" class="map-route-steps"><li v-for="step in routeSummary.steps" :key="step.index || step.instruction">{{ step.instruction }}</li></ol>
        <p v-if="routeSummary?.schema_version === 2" class="route-step-count">高德原始步骤共{{ routeSummary.total_step_count || routeSummary.steps?.length || 0 }}条，当前展示{{ routeSummary.steps?.length || 0 }}条关键步骤。</p>
      </section>
    </section>
    <AttractionDetailDrawer :attraction="drawerAttraction" @close="drawerAttraction = null" />
  </main>
</template>
