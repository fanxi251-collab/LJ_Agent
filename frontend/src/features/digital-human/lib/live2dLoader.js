const CORE_SCRIPT_ID = "lingjing-live2d-cubism-core";
const CORE_URL = "/digital-human/live2d/live2dcubismcore.min.js";

let corePromise = null;
let libraryPromise = null;

function coreIsReady() {
  return Boolean(globalThis.Live2DCubismCore);
}

export function loadLive2DCore() {
  if (coreIsReady()) return Promise.resolve();
  if (corePromise) return corePromise;

  corePromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById(CORE_SCRIPT_ID);
    const script = existingScript || document.createElement("script");

    function finish() {
      if (coreIsReady()) resolve();
      else reject(new Error("Cubism Core 已加载，但未暴露运行时对象。"));
    }

    script.addEventListener("load", finish, { once: true });
    script.addEventListener("error", () => reject(new Error("Cubism Core 加载失败。")), { once: true });
    if (!existingScript) {
      script.id = CORE_SCRIPT_ID;
      script.src = CORE_URL;
      script.async = true;
      document.head.appendChild(script);
    }
  }).catch((error) => {
    corePromise = null;
    document.getElementById(CORE_SCRIPT_ID)?.remove();
    throw error;
  });

  return corePromise;
}

export async function loadLive2DLibrary() {
  await loadLive2DCore();
  // Load Pixi together with the adapter so text-only visitors do not download the rendering stack.
  libraryPromise ||= Promise.all([
    import("pixi.js"),
    import("pixi-live2d-display/cubism4"),
  ]).then(([PIXI, { Live2DModel }]) => ({ PIXI, Live2DModel })).catch((error) => {
      libraryPromise = null;
      throw error;
    });
  return libraryPromise;
}
