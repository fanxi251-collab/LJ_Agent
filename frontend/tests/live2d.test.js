import assert from "node:assert/strict";
import test from "node:test";

import * as live2dMotion from "../src/features/digital-human/lib/live2dMotion.js";
import {
  LIP_SYNC_ATTACK_MS,
  LIP_SYNC_RELEASE_MS,
  applyLipSyncValue,
  live2DMouthTarget,
  resolveLipSyncIds,
  smoothLipSyncValue,
} from "../src/features/digital-human/lib/live2dMotion.js";
import {
  EXPRESSION_DEBOUNCE_MS,
  createExpressionDebouncer,
  resolveLive2DExpression,
} from "../src/features/digital-human/lib/live2dExpression.js";

test("Live2D mouth opens only while speaking and clamps amplified audio", () => {
  assert.equal(live2DMouthTarget("idle", 0.8), 0);
  assert.equal(live2DMouthTarget("speaking", -1), 0);
  assert.equal(live2DMouthTarget("speaking", 0.5), 0.65);
  assert.equal(live2DMouthTarget("speaking", 1), 1);
});

test("Live2D mouth uses a faster attack than release", () => {
  const opened = smoothLipSyncValue(0, 1, 60);
  const remainingAfterRelease = smoothLipSyncValue(1, 0, 60);

  assert.equal(LIP_SYNC_ATTACK_MS, 60);
  assert.equal(LIP_SYNC_RELEASE_MS, 120);
  assert.ok(opened > 0.63 && opened < 0.64);
  assert.ok(remainingAfterRelease > 0.6 && remainingAfterRelease < 0.61);
});

test("Live2D mouth writes every model-provided lip sync parameter", () => {
  const writes = [];
  const internalModel = {
    motionManager: {
      lipSyncIds: ["ParamA", "ParamMouthOpenY"],
    },
    coreModel: {
      setParameterValueById(id, value) {
        writes.push([id, value]);
      },
    },
  };

  applyLipSyncValue(internalModel, 0.72);

  assert.deepEqual(writes, [
    ["ParamA", 0.72],
    ["ParamMouthOpenY", 0.72],
  ]);
});

test("Live2D lip sync IDs prefer the real motion manager and safely fall back", () => {
  assert.deepEqual(resolveLipSyncIds({
    motionManager: { lipSyncIds: ["", "ParamA", "ParamA", null] },
    lipSyncIds: ["ParamMouthOpenY"],
  }), ["ParamA"]);
  assert.deepEqual(resolveLipSyncIds({
    motionManager: { lipSyncIds: ["", null] },
    lipSyncIds: ["ParamMouthOpenY", "ParamMouthOpenY"],
  }), ["ParamMouthOpenY"]);
  assert.deepEqual(resolveLipSyncIds({
    motionManager: { lipSyncIds: "ParamA" },
    lipSyncIds: ["ParamLegacy"],
  }), ["ParamLegacy"]);
  assert.deepEqual(resolveLipSyncIds({}), []);
});

test("Live2D missing lip sync parameters warn only once per renderer", () => {
  assert.equal(typeof live2dMotion.createMissingLipSyncWarning, "function");
  const warnings = [];
  const warnIfMissing = live2dMotion.createMissingLipSyncWarning((message) => {
    warnings.push(message);
  });

  assert.equal(warnIfMissing({ motionManager: { lipSyncIds: ["ParamA"] } }), false);
  assert.equal(warnIfMissing({ motionManager: { lipSyncIds: [] } }), true);
  assert.equal(warnIfMissing({ motionManager: { lipSyncIds: [] } }), false);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /Live2D.*口型参数/);
});

test("Live2D lip sync writes clamp values to the model parameter range", () => {
  const writes = [];
  const internalModel = {
    motionManager: { lipSyncIds: ["ParamA"] },
    coreModel: {
      setParameterValueById(id, value) { writes.push([id, value]); },
    },
  };

  applyLipSyncValue(internalModel, -0.5);
  applyLipSyncValue(internalModel, 1.5);

  assert.deepEqual(writes, [["ParamA", 0], ["ParamA", 1]]);
});

test("Live2D expression uses professional categories and conflict priority", () => {
  assert.equal(resolveLive2DExpression({ state: "idle", assistantText: "欢迎您" }), "neutral");
  assert.equal(resolveLive2DExpression({ state: "speaking", assistantText: "欢迎体验精彩景区" }), "joy");
  assert.equal(resolveLive2DExpression({ state: "speaking", assistantText: "这里非常壮观，是首次开放" }), "surprise");
  assert.equal(resolveLive2DExpression({ state: "speaking", assistantText: "很抱歉，特别活动暂不可用" }), "apology");
  assert.equal(resolveLive2DExpression({ state: "error", assistantText: "欢迎" }), "apology");
  assert.equal(resolveLive2DExpression({ state: "speaking", assistantText: "普通路线说明" }), "neutral");
});

test("Live2D expression waits 300ms and reset returns to neutral immediately", () => {
  const scheduled = [];
  const committed = [];
  const debouncer = createExpressionDebouncer((expression) => committed.push(expression), {
    schedule(callback, delay) {
      scheduled.push({ callback, delay, cancelled: false });
      return scheduled.length - 1;
    },
    cancel(handle) {
      scheduled[handle].cancelled = true;
    },
  });

  debouncer.update("joy");
  assert.equal(EXPRESSION_DEBOUNCE_MS, 300);
  assert.equal(scheduled[0].delay, 300);
  assert.deepEqual(committed, []);

  debouncer.reset();
  assert.equal(scheduled[0].cancelled, true);
  assert.deepEqual(committed, ["neutral"]);
});
