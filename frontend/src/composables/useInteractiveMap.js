import { onBeforeUnmount, ref } from "vue";

let amapLoadPromise = null;

export function useInteractiveMap(elementId) {
  const notice = ref("正在准备互动地图...");
  let map = null;
  let attractions = [];
  let onSelect = null;

  async function initialize(items, selectHandler) {
    attractions = items.filter((item) => Number.isFinite(item.longitude) && Number.isFinite(item.latitude));
    onSelect = selectHandler;
    const config = await fetchMapConfig();
    if (!config.enabled || !config.js_api_key || !config.security_js_code) {
      notice.value = config.message || "高德前端地图配置不完整，仍可使用景点列表和文字路线。";
      return false;
    }
    try {
      await loadAmapScript(config.js_api_key, config.security_js_code);
      createMap();
      drawMarkers();
      notice.value = "点击地图标记或左侧列表查看景点。";
      return true;
    } catch (error) {
      notice.value = `地图加载失败：${error.message}`;
      return false;
    }
  }

  function createMap() {
    const element = document.getElementById(elementId);
    if (!element || !window.AMap) return;
    map = new window.AMap.Map(element, {
      zoom: 16,
      center: attractions.length ? [attractions[0].longitude, attractions[0].latitude] : [120.09, 31.424],
      viewMode: "2D",
    });
  }

  function drawMarkers() {
    if (!map || !window.AMap) return;
    attractions.forEach((item) => {
      const marker = new window.AMap.Marker({
        map,
        position: [item.longitude, item.latitude],
        title: item.name,
      });
      marker.on("click", () => onSelect?.(item));
    });
    if (attractions.length) map.setFitView();
  }

  function selectAttraction(item) {
    if (!map || !item) return;
    map.setZoomAndCenter(17, [item.longitude, item.latitude]);
  }

  function renderRoute(summary) {
    if (!map || !window.AMap || !summary) return;
    const path = (summary.polyline || []).map(parseLngLat).filter(Boolean);
    if (path.length < 2) {
      notice.value = "路线坐标不足，暂时只能显示文字步骤。";
      return;
    }
    map.clearMap();
    drawMarkers();
    new window.AMap.Polyline({ map, path, strokeColor: "#2f766d", strokeWeight: 7, strokeOpacity: 0.9 });
    map.setFitView();
    notice.value = "路线已绘制，实际通行请以现场指引为准。";
  }

  function destroy() {
    if (map) map.destroy();
    map = null;
  }

  onBeforeUnmount(destroy);
  return { notice, initialize, selectAttraction, renderRoute, destroy };
}

async function fetchMapConfig() {
  const response = await fetch("/api/tools/map/config");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function loadAmapScript(apiKey, securityCode) {
  if (window.AMap) return Promise.resolve();
  if (amapLoadPromise) return amapLoadPromise;
  // 高德要求安全配置先于 JS API 脚本生效，否则新申请的 Web 端 Key 会校验失败。
  window._AMapSecurityConfig = { securityJsCode: securityCode };
  amapLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(apiKey)}`;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("高德 JS API 加载失败"));
    document.head.appendChild(script);
  });
  return amapLoadPromise;
}

function parseLngLat(point) {
  const [longitude, latitude] = String(point || "").split(",").map(Number);
  return Number.isFinite(longitude) && Number.isFinite(latitude) ? [longitude, latitude] : null;
}
