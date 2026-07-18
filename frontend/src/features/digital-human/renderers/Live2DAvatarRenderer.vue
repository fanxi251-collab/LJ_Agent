<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { loadLive2DLibrary } from "../lib/live2dLoader.js";
import {
  applyLipSyncValue,
  createMissingLipSyncWarning,
  live2DMouthTarget,
  smoothLipSyncValue,
} from "../lib/live2dMotion.js";

const MODEL_URL = "/digital-human/live2d/mao_pro/mao_pro.model3.json";

const props = defineProps({
  state: { type: String, default: "idle" },
  audioLevel: { type: Number, default: 0 },
  expression: { type: String, default: "exp_01" },
});
const emit = defineEmits(["ready", "error"]);

const host = ref(null);
let application = null;
let model = null;
let resizeObserver = null;
let currentMouthValue = 0;
let lifecycleToken = 0;
let lipSyncHandler = null;
let tickerHandler = null;
const warnIfMissingLipSync = createMissingLipSyncWarning();

function fitModel() {
  if (!application || !model || !host.value) return;
  const width = Math.max(1, host.value.clientWidth);
  const height = Math.max(1, host.value.clientHeight);
  const unscaledWidth = model.width / Math.max(model.scale.x, 0.0001);
  const unscaledHeight = model.height / Math.max(model.scale.y, 0.0001);
  const scale = Math.min((width * 0.92) / unscaledWidth, (height * 1.06) / unscaledHeight);
  model.scale.set(scale);
  model.position.set(width / 2, (height / 2) + (height * 0.04));
  application.renderer.resize(width, height);
}

async function applyExpression(expression) {
  if (!model) return;
  try {
    await model.expression(expression);
  } catch (error) {
    // Keep the avatar usable when one optional expression fails, because speech is the primary interaction.
    console.warn(`Live2D expression ${expression} failed`, error);
  }
}

function destroyRenderer() {
  lifecycleToken += 1;
  resizeObserver?.disconnect();
  resizeObserver = null;

  if (application && tickerHandler) application.ticker.remove(tickerHandler);
  if (model?.internalModel && lipSyncHandler) {
    model.internalModel.off("beforeModelUpdate", lipSyncHandler);
  }
  tickerHandler = null;
  lipSyncHandler = null;
  currentMouthValue = 0;

  if (application && model) application.stage.removeChild(model);
  model?.destroy({ children: true, texture: true, baseTexture: true });
  model = null;
  application?.destroy(true, { children: true, texture: true, baseTexture: true });
  application = null;
}

async function initializeRenderer() {
  destroyRenderer();
  const token = lifecycleToken;
  await nextTick();

  try {
    const { PIXI, Live2DModel } = await loadLive2DLibrary();
    if (token !== lifecycleToken || !host.value) return;
    Live2DModel.registerTicker(PIXI.Ticker);

    application = new PIXI.Application({
      antialias: true,
      autoDensity: true,
      backgroundAlpha: 0,
      resolution: Math.min(globalThis.devicePixelRatio || 1, 2),
    });
    host.value.appendChild(application.view);

    const loadedModel = await Live2DModel.from(MODEL_URL, { autoInteract: false });
    if (token !== lifecycleToken || !application) {
      loadedModel.destroy({ children: true, texture: true, baseTexture: true });
      return;
    }
    model = loadedModel;
    warnIfMissingLipSync(model.internalModel);
    model.anchor.set(0.5, 0.5);
    application.stage.addChild(model);

    tickerHandler = () => {
      const target = live2DMouthTarget(props.state, props.audioLevel);
      currentMouthValue = smoothLipSyncValue(
        currentMouthValue,
        target,
        application?.ticker.deltaMS || 16.67,
      );
    };
    lipSyncHandler = () => applyLipSyncValue(model?.internalModel, currentMouthValue);
    application.ticker.add(tickerHandler);
    model.internalModel.on("beforeModelUpdate", lipSyncHandler);

    resizeObserver = new ResizeObserver(fitModel);
    resizeObserver.observe(host.value);
    fitModel();
    await applyExpression(props.expression);
    emit("ready");
  } catch (error) {
    destroyRenderer();
    emit("error", error instanceof Error ? error : new Error(String(error)));
  }
}

watch(() => props.expression, (expression) => applyExpression(expression));
watch(() => props.state, (state) => {
  if (state !== "speaking") currentMouthValue = 0;
});

onMounted(initializeRenderer);
onBeforeUnmount(destroyRenderer);
</script>

<template>
  <div ref="host" class="live2d-avatar" role="img" aria-label="Mao Pro Live2D 数字人导游"></div>
</template>

<style scoped>
.live2d-avatar {
  position: absolute;
  inset: 34px 14px 58px;
  min-height: 280px;
  pointer-events: none;
}

.live2d-avatar :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
