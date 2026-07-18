import assert from "node:assert/strict";
import test from "node:test";

import { usePcmAudio } from "../src/features/digital-human/composables/usePcmAudio.js";
import {
  TAIL_PROTECTION_MS,
  createCaptureQualityTracker,
  createTailProtection,
} from "../src/features/digital-human/lib/audioCaptureQuality.js";

test("microphone exposes a starting state while browser permission is pending", async () => {
  let rejectPermission;
  const permission = new Promise((resolve, reject) => {
    rejectPermission = reject;
  });
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { mediaDevices: { getUserMedia: () => permission } },
  });
  const audio = usePcmAudio({ onCaptureChunk() {} });

  const capture = audio.startCapture();
  const stateWhileWaiting = audio.microphoneState.value;
  rejectPermission(new Error("permission denied for test"));
  await assert.rejects(capture);

  assert.equal(stateWhileWaiting, "starting");
  assert.equal(audio.microphoneState.value, "denied");
});

test("microphone requests browser gain, echo, noise and mono processing", async () => {
  let requestedConstraints;
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getUserMedia: (constraints) => {
          requestedConstraints = constraints;
          return Promise.reject(new Error("stop after inspecting constraints"));
        },
      },
    },
  });
  const audio = usePcmAudio({ onCaptureChunk() {} });

  await assert.rejects(audio.startCapture());

  assert.deepEqual(requestedConstraints.audio, {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  });
});

test("capture quality tracks speech, low volume and sustained clipping", () => {
  const quality = createCaptureQualityTracker();

  quality.add({ rms: 0.018, peak: 0.4, clippedRatio: 0 });
  quality.add({ rms: 0.021, peak: 0.5, clippedRatio: 0 });
  quality.add({ rms: 0.03, peak: 1, clippedRatio: 0.02 });
  quality.add({ rms: 0.03, peak: 1, clippedRatio: 0.02 });
  quality.add({ rms: 0.03, peak: 1, clippedRatio: 0.02 });

  assert.equal(quality.snapshot().inputQuality, "loud");
  assert.equal(quality.snapshot().severeClipping, true);
  assert.equal(quality.snapshot().voicedDurationMs, 500);
});

test("capture quality rejects short silence but submits quiet speech", () => {
  const silence = createCaptureQualityTracker();
  silence.add({ rms: 0.001, peak: 0.002, clippedRatio: 0 });
  silence.add({ rms: 0.001, peak: 0.002, clippedRatio: 0 });
  assert.equal(silence.snapshot().canCommit, false);

  const quietSpeech = createCaptureQualityTracker();
  quietSpeech.add({ rms: 0.01, peak: 0.05, clippedRatio: 0 });
  quietSpeech.add({ rms: 0.01, peak: 0.05, clippedRatio: 0 });
  quietSpeech.add({ rms: 0.01, peak: 0.05, clippedRatio: 0 });
  assert.equal(quietSpeech.snapshot().canCommit, true);
  assert.equal(quietSpeech.snapshot().inputQuality, "quiet");
  assert.equal(TAIL_PROTECTION_MS, 300);
});

test("tail protection finishes after 300ms and cancellation suppresses commit", async () => {
  const scheduled = [];
  const tail = createTailProtection({
    schedule(callback, delay) {
      scheduled.push({ callback, delay, cancelled: false });
      return scheduled.length - 1;
    },
    cancel(handle) {
      scheduled[handle].cancelled = true;
    },
  });
  let commits = 0;

  tail.start(() => { commits += 1; });
  assert.equal(scheduled[0].delay, 300);
  tail.cancel();
  if (!scheduled[0].cancelled) await scheduled[0].callback();
  assert.equal(commits, 0);

  tail.start(() => { commits += 1; });
  await scheduled[1].callback();
  assert.equal(commits, 1);
  assert.equal(tail.active(), false);
});
