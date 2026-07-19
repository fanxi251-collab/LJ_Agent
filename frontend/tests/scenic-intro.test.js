import test from "node:test";
import assert from "node:assert/strict";

import {
  GUIDE_INTRO_SESSION_KEY,
  resolveGuideIntroVisibility,
  withoutIntroQuery,
} from "../src/features/scenic-intro/lib/introPolicy.js";


test("shows the scenic intro only on an unseen plain guide entry", () => {
  assert.equal(GUIDE_INTRO_SESSION_KEY, "lingjing.guide.intro.seen.v1");
  assert.equal(resolveGuideIntroVisibility({ path: "/visitor/guide", query: {}, sessionSeen: false }), true);
  assert.equal(resolveGuideIntroVisibility({ path: "/visitor/guide", query: {}, sessionSeen: true }), false);
  assert.equal(resolveGuideIntroVisibility({ path: "/visitor/explore", query: {}, sessionSeen: false }), false);
});


test("force replay overrides the session marker on a plain guide entry", () => {
  assert.equal(
    resolveGuideIntroVisibility({ path: "/visitor/guide", query: { intro: "1" }, sessionSeen: true }),
    true,
  );
});


test("an explicit guide question bypasses the intro even when replay is forced", () => {
  assert.equal(
    resolveGuideIntroVisibility({
      path: "/visitor/guide",
      query: { intro: "1", q: "请介绍灵山大佛" },
      sessionSeen: false,
    }),
    false,
  );
  assert.equal(
    resolveGuideIntroVisibility({ path: "/visitor/guide", query: { q: "   " }, sessionSeen: false }),
    true,
  );
});


test("removing the replay query preserves unrelated query values", () => {
  assert.deepEqual(
    withoutIntroQuery({ intro: "1", source: "defense", tags: ["lake", "temple"] }),
    { source: "defense", tags: ["lake", "temple"] },
  );
});
