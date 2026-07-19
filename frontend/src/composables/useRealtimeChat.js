import { computed, onBeforeUnmount, ref } from "vue";
import {
  buildModeSetEvent,
  buildAvatarSetEvent,
  buildRealtimeUrl,
  buildTranscriptConfirmEvent,
  createTurnId,
  isRealtimeBusy,
  resolveAvatarAudioState,
  resolveAvatarCaption,
} from "../lib/realtimeProtocol";
import {
  createTailProtection,
  loadAvatarPreference,
  normalizeAvatarId,
  saveAvatarPreference,
  usePcmAudio,
} from "../features/digital-human";
import { findSuccessfulRouteSource } from "../lib/routeSummary.js";

export function useRealtimeChat({ currentSessionId, visitorId, onSessionChanged }) {
  const mode = ref("text");
  const messages = ref([]);
  const sources = ref([]);
  const confidence = ref("--");
  const serviceState = ref("正在连接");
  const avatarState = ref("idle");
  const avatarId = ref(loadAvatarPreference());
  const avatarSynchronized = ref(false);
  const liveTranscript = ref("");
  const assistantTranscript = ref("");
  const activeTurnId = ref("");
  const socketState = ref("closed");
  const transcriptConfirmation = ref(null);
  const correctionNotice = ref("");
  let socket = null;
  let connectPromise = null;
  let stopRecordingRequested = false;
  let capturedAudioChunks = 0;
  const tailProtection = createTailProtection();

  const audio = usePcmAudio({
    onCaptureChunk: (chunk) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(chunk);
        capturedAudioChunks += 1;
      }
    },
    onPlaybackStateChange: (active) => {
      // Browser playback owns the speaking state because upstream completion can arrive before sound ends.
      avatarState.value = resolveAvatarAudioState({
        eventType: active ? "playback.started" : "playback.ended",
        playbackActive: active,
        turnActive: Boolean(activeTurnId.value),
      });
    },
  });
  const isLoading = computed(() => isRealtimeBusy(activeTurnId.value, audio.playbackActive.value));
  const avatarReady = computed(() => mode.value !== "avatar" || avatarSynchronized.value);
  const avatarCaption = computed(() =>
    resolveAvatarCaption(assistantTranscript.value, liveTranscript.value),
  );
  const hasRouteSource = computed(() =>
    Boolean(findSuccessfulRouteSource(sources.value)),
  );

  function connect(sessionId = currentSessionId.value) {
    disconnect(false);
    // Every socket must re-acknowledge the role so a reconnect cannot reuse stale voice state.
    avatarSynchronized.value = false;
    socketState.value = "connecting";
    connectPromise = new Promise((resolve) => {
      socket = new WebSocket(buildRealtimeUrl(window.location, visitorId, sessionId));
      socket.binaryType = "arraybuffer";
      socket.onopen = () => {
        socketState.value = "open";
        serviceState.value = "智能导游在线";
        resolve();
      };
      socket.onmessage = async ({ data }) => {
        if (data instanceof ArrayBuffer) {
          try {
            await audio.enqueuePlayback(data);
          } catch {
            // Keep text usable when browser autoplay or the selected output device rejects PCM playback.
            avatarState.value = "error";
            serviceState.value = "语音播放失败，回答字幕仍可查看";
          }
          return;
        }
        handleServerEvent(JSON.parse(data));
      };
      socket.onerror = () => {
        serviceState.value = "连接异常，正在等待恢复";
        socketState.value = "error";
        resolve();
      };
      socket.onclose = () => {
        socketState.value = "closed";
        avatarSynchronized.value = false;
        if (activeTurnId.value) failActiveMessage("连接已断开，请重试。", true);
        resolve();
      };
    });
    return connectPromise;
  }

  async function ensureConnected() {
    if (socket?.readyState === WebSocket.OPEN) return;
    if (socketState.value !== "connecting") connect();
    await connectPromise;
    if (socket?.readyState !== WebSocket.OPEN) throw new Error("实时连接尚未建立");
  }

  async function ask(text) {
    const question = String(text || "").trim();
    if (!question) return;
    try {
      if (mode.value === "avatar") {
        audio.preparePlayback().catch(() => {
          serviceState.value = "浏览器暂未允许语音播放，将继续显示回答字幕";
        });
      }
      await ensureConnected();
      ensureAvatarReady();
      if (activeTurnId.value) cancelResponse();
      const turnId = createTurnId();
      activeTurnId.value = turnId;
      messages.value.push({ id: `${turnId}_user`, role: "user", content: question });
      messages.value.push({
        id: turnId,
        role: "assistant",
        content: "",
        pending: true,
        retryQuestion: question,
      });
      sources.value = [];
      confidence.value = "--";
      liveTranscript.value = question;
      assistantTranscript.value = "";
      avatarState.value = "thinking";
      serviceState.value = "正在检索景区资料";
      sendJson({ type: "text.submit", turn_id: turnId, text: question });
    } catch (error) {
      failActiveMessage(error.message || "发送失败，请重试。", true);
    }
  }

  async function startRecording() {
    let recordingTurnId = "";
    try {
      stopRecordingRequested = false;
      tailProtection.cancel();
      capturedAudioChunks = 0;
      audio.preparePlayback().catch(() => {
        serviceState.value = "浏览器暂未允许语音播放，将继续显示回答字幕";
      });
      await ensureConnected();
      ensureAvatarReady();
      cancelResponse();
      const turnId = createTurnId();
      recordingTurnId = turnId;
      activeTurnId.value = turnId;
      liveTranscript.value = "";
      assistantTranscript.value = "";
      transcriptConfirmation.value = null;
      correctionNotice.value = "";
      avatarState.value = "listening";
      sendJson({ type: "audio.start", turn_id: turnId });
      await audio.startCapture();
      if (stopRecordingRequested) {
        await audio.stopCapture();
        sendJson({ type: "response.cancel", turn_id: turnId });
        activeTurnId.value = "";
        avatarState.value = "idle";
        serviceState.value = "麦克风已就绪，请重新按住说话";
        return;
      }
      serviceState.value = "正在聆听，松开发送";
    } catch {
      if (recordingTurnId) {
        sendJson({ type: "response.cancel", turn_id: recordingTurnId });
      }
      if (activeTurnId.value !== recordingTurnId) return;
      avatarState.value = "error";
      serviceState.value = "麦克风不可用，请使用文字输入";
      activeTurnId.value = "";
    }
  }

  async function stopRecording() {
    if (audio.microphoneState.value === "starting") {
      stopRecordingRequested = true;
      serviceState.value = "正在启动麦克风，完成后请重新按住说话";
      return;
    }
    if (audio.microphoneState.value !== "recording" || !activeTurnId.value) return;
    const turnId = activeTurnId.value;
    audio.beginFinishing();
    serviceState.value = "正在补全句尾语音";
    tailProtection.start(async () => {
      await audio.stopCapture();
      if (turnId !== activeTurnId.value) return;
      const quality = audio.captureSnapshot();
      if (!capturedAudioChunks || quality.voicedDurationMs < 300) {
        sendJson({ type: "response.cancel", turn_id: turnId });
        activeTurnId.value = "";
        avatarState.value = "idle";
        serviceState.value = "未检测到完整语音，请按住按钮说完后再松开";
        return;
      }
      if (quality.severeClipping) {
        sendJson({ type: "response.cancel", turn_id: turnId });
        activeTurnId.value = "";
        avatarState.value = "error";
        serviceState.value = "录音音量过大，请稍微远离麦克风后重试";
        return;
      }
      sendJson({ type: "audio.commit", turn_id: turnId });
      avatarState.value = "thinking";
      serviceState.value = quality.inputQuality === "quiet"
        ? "正在识别语音（录音音量偏低）"
        : "正在识别语音";
    });
  }

  function setMode(nextMode) {
    if (!['text', 'avatar'].includes(nextMode) || nextMode === mode.value) return;
    cancelResponse();
    mode.value = nextMode;
    liveTranscript.value = "";
    assistantTranscript.value = "";
    sendJson(buildModeSetEvent(nextMode));
    serviceState.value = nextMode === "avatar" ? "数字人已就绪" : "常规对话已就绪";
    avatarState.value = "idle";
  }

  function setAvatar(nextAvatarId) {
    const normalized = normalizeAvatarId(nextAvatarId);
    if (normalized !== avatarId.value) cancelResponse();
    avatarId.value = saveAvatarPreference(globalThis.localStorage, normalized);
    avatarSynchronized.value = false;
    sendJson(buildAvatarSetEvent(avatarId.value));
    serviceState.value = "正在切换数字人形象";
    avatarState.value = "idle";
  }

  function ensureAvatarReady() {
    if (mode.value === "avatar" && !avatarSynchronized.value) {
      serviceState.value = "正在同步数字人角色，请稍候";
      throw new Error("数字人角色尚未同步完成");
    }
  }

  function cancelResponse() {
    tailProtection.cancel();
    transcriptConfirmation.value = null;
    if (!isRealtimeBusy(activeTurnId.value, audio.playbackActive.value)) return;
    stopRecordingRequested = true;
    if (activeTurnId.value) {
      sendJson({ type: "response.cancel", turn_id: activeTurnId.value });
    }
    audio.stopCapture();
    audio.clearPlayback();
    activeTurnId.value = "";
    avatarState.value = "idle";
  }

  function confirmTranscript(text) {
    const pending = transcriptConfirmation.value;
    const confirmed = String(text || "").trim();
    if (!pending || !confirmed) return;
    sendJson(buildTranscriptConfirmEvent(pending.turnId, confirmed));
    transcriptConfirmation.value = null;
    liveTranscript.value = confirmed;
    avatarState.value = "thinking";
    serviceState.value = "正在检索景区资料";
  }

  function handleServerEvent(event) {
    if (event.type === "session.ready") {
      // Reassert local mode after every connection because mode changes made while connecting are otherwise lost.
      sendJson(buildModeSetEvent(mode.value));
      avatarSynchronized.value = false;
      sendJson(buildAvatarSetEvent(avatarId.value));
      if (!event.upstream_available) serviceState.value = "语音服务暂不可用，可继续尝试文字回答";
      return;
    }
    if (event.type === "avatar.changed") {
      avatarId.value = saveAvatarPreference(globalThis.localStorage, event.avatar_id);
      avatarSynchronized.value = true;
      serviceState.value = mode.value === "avatar" ? "数字人已就绪" : serviceState.value;
      return;
    }
    if (event.type === "session.bound" && event.session_id) {
      currentSessionId.value = event.session_id;
      localStorage.setItem("lingjing_current_session_id", event.session_id);
      return;
    }
    if (event.type === "user.transcript.delta") {
      if (event.turn_id && event.turn_id !== activeTurnId.value) return;
      liveTranscript.value += event.delta || "";
      return;
    }
    if (event.type === "user.transcript.done") {
      if (event.turn_id !== activeTurnId.value) return;
      liveTranscript.value = event.text || liveTranscript.value;
      ensureVoiceMessages(event.turn_id, liveTranscript.value);
      transcriptConfirmation.value = null;
      correctionNotice.value = event.correction?.applied ? "已按景区词典纠正" : "";
      avatarState.value = "thinking";
      return;
    }
    if (event.type === "user.transcript.confirmation_required") {
      if (event.turn_id !== activeTurnId.value) return;
      transcriptConfirmation.value = {
        turnId: event.turn_id,
        text: event.text || liveTranscript.value,
        candidates: event.candidates || [],
      };
      liveTranscript.value = transcriptConfirmation.value.text;
      avatarState.value = "idle";
      serviceState.value = "转写结果需要确认";
      return;
    }
    if (event.type === "agent.meta") {
      if (event.turn_id !== activeTurnId.value) return;
      sources.value = event.sources || [];
      confidence.value = formatConfidence(event.confidence);
      return;
    }
    if (event.type === "assistant.text.delta") {
      if (event.turn_id !== activeTurnId.value) return;
      const delta = event.delta || "";
      ensureAssistantMessage(event.turn_id).content += delta;
      assistantTranscript.value += delta;
      return;
    }
    if (event.type === "assistant.text.done") {
      if (event.turn_id !== activeTurnId.value) return;
      const message = ensureAssistantMessage(event.turn_id);
      message.content = event.text || message.content;
      assistantTranscript.value = message.content;
      return;
    }
    if (event.type === "turn.reset") {
      if (event.turn_id !== activeTurnId.value) return;
      const message = ensureAssistantMessage(event.turn_id);
      message.content = "";
      audio.clearPlayback();
      avatarState.value = "thinking";
      serviceState.value = "连接已恢复，正在重新生成";
      return;
    }
    if (event.type === "assistant.audio.started") {
      if (event.turn_id !== activeTurnId.value) return;
      avatarState.value = resolveAvatarAudioState({
        eventType: event.type,
        playbackActive: audio.playbackActive.value,
        turnActive: true,
      });
      return;
    }
    if (event.type === "assistant.audio.done") {
      if (event.turn_id !== activeTurnId.value) return;
      avatarState.value = resolveAvatarAudioState({
        eventType: event.type,
        playbackActive: audio.playbackActive.value,
        turnActive: true,
      });
      return;
    }
    if (event.type === "turn.completed") {
      if (event.turn_id !== activeTurnId.value) return;
      const message = ensureAssistantMessage(event.turn_id);
      message.pending = false;
      message.sources = sources.value;
      activeTurnId.value = "";
      avatarState.value = resolveAvatarAudioState({
        eventType: event.type,
        playbackActive: audio.playbackActive.value,
        turnActive: false,
      });
      serviceState.value = "回答完成";
      onSessionChanged?.();
      return;
    }
    if (event.type === "turn.cancelled") {
      if (event.turn_id !== activeTurnId.value) return;
      audio.clearPlayback();
      activeTurnId.value = "";
      avatarState.value = "idle";
      return;
    }
    if (event.type === "error") {
      serviceState.value = event.message || "实时服务异常";
      if (!event.recoverable) failActiveMessage(serviceState.value, true);
    }
  }

  function ensureVoiceMessages(turnId, transcript) {
    if (!messages.value.some((message) => message.id === `${turnId}_user`)) {
      messages.value.push({ id: `${turnId}_user`, role: "user", content: transcript, voice: true });
    }
    ensureAssistantMessage(turnId, transcript);
  }

  function ensureAssistantMessage(turnId, retryQuestion = "") {
    let message = messages.value.find((item) => item.id === turnId && item.role === "assistant");
    if (!message) {
      message = {
        id: turnId,
        role: "assistant",
        content: "",
        pending: true,
        retryQuestion,
      };
      messages.value.push(message);
    }
    if (retryQuestion && !message.retryQuestion) message.retryQuestion = retryQuestion;
    return message;
  }

  function failActiveMessage(message, retryable) {
    // Stop buffered speech on failures so an error state cannot keep talking with stale lip movement.
    audio.clearPlayback();
    if (activeTurnId.value) {
      const target = ensureAssistantMessage(activeTurnId.value);
      target.error = message;
      target.retryable = retryable;
      target.pending = false;
      if (!target.retryQuestion) {
        const targetIndex = messages.value.indexOf(target);
        target.retryQuestion = [...messages.value.slice(0, targetIndex)]
          .reverse()
          .find((item) => item.role === "user")?.content || "";
      }
    }
    activeTurnId.value = "";
    avatarState.value = "error";
  }

  function restoreMessages(storedMessages) {
    messages.value = (storedMessages || []).map((message) => ({
      id: `stored_${message.message_id}`,
      role: message.role,
      content: message.content,
      sources: message.sources || [],
    }));
    const lastAssistant = [...(storedMessages || [])].reverse().find((item) => item.role === "assistant");
    sources.value = lastAssistant?.sources || [];
    connect(currentSessionId.value);
    serviceState.value = "历史会话已载入";
  }

  function resetConversation(message) {
    cancelResponse();
    messages.value = [];
    sources.value = [];
    confidence.value = "--";
    liveTranscript.value = "";
    assistantTranscript.value = "";
    connect("");
    serviceState.value = message || "已开启新会话";
  }

  function disconnect(clearAudio = true) {
    tailProtection.cancel();
    if (clearAudio) audio.clearPlayback();
    if (socket) {
      socket.onclose = null;
      socket.close();
      socket = null;
    }
    socketState.value = "closed";
  }

  function suspendForRoute() {
    tailProtection.cancel();
    stopRecordingRequested = true;
    // 缓存页面离场时只释放麦克风与扬声器，保留 WebSocket 让正在生成的文字回答能够继续完成。
    audio.stopCapture();
    audio.clearPlayback();
    if (avatarState.value === "listening" || avatarState.value === "speaking") {
      avatarState.value = activeTurnId.value ? "thinking" : "idle";
    }
  }

  function sendJson(event) {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(event));
  }

  function markKnowledgeUpdated() {
    serviceState.value = "资料已更新";
  }

  connect();
  onBeforeUnmount(async () => {
    disconnect();
    await audio.dispose();
  });

  return {
    mode,
    messages,
    sources,
    confidence,
    serviceState,
    avatarState,
    avatarId,
    avatarSynchronized,
    avatarReady,
    liveTranscript,
    assistantTranscript,
    transcriptConfirmation,
    correctionNotice,
    avatarCaption,
    isLoading,
    hasRouteSource,
    audioLevel: audio.audioLevel,
    inputLevel: audio.inputLevel,
    inputQuality: audio.inputQuality,
    autoGainState: audio.autoGainState,
    microphoneState: audio.microphoneState,
    ask,
    startRecording,
    stopRecording,
    setMode,
    setAvatar,
    cancelResponse,
    confirmTranscript,
    restoreMessages,
    resetConversation,
    markKnowledgeUpdated,
    suspendForRoute,
  };
}

function formatConfidence(value) {
  const number = Number(value);
  return Number.isNaN(number) ? "--" : `${Math.round(number * 100)}%`;
}
