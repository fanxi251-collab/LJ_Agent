import { readonly, ref, watch } from "vue";
import {
  GUIDE_INTRO_SESSION_KEY,
  resolveGuideIntroVisibility,
  withoutIntroQuery,
} from "../lib/introPolicy.js";

export function useGuideIntro(route, router) {
  const visible = ref(false);
  let memorySeen = false;

  function readSessionSeen() {
    try {
      return window.sessionStorage.getItem(GUIDE_INTRO_SESSION_KEY) === "1";
    } catch {
      // In-memory fallback keeps navigation usable when privacy settings block sessionStorage.
      return memorySeen;
    }
  }

  function markSessionSeen() {
    memorySeen = true;
    try {
      window.sessionStorage.setItem(GUIDE_INTRO_SESSION_KEY, "1");
    } catch {
      // The current SPA session still remembers completion through memorySeen.
    }
  }

  function syncVisibility() {
    visible.value = resolveGuideIntroVisibility({
      path: route.path,
      query: route.query,
      sessionSeen: readSessionSeen(),
    });
  }

  async function completeIntro() {
    markSessionSeen();
    visible.value = false;

    if (Object.prototype.hasOwnProperty.call(route.query, "intro")) {
      await router.replace({ path: route.path, query: withoutIntroQuery(route.query) });
    }
  }

  watch(
    () => [route.path, route.query.q, route.query.intro],
    syncVisibility,
    { immediate: true },
  );

  return { visible: readonly(visible), completeIntro };
}
