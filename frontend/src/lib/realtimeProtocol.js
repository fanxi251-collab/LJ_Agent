export function buildRealtimeUrl(locationLike, visitorId, sessionId = "") {
  const protocol = locationLike.protocol === "https:" ? "wss:" : "ws:";
  const params = new URLSearchParams({ visitor_id: visitorId });
  if (sessionId) params.set("session_id", sessionId);
  return `${protocol}//${locationLike.host}/api/visitor/realtime?${params}`;
}

export function responseModalities(mode) {
  return mode === "avatar" ? ["audio", "text"] : ["text"];
}

export function buildModeSetEvent(mode) {
  return { type: "mode.set", mode: mode === "avatar" ? "avatar" : "text" };
}

export function buildAvatarSetEvent(avatarId) {
  return { type: "avatar.set", avatar_id: normalizeAvatarId(avatarId) };
}

export function buildTranscriptConfirmEvent(turnId, text) {
  return {
    type: "transcript.confirm",
    turn_id: String(turnId || ""),
    text: String(text || "").trim(),
  };
}

export function resolveAvatarCaption(assistantText, userText) {
  return String(assistantText || "").trim() || String(userText || "").trim();
}

export function resolveAvatarAudioState({ eventType, playbackActive, turnActive }) {
  if (playbackActive) return "speaking";
  if (eventType === "assistant.audio.started") return "thinking";
  if (eventType === "turn.completed") return "idle";
  if (["assistant.audio.done", "playback.ended"].includes(eventType)) {
    return turnActive ? "thinking" : "idle";
  }
  return turnActive ? "thinking" : "idle";
}

export function isRealtimeBusy(activeTurnId, playbackActive) {
  return Boolean(activeTurnId) || Boolean(playbackActive);
}

export function createTurnId() {
  const random = globalThis.crypto?.randomUUID?.().replaceAll("-", "");
  return `turn_${random || `${Date.now()}_${Math.random().toString(16).slice(2)}`}`;
}
import { normalizeAvatarId } from "../features/digital-human/lib/live2dCharacters.js";
