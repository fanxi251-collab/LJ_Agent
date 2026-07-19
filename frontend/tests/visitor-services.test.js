import test from "node:test";
import assert from "node:assert/strict";

import { filterFoods } from "../src/features/food/lib/foodFilters.js";
import { normalizeAttractionPlace, normalizeFoodPlace } from "../src/lib/mapPlaces.js";
import { getOrCreateVisitorId } from "../src/lib/visitorIdentity.js";


test("visitor identity reuses storage and creates one stable anonymous id", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
  };
  const cryptoLike = { randomUUID: () => "12345678-1234-1234-1234-123456789abc" };

  const first = getOrCreateVisitorId(storage, cryptoLike);
  const second = getOrCreateVisitorId(storage, { randomUUID: () => "different" });

  assert.equal(first, "visitor_12345678123412341234123456789abc");
  assert.equal(second, first);
});


test("food filters combine scope category taste price and vegetarian preference", () => {
  const foods = [
    {
      name: "灵山蔬食馆",
      summary: "江南素食",
      scope: "inside",
      category: "素食",
      taste_tags: ["清淡", "江南"],
      signature_dishes: ["灵山素面"],
      price_level: 2,
      vegetarian_friendly: true,
    },
    {
      name: "太湖渔村",
      summary: "湖鲜",
      scope: "nearby",
      category: "正餐",
      taste_tags: ["鲜美"],
      signature_dishes: ["太湖白鱼"],
      price_level: 3,
      vegetarian_friendly: false,
    },
  ];

  const visible = filterFoods(foods, {
    keyword: "素面",
    scope: "inside",
    category: "素食",
    taste: "清淡",
    priceLevel: "2",
    vegetarianOnly: true,
  });

  assert.deepEqual(visible.map((item) => item.name), ["灵山蔬食馆"]);
});


test("map places preserve source identity and use distinct attraction and food kinds", () => {
  const attraction = normalizeAttractionPlace({
    attraction_id: "attr_1",
    name: "灵山大佛",
    summary: "核心景观",
    longitude: 120.09,
    latitude: 31.43,
  });
  const food = normalizeFoodPlace({
    food_id: "food_1",
    name: "灵山蔬食馆",
    summary: "景区餐饮",
    longitude: 120.1,
    latitude: 31.42,
  });

  assert.equal(attraction.place_id, "attraction:attr_1");
  assert.equal(attraction.kind, "attraction");
  assert.equal(food.place_id, "food:food_1");
  assert.equal(food.kind, "food");
});
