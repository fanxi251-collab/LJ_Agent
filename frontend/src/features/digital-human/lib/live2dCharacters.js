export const AVATAR_STORAGE_KEY = "lingjing_digital_human_avatar";
export const DEFAULT_AVATAR_ID = "mao_pro";

const PROFILES = Object.freeze({
  mao_pro: Object.freeze({
    id: "mao_pro",
    label: "Mao Pro",
    roleLabel: "女导游",
    modelUrl: "/digital-human/live2d/mao_pro/mao_pro.model3.json",
    attribution: "Mao Pro sample © Live2D Inc.",
    expressionMap: Object.freeze({
      neutral: "exp_01",
      joy: "exp_02",
      apology: "exp_05",
      surprise: "exp_04",
    }),
    fit: Object.freeze({ scale: 1, yOffset: 0.04 }),
  }),
  chitose: Object.freeze({
    id: "chitose",
    label: "Chitose",
    roleLabel: "男导游",
    modelUrl: "/digital-human/live2d/chitose/chitose.model3.json",
    attribution: "Chitose sample © Live2D Inc.",
    expressionMap: Object.freeze({
      neutral: "Normal.exp3.json",
      joy: "Smile.exp3.json",
      apology: "Sad.exp3.json",
      surprise: "Surprised.exp3.json",
    }),
    fit: Object.freeze({ scale: 1, yOffset: 0.04 }),
  }),
  haruto: Object.freeze({
    id: "haruto",
    label: "Haruto",
    roleLabel: "儿童导游",
    modelUrl: "/digital-human/live2d/haruto/haruto.model3.json",
    attribution: "Haruto sample © Live2D Inc.",
    expressionMap: Object.freeze({}),
    fit: Object.freeze({ scale: 1, yOffset: 0.04 }),
  }),
});

export const AVATAR_IDS = Object.freeze(Object.keys(PROFILES));
export const AVATAR_PROFILES = Object.freeze(AVATAR_IDS.map((id) => PROFILES[id]));

export function normalizeAvatarId(avatarId) {
  const normalized = String(avatarId || "").trim();
  return Object.hasOwn(PROFILES, normalized) ? normalized : DEFAULT_AVATAR_ID;
}

export function resolveAvatarProfile(avatarId) {
  return PROFILES[normalizeAvatarId(avatarId)];
}

export function avatarExpression(avatarId, semanticExpression) {
  const profile = resolveAvatarProfile(avatarId);
  return profile.expressionMap[String(semanticExpression || "neutral")] || null;
}

export function loadAvatarPreference(storage = globalThis.localStorage) {
  try {
    return normalizeAvatarId(storage?.getItem?.(AVATAR_STORAGE_KEY));
  } catch {
    return DEFAULT_AVATAR_ID;
  }
}

export function saveAvatarPreference(storage = globalThis.localStorage, avatarId) {
  const normalized = normalizeAvatarId(avatarId);
  try {
    storage?.setItem?.(AVATAR_STORAGE_KEY, normalized);
  } catch {
    // Browser privacy modes may reject storage; the in-memory choice must remain usable.
  }
  return normalized;
}
