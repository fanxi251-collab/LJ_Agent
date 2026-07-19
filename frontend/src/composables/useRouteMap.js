import { ref, unref } from "vue";

let amapLoadPromise = null;

export function useRouteMap(target) {
  const notice = ref("暂无路线数据。");
  let amapMap = null;

  async function renderRoute(summary) {
    if (!summary) {
      notice.value = "暂无路线数据。";
      return;
    }
    notice.value = "正在加载高德地图...";
    try {
      const config = await fetchMapConfig();
      if (!config.enabled || !config.js_api_key || !config.security_js_code) {
        notice.value = config.message || "高德前端地图配置不完整，暂只显示文字路线。";
        return;
      }
      await loadAmapScript(config.js_api_key, config.security_js_code);
      drawRoute(summary);
      notice.value = "路线由高德地图绘制，实际通行请以现场交通为准。";
    } catch (error) {
      notice.value = `地图加载失败：${error.message}`;
    }
  }

  function drawRoute(summary) {
    const element = resolveMapElement(target);
    if (!element || !window.AMap) {
      return;
    }
    const path = (summary.polyline || []).map(parseLngLat).filter(Boolean);
    if (path.length < 2) {
      notice.value = "路线坐标不足，暂无法绘制地图。";
      return;
    }
    if (!amapMap) {
      amapMap = new window.AMap.Map(element, {
        zoom: 11,
        center: path[0],
        viewMode: "2D",
      });
    }
    amapMap.clearMap();
    new window.AMap.Marker({ map: amapMap, position: path[0], title: summary.origin || "起点" });
    new window.AMap.Marker({ map: amapMap, position: path[path.length - 1], title: summary.destination || "终点" });
    new window.AMap.Polyline({
      map: amapMap,
      path,
      strokeColor: "#4f75ff",
      strokeWeight: 7,
      strokeOpacity: 0.9,
    });
    amapMap.setFitView();
  }

  function destroy() {
    if (!amapMap) return;
    // Release WebGL and DOM listeners because history changes can remove several inline maps at once.
    amapMap.destroy();
    amapMap = null;
  }

  return { notice, renderRoute, destroy };
}

function resolveMapElement(target) {
  const elementOrId = unref(target);
  return typeof elementOrId === "string"
    ? document.getElementById(elementOrId)
    : elementOrId || null;
}

async function fetchMapConfig() {
  const response = await fetch("/api/tools/map/config");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function loadAmapScript(jsApiKey, securityCode) {
  if (window.AMap) {
    return Promise.resolve();
  }
  if (amapLoadPromise) {
    return amapLoadPromise;
  }
  // 高德要求安全配置先于 JS API 脚本生效，否则新申请的 Web 端 Key 会校验失败。
  window._AMapSecurityConfig = { securityJsCode: securityCode };
  amapLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(jsApiKey)}`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("高德 JS API 加载失败"));
    document.head.appendChild(script);
  });
  return amapLoadPromise;
}

function parseLngLat(point) {
  const [lng, lat] = String(point || "").split(",").map(Number);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
    return null;
  }
  return [lng, lat];
}
