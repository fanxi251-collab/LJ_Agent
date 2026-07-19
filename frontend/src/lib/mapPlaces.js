export function normalizeAttractionPlace(attraction) {
  return normalizePlace("attraction", attraction.attraction_id, attraction);
}

export function normalizeFoodPlace(food) {
  return normalizePlace("food", food.food_id, food);
}

function normalizePlace(kind, sourceId, source) {
  return {
    place_id: `${kind}:${sourceId}`,
    source_id: sourceId,
    kind,
    name: source.name,
    summary: source.summary || "",
    longitude: Number(source.longitude),
    latitude: Number(source.latitude),
    source,
  };
}

