<script setup>
import { computed, onMounted, watch } from "vue";
import { useRouteMap } from "../composables/useRouteMap";

const props = defineProps({
  sources: { type: Array, required: true },
});

const routeSource = computed(() => {
  return (props.sources || []).find((source) => {
    const metadata = source.metadata || {};
    return metadata.source_type === "amap_route" && (metadata.route_summary || metadata.polyline);
  });
});

const summary = computed(() => routeSource.value?.metadata?.route_summary || routeSource.value?.metadata || null);
const routeMap = useRouteMap("routeMap");

watch(summary, (value) => {
  routeMap.renderRoute(value);
});

onMounted(() => routeMap.renderRoute(summary.value));
</script>

<template>
  <section class="route-panel">
    <div class="panel-heading">
      <h2>路线地图</h2>
      <span v-if="summary">
        {{ summary.mode_text || "路线" }} {{ summary.distance_text || "--" }}，预计{{ summary.duration_text || "--" }}
      </span>
    </div>
    <div id="routeMap" class="route-map" aria-label="高德路线地图"></div>
    <p class="route-notice">{{ routeMap.notice.value }}</p>
    <ol class="route-steps">
      <li v-if="!summary">暂无路线数据。提问“从无锡站到灵山胜境怎么走”后显示。</li>
      <li v-for="step in (summary?.steps || []).slice(0, 8)" :key="step.instruction">
        {{ step.instruction || "继续前行" }}
      </li>
    </ol>
  </section>
</template>
