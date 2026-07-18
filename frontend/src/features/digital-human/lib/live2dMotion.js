export const LIP_SYNC_ATTACK_MS = 60;
export const LIP_SYNC_RELEASE_MS = 120;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function live2DMouthTarget(state, audioLevel) {
  if (state !== "speaking") return 0;
  return clamp(Number(audioLevel || 0) * 1.3, 0, 1);
}

export function smoothLipSyncValue(current, target, deltaMs) {
  const safeCurrent = clamp(Number(current || 0), 0, 1);
  const safeTarget = clamp(Number(target || 0), 0, 1);
  const timeConstant = safeTarget > safeCurrent
    ? LIP_SYNC_ATTACK_MS
    : LIP_SYNC_RELEASE_MS;
  const alpha = 1 - Math.exp(-Math.max(0, Number(deltaMs || 0)) / timeConstant);
  return safeCurrent + ((safeTarget - safeCurrent) * alpha);
}

export function resolveLipSyncIds(internalModel) {
  const motionManagerIds = internalModel?.motionManager?.lipSyncIds;
  const legacyIds = internalModel?.lipSyncIds;
  const primaryIds = Array.isArray(motionManagerIds)
    ? [...new Set(motionManagerIds.filter(Boolean))]
    : [];
  if (primaryIds.length) return primaryIds;
  return Array.isArray(legacyIds) ? [...new Set(legacyIds.filter(Boolean))] : [];
}

export function createMissingLipSyncWarning(warn = (message) => console.warn(message)) {
  let warned = false;
  return (internalModel) => {
    if (resolveLipSyncIds(internalModel).length || warned) return false;
    warned = true;
    // Warn once because silent lip-sync failures otherwise look like an animation limitation to operators.
    warn("Live2D 模型未声明可用的口型参数，语音将继续播放但嘴型不会变化。");
    return true;
  };
}

export function applyLipSyncValue(internalModel, value) {
  const coreModel = internalModel?.coreModel;
  if (!coreModel?.setParameterValueById) return;
  // Read IDs from the renderer's real motion manager so model-specific mouth parameters are never hard-coded.
  for (const parameterId of resolveLipSyncIds(internalModel)) {
    coreModel.setParameterValueById(parameterId, clamp(Number(value || 0), 0, 1));
  }
}
