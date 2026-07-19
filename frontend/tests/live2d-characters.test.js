import assert from "node:assert/strict";
import test from "node:test";

import {
  AVATAR_IDS,
  DEFAULT_AVATAR_ID,
  avatarExpression,
  loadAvatarPreference,
  resolveAvatarProfile,
  saveAvatarPreference,
} from "../src/features/digital-human/lib/live2dCharacters.js";

test("digital human registry exposes the three approved local avatars", () => {
  assert.deepEqual(AVATAR_IDS, ["mao_pro", "chitose", "haruto"]);
  assert.equal(DEFAULT_AVATAR_ID, "mao_pro");

  const male = resolveAvatarProfile("chitose");
  const child = resolveAvatarProfile("haruto");
  assert.equal(male.modelUrl, "/digital-human/live2d/chitose/chitose.model3.json");
  assert.equal(male.roleLabel, "男导游");
  assert.equal(child.modelUrl, "/digital-human/live2d/haruto/haruto.model3.json");
  assert.equal(child.roleLabel, "儿童导游");
  assert.equal(resolveAvatarProfile("unknown").id, DEFAULT_AVATAR_ID);
});

test("semantic expressions map per avatar and Haruto safely skips expressions", () => {
  assert.equal(avatarExpression("mao_pro", "joy"), "exp_02");
  assert.equal(avatarExpression("chitose", "neutral"), "Normal.exp3.json");
  assert.equal(avatarExpression("chitose", "apology"), "Sad.exp3.json");
  assert.equal(avatarExpression("chitose", "surprise"), "Surprised.exp3.json");
  assert.equal(avatarExpression("haruto", "joy"), null);
});

test("avatar preference persists only approved IDs and falls back to Mao Pro", () => {
  const values = new Map();
  const storage = {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
  };

  assert.equal(loadAvatarPreference(storage), DEFAULT_AVATAR_ID);
  assert.equal(saveAvatarPreference(storage, "chitose"), "chitose");
  assert.equal(loadAvatarPreference(storage), "chitose");
  assert.equal(saveAvatarPreference(storage, "remote-model"), DEFAULT_AVATAR_ID);
  assert.equal(loadAvatarPreference(storage), DEFAULT_AVATAR_ID);
});
