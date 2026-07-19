export const GUIDE_INTRO_SESSION_KEY = "lingjing.guide.intro.seen.v1";

function queryValues(value) {
  return Array.isArray(value) ? value : [value];
}

function hasNonEmptyQueryValue(value) {
  return queryValues(value).some((item) => String(item ?? "").trim().length > 0);
}

export function resolveGuideIntroVisibility({ path, query = {}, sessionSeen = false }) {
  if (path !== "/visitor/guide") return false;

  // Explicit questions bypass the cinematic layer so cross-page guide actions remain immediate.
  if (hasNonEmptyQueryValue(query.q)) return false;

  const forceReplay = queryValues(query.intro).some((item) => String(item ?? "") === "1");
  return forceReplay || !sessionSeen;
}

export function withoutIntroQuery(query = {}) {
  // Copy before deletion so Vue Router's readonly query object is never mutated.
  const nextQuery = { ...query };
  delete nextQuery.intro;
  return nextQuery;
}
