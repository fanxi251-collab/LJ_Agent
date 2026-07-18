export const AUDIO_CHUNK_MS = 100;
export const TAIL_PROTECTION_MS = 300;
export const SILENCE_RMS = 0.006;
export const LOW_VOLUME_RMS = 0.02;
export const CLIPPING_RATIO = 0.01;
export const MIN_VOICED_DURATION_MS = 300;

export function createCaptureQualityTracker() {
  let frames = 0;
  let voicedFrames = 0;
  let voicedRmsTotal = 0;
  let consecutiveClippedFrames = 0;
  let severeClipping = false;
  let latestRms = 0;

  function add(metrics = {}) {
    const rms = finiteNumber(metrics.rms);
    const clippedRatio = finiteNumber(metrics.clippedRatio);
    frames += 1;
    latestRms = rms;
    if (rms >= SILENCE_RMS) {
      voicedFrames += 1;
      voicedRmsTotal += rms;
    }
    consecutiveClippedFrames = clippedRatio >= CLIPPING_RATIO
      ? consecutiveClippedFrames + 1
      : 0;
    if (consecutiveClippedFrames >= 3) severeClipping = true;
    return snapshot();
  }

  function snapshot() {
    const averageVoicedRms = voicedFrames ? voicedRmsTotal / voicedFrames : 0;
    const voicedDurationMs = voicedFrames * AUDIO_CHUNK_MS;
    const inputQuality = severeClipping
      ? "loud"
      : averageVoicedRms > 0 && averageVoicedRms < LOW_VOLUME_RMS
        ? "quiet"
        : "good";
    return {
      frames,
      voicedFrames,
      voicedDurationMs,
      averageVoicedRms,
      latestRms,
      severeClipping,
      inputQuality,
      canCommit: voicedDurationMs >= MIN_VOICED_DURATION_MS && !severeClipping,
    };
  }

  function reset() {
    frames = 0;
    voicedFrames = 0;
    voicedRmsTotal = 0;
    consecutiveClippedFrames = 0;
    severeClipping = false;
    latestRms = 0;
  }

  return { add, snapshot, reset };
}

export function createTailProtection({
  schedule = setTimeout,
  cancel = clearTimeout,
} = {}) {
  let handle = null;

  function start(callback) {
    stop();
    handle = schedule(async () => {
      handle = null;
      await callback();
    }, TAIL_PROTECTION_MS);
  }

  function stop() {
    if (handle === null) return;
    cancel(handle);
    handle = null;
  }

  return { start, cancel: stop, active: () => handle !== null };
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, number) : 0;
}
