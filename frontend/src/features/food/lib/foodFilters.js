export function filterFoods(foods, filters) {
  const keyword = String(filters.keyword || "").trim().toLowerCase();
  return foods.filter((food) => {
    const searchable = [food.name, food.summary, ...(food.taste_tags || []), ...(food.signature_dishes || [])]
      .join(" ")
      .toLowerCase();
    return (
      (!keyword || searchable.includes(keyword))
      && (!filters.scope || food.scope === filters.scope)
      && (!filters.category || food.category === filters.category)
      && (!filters.taste || (food.taste_tags || []).includes(filters.taste))
      && (!filters.priceLevel || food.price_level === Number(filters.priceLevel))
      && (!filters.vegetarianOnly || food.vegetarian_friendly)
    );
  });
}

