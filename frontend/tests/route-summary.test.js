import test from "node:test";
import assert from "node:assert/strict";

import { findSuccessfulRouteSource, resolveRouteSummary } from "../src/lib/routeSummary.js";


test("resolves V2 route_summary and legacy metadata", () => {
  const v2 = { schema_version: 2, origin: "无锡站", steps: [{ instruction: "出发" }] };
  const v2Source = { metadata: { source_type: "amap_route", route_summary: v2 } };
  const legacy = {
    metadata: {
      source_type: "amap_route",
      origin: "旧起点",
      polyline: ["120.1,31.5", "120.2,31.6"],
      steps: [{ instruction: "旧路线" }],
    },
  };

  assert.equal(resolveRouteSummary(v2Source), v2);
  assert.equal(resolveRouteSummary(legacy), legacy.metadata);
});


test("finds only a successful route source with drawable route data", () => {
  const failed = { metadata: { source_type: "amap_route", route_error: "超时" } };
  const success = {
    metadata: {
      source_type: "amap_route",
      route_summary: { schema_version: 2, polyline: ["120.1,31.5", "120.2,31.6"] },
    },
  };

  assert.equal(findSuccessfulRouteSource([failed]), null);
  assert.equal(findSuccessfulRouteSource([failed, success]), success);
});
