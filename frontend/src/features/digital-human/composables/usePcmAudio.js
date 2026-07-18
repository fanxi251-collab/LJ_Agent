import { ref } from "vue";
import { createCaptureQualityTracker } from "../lib/audioCaptureQuality.js";
import { pcmRms } from "../lib/pcmAudio.js";

export function usePcmAudio({ onCaptureChunk }) {
  const audioLevel = ref(0);
  const inputLevel = ref(0);
  const inputQuality = ref("good");
  const autoGainState = ref("unknown");
  const microphoneState = ref("idle");
  const qualityTracker = createCaptureQualityTracker();
  let captureContext = null;
  let captureStream = null;
  let captureNode = null;
  let playbackContext = null;
  let playbackCursor = 0;
  const playbackSources = new Set();
  const levelTimers = new Set();

  async function preparePlayback() {
    if (!playbackContext) {
      // Create playback during a user gesture because browsers may block contexts created by later socket events.
      playbackContext = new AudioContext({ sampleRate: 24000 });
      playbackCursor = playbackContext.currentTime;
    }
    if (playbackContext.state === "suspended") await playbackContext.resume();
  }

  async function startCapture() {
    if (["starting", "recording"].includes(microphoneState.value)) return;
    microphoneState.value = "starting";
    qualityTracker.reset();
    inputLevel.value = 0;
    inputQuality.value = "good";
    try {
      captureStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const settings = captureStream.getAudioTracks?.()[0]?.getSettings?.() || {};
      autoGainState.value = "autoGainControl" in settings
        ? (settings.autoGainControl ? "enabled" : "disabled")
        : "unsupported";
      captureContext = new AudioContext();
      // Keep the worklet under the feature asset path so Vite development and production share one URL.
      await captureContext.audioWorklet.addModule("/digital-human/pcm-capture-worklet.js");
      const source = captureContext.createMediaStreamSource(captureStream);
      captureNode = new AudioWorkletNode(captureContext, "pcm-capture-processor");
      captureNode.port.onmessage = ({ data }) => {
        if (data?.type !== "pcm" || !(data.buffer instanceof ArrayBuffer)) return;
        const quality = qualityTracker.add(data.metrics);
        inputLevel.value = Math.min(1, quality.latestRms * 12);
        inputQuality.value = quality.inputQuality;
        onCaptureChunk?.(data.buffer, data.metrics);
      };
      source.connect(captureNode);
      // A silent gain keeps the worklet alive without feeding microphone audio to speakers.
      const silentGain = captureContext.createGain();
      silentGain.gain.value = 0;
      captureNode.connect(silentGain).connect(captureContext.destination);
      microphoneState.value = "recording";
      return true;
    } catch (error) {
      microphoneState.value = "denied";
      await stopCapture();
      throw error;
    }
  }

  async function stopCapture() {
    captureNode?.disconnect();
    captureNode = null;
    captureStream?.getTracks().forEach((track) => track.stop());
    captureStream = null;
    if (captureContext) await captureContext.close();
    captureContext = null;
    inputLevel.value = 0;
    if (microphoneState.value !== "denied") microphoneState.value = "idle";
  }

  function beginFinishing() {
    if (microphoneState.value === "recording") microphoneState.value = "finishing";
  }

  async function enqueuePlayback(arrayBuffer) {
    if (!arrayBuffer?.byteLength) return;
    await preparePlayback();
    const pcm = new Int16Array(arrayBuffer);
    const buffer = playbackContext.createBuffer(1, pcm.length, 24000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 32768;
    const source = playbackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackContext.destination);
    const startAt = Math.max(playbackCursor, playbackContext.currentTime + 0.015);
    playbackCursor = startAt + buffer.duration;
    playbackSources.add(source);
    const levelTimer = setTimeout(() => {
      levelTimers.delete(levelTimer);
      audioLevel.value = Math.min(1, pcmRms(pcm) * 3.2);
    }, Math.max(0, (startAt - playbackContext.currentTime) * 1000));
    levelTimers.add(levelTimer);
    source.onended = () => {
      playbackSources.delete(source);
      if (!playbackSources.size) audioLevel.value = 0;
    };
    source.start(startAt);
  }

  function clearPlayback() {
    for (const timer of levelTimers) clearTimeout(timer);
    levelTimers.clear();
    for (const source of playbackSources) {
      try {
        source.stop();
      } catch {
        // A source may already be ended; ignoring it keeps cancellation immediate.
      }
    }
    playbackSources.clear();
    playbackCursor = playbackContext?.currentTime || 0;
    audioLevel.value = 0;
  }

  async function dispose() {
    await stopCapture();
    clearPlayback();
    if (playbackContext) await playbackContext.close();
    playbackContext = null;
  }

  return {
    audioLevel,
    inputLevel,
    inputQuality,
    autoGainState,
    microphoneState,
    captureSnapshot: () => qualityTracker.snapshot(),
    preparePlayback,
    startCapture,
    beginFinishing,
    stopCapture,
    enqueuePlayback,
    clearPlayback,
    dispose,
  };
}
