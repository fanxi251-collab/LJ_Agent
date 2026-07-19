<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from "vue";
import { useRouteMap } from "../composables/useRouteMap";
import { findSuccessfulRouteSource, resolveRouteSummary } from "../lib/routeSummary.js";

const props = defineProps({
  sources: { type: Array, default: () => [] },
});

const expanded = ref(false);
const routeElement = ref(null);
const routeSource = computed(() => findSuccessfulRouteSource(props.sources));
const summary = computed(() => resolveRouteSummary(routeSource.value));
const visibleSteps = computed(() => {
  const steps = summary.value?.steps || [];
  return expanded.value ? steps : steps.slice(0, 3);
});
const routeMap = useRouteMap(routeElement);

async function toggleMap() {
  expanded.value = !expanded.value;
  if (!expanded.value) {
    routeMap.destroy();
    return;
  }
  // Wait for the lazy map container because AMap cannot attach to an element before Vue renders it.
  await nextTick();
  await routeMap.renderRoute(summary.value);
}

onBeforeUnmount(routeMap.destroy);
</script>

<template>
  <section v-if="summary" class="inline-route-card" aria-label="路线建议">
    <header class="inline-route-heading">
      <span class="inline-route-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <circle cx="6" cy="18" r="2" />
          <circle cx="18" cy="6" r="2" />
          <path d="M7.5 16.5c1.5-1.4 2.2-2.7 2-4-.3-1.7-2-2.5-1.8-4.1.2-1.4 1.7-2.4 4.4-2.4h3.8" />
        </svg>
      </span>
      <div>
        <small>为你找到一条路线</small>
        <strong>{{ summary.origin || "起点" }} → {{ summary.destination || "终点" }}</strong>
      </div>
    </header>

    <div class="inline-route-metrics">
      <span><small>方式</small><strong>{{ summary.mode_text || "路线" }}</strong></span>
      <span><small>距离</small><strong>{{ summary.distance_text || "待确认" }}</strong></span>
      <span><small>预计用时</small><strong>{{ summary.duration_text || "待确认" }}</strong></span>
    </div>

    <ol v-if="visibleSteps.length" class="inline-route-steps">
      <li v-for="step in visibleSteps" :key="step.index || step.instruction">
        {{ step.instruction || "继续前行" }}
      </li>
    </ol>

    <button class="inline-route-toggle" type="button" :aria-expanded="expanded" @click="toggleMap">
      {{ expanded ? "收起地图" : "展开地图" }}
      <span aria-hidden="true">{{ expanded ? "↑" : "↓" }}</span>
    </button>

    <div v-if="expanded" class="inline-route-map-wrap">
      <div ref="routeElement" class="inline-route-map" aria-label="高德路线地图"></div>
      <p>{{ routeMap.notice.value }}</p>
    </div>
  </section>
</template>
