const VISITOR_STORAGE_KEY = "lingjing_visitor_id";

export function getOrCreateVisitorId(
  storage = window.localStorage,
  cryptoLike = window.crypto,
) {
  const existing = storage.getItem(VISITOR_STORAGE_KEY);
  if (existing) return existing;
  const randomPart = cryptoLike?.randomUUID
    ? cryptoLike.randomUUID().replaceAll("-", "")
    : `${Date.now()}${Math.random().toString(16).slice(2)}`;
  const visitorId = `visitor_${randomPart}`;
  storage.setItem(VISITOR_STORAGE_KEY, visitorId);
  return visitorId;
}

