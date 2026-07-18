export { default as DigitalHumanStage } from "./components/DigitalHumanStage.vue";
export { default as DigitalHumanVoiceControls } from "./components/DigitalHumanVoiceControls.vue";
export { default as TranscriptConfirmation } from "./components/TranscriptConfirmation.vue";
export { usePcmAudio } from "./composables/usePcmAudio.js";
export {
  TAIL_PROTECTION_MS,
  createCaptureQualityTracker,
  createTailProtection,
} from "./lib/audioCaptureQuality.js";
export { float32Metrics, float32ToInt16, pcmRms } from "./lib/pcmAudio.js";
