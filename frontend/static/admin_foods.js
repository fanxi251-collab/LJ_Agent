const elements = Object.fromEntries(
  [
    "adminState", "newFoodButton", "foodSearch", "statusFilter", "foodList", "foodForm",
    "formTitle", "formStatus", "foodId", "name", "scope", "category", "priceLevel",
    "summary", "description", "tasteTags", "signatureDishes", "address", "openingHours",
    "verifiedAt", "longitude", "latitude", "sourceUrl", "sortOrder", "status",
    "vegetarianFriendly", "featured", "placeSearchButton", "archiveButton", "imageInput",
    "imageIsCover", "uploadImageButton", "imageList",
  ].map((id) => [id, document.querySelector(`#${id}`)])
);

let foods = [];
let selected = null;

elements.foodForm.addEventListener("submit", saveFood);
elements.newFoodButton.addEventListener("click", resetForm);
elements.foodSearch.addEventListener("input", renderFilteredFoods);
elements.statusFilter.addEventListener("change", loadFoods);
elements.placeSearchButton.addEventListener("click", fillLocationFromAmap);
elements.archiveButton.addEventListener("click", archiveFood);
elements.uploadImageButton.addEventListener("click", uploadImage);

async function loadFoods() {
  setState("加载中");
  const params = new URLSearchParams();
  if (elements.statusFilter.value) params.set("status", elements.statusFilter.value);
  const response = await fetch("/api/admin/foods" + (params.size ? `?${params}` : ""));
  const data = await response.json();
  if (!response.ok) throw new Error(detailMessage(data, `HTTP ${response.status}`));
  foods = data.foods || [];
  renderFilteredFoods();
  setState("管理端在线");
}

function renderFilteredFoods() {
  const keyword = elements.foodSearch.value.trim().toLowerCase();
  const visible = foods.filter((item) => !keyword || `${item.name} ${item.signature_dishes.join(" ")}`.toLowerCase().includes(keyword));
  elements.foodList.innerHTML = "";
  if (!visible.length) return void (elements.foodList.textContent = "暂无符合条件的美食内容。");
  visible.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `admin-attraction-item${selected?.food_id === item.food_id ? " active" : ""}`;
    button.innerHTML = `<strong>${escapeHtml(item.name)}</strong><span>${statusLabel(item.status)} · ${item.scope === "inside" ? "景区内" : "周边"} · ${escapeHtml(item.category)}</span>`;
    button.addEventListener("click", () => selectFood(item));
    elements.foodList.appendChild(button);
  });
}

function selectFood(item) {
  selected = item;
  elements.formTitle.textContent = `编辑：${item.name}`;
  elements.formStatus.textContent = `更新于 ${formatDate(item.updated_at)}`;
  elements.foodId.value = item.food_id;
  elements.name.value = item.name;
  elements.scope.value = item.scope;
  elements.category.value = item.category;
  elements.priceLevel.value = String(item.price_level);
  elements.summary.value = item.summary;
  elements.description.value = item.description;
  elements.tasteTags.value = (item.taste_tags || []).join("，");
  elements.signatureDishes.value = (item.signature_dishes || []).join("，");
  elements.address.value = item.address;
  elements.openingHours.value = item.opening_hours;
  elements.verifiedAt.value = item.verified_at;
  elements.longitude.value = item.longitude;
  elements.latitude.value = item.latitude;
  elements.sourceUrl.value = item.source_url;
  elements.sortOrder.value = item.sort_order;
  elements.status.value = item.status;
  elements.vegetarianFriendly.checked = item.vegetarian_friendly;
  elements.featured.checked = item.is_featured;
  renderImages(item.images || []);
  renderFilteredFoods();
}

function resetForm() {
  selected = null;
  elements.foodForm.reset();
  elements.foodId.value = "";
  elements.scope.value = "inside";
  elements.priceLevel.value = "2";
  elements.status.value = "draft";
  elements.sortOrder.value = "0";
  elements.formTitle.textContent = "新建美食";
  elements.formStatus.textContent = "尚未保存";
  elements.imageList.innerHTML = "<p>保存美食后可上传图片。</p>";
  renderFilteredFoods();
}

async function saveFood(event) {
  event.preventDefault();
  const foodId = elements.foodId.value;
  const endpoint = foodId ? `/api/admin/foods/${foodId}` : "/api/admin/foods";
  const response = await fetch(endpoint, {
    method: foodId ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(formPayload()),
  });
  const data = await response.json();
  if (!response.ok) return setFormStatus(`保存失败：${detailMessage(data, response.status)}`, true);
  await loadFoods();
  selectFood(foods.find((item) => item.food_id === data.food_id) || data);
  setFormStatus(data.status === "draft" && elements.status.value === "published" ? "已保存为草稿；上传封面后可发布。" : "保存成功", false);
}

async function fillLocationFromAmap() {
  const keyword = elements.name.value.trim();
  if (!keyword) return setFormStatus("请先填写地点名称。", true);
  const response = await fetch("/api/tools/map/search?" + new URLSearchParams({ keywords: keyword, city: "无锡" }));
  const data = await response.json();
  const poi = data.data?.pois?.[0];
  if (!response.ok || !poi?.location) return setFormStatus(data.message || "未找到地点坐标。", true);
  const [longitude, latitude] = poi.location.split(",");
  elements.longitude.value = longitude;
  elements.latitude.value = latitude;
  elements.address.value = poi.address || elements.address.value;
  setFormStatus("已填入高德地点坐标。", false);
}

async function archiveFood() {
  const foodId = elements.foodId.value;
  if (!foodId || !confirm("确认归档当前美食内容吗？图片会保留。")) return;
  const response = await fetch(`/api/admin/foods/${foodId}`, { method: "DELETE" });
  const data = await response.json();
  if (!response.ok) return setFormStatus(detailMessage(data, "归档失败。"), true);
  resetForm();
  await loadFoods();
  setState("美食内容已归档");
}

async function uploadImage() {
  const foodId = elements.foodId.value;
  const file = elements.imageInput.files[0];
  if (!foodId) return setFormStatus("请先保存美食内容。", true);
  if (!file) return setFormStatus("请选择一张图片。", true);
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({ is_cover: String(elements.imageIsCover.checked), sort_order: "0" });
  const response = await fetch(`/api/admin/foods/${foodId}/images?${params}`, { method: "POST", body: formData });
  const data = await response.json();
  if (!response.ok) return setFormStatus(detailMessage(data, "图片上传失败。"), true);
  elements.imageInput.value = "";
  await refreshSelected(foodId);
  setFormStatus("图片上传成功。", false);
}

function renderImages(images) {
  elements.imageList.innerHTML = "";
  if (!images.length) return void (elements.imageList.textContent = "暂无图片。发布前请设置封面。 ");
  images.forEach((image) => {
    const card = document.createElement("article");
    card.className = "admin-image-card";
    const picture = document.createElement("img");
    picture.src = image.url;
    picture.alt = "菜品氛围图片";
    const caption = document.createElement("span");
    caption.textContent = image.is_cover ? "当前封面" : `排序 ${image.sort_order}`;
    const actions = document.createElement("div");
    actions.className = "upload-actions";
    if (!image.is_cover) actions.append(actionButton("设为封面", () => updateImage(image, true)));
    actions.append(actionButton("删除", () => deleteImage(image)));
    card.append(picture, caption, actions);
    elements.imageList.appendChild(card);
  });
}

async function updateImage(image, isCover) {
  const response = await fetch(`/api/admin/foods/${image.food_id}/images/${image.image_id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_cover: isCover, sort_order: image.sort_order }),
  });
  if (!response.ok) return setFormStatus("图片更新失败。", true);
  await refreshSelected(image.food_id);
}

async function deleteImage(image) {
  if (!confirm("确认只删除这张图片吗？")) return;
  const response = await fetch(`/api/admin/foods/${image.food_id}/images/${image.image_id}`, { method: "DELETE" });
  if (!response.ok) return setFormStatus("图片删除失败。", true);
  await refreshSelected(image.food_id);
}

async function refreshSelected(foodId) {
  const response = await fetch(`/api/admin/foods/${foodId}`);
  const data = await response.json();
  if (response.ok) {
    await loadFoods();
    selectFood(data);
  }
}

function formPayload() {
  return {
    name: elements.name.value.trim(),
    summary: elements.summary.value.trim(),
    description: elements.description.value.trim(),
    scope: elements.scope.value,
    category: elements.category.value.trim(),
    taste_tags: splitList(elements.tasteTags.value),
    signature_dishes: splitList(elements.signatureDishes.value),
    price_level: Number(elements.priceLevel.value),
    vegetarian_friendly: elements.vegetarianFriendly.checked,
    address: elements.address.value.trim(),
    opening_hours: elements.openingHours.value.trim(),
    longitude: Number(elements.longitude.value),
    latitude: Number(elements.latitude.value),
    source_url: elements.sourceUrl.value.trim(),
    verified_at: elements.verifiedAt.value,
    is_featured: elements.featured.checked,
    sort_order: Number(elements.sortOrder.value || 0),
    status: elements.status.value,
  };
}

function splitList(value) { return value.split(/[，,]/).map((item) => item.trim()).filter(Boolean); }
function actionButton(label, handler) { const button = document.createElement("button"); button.type = "button"; button.textContent = label; button.addEventListener("click", handler); return button; }
function setState(message) { elements.adminState.textContent = message; }
function setFormStatus(message, isError) { elements.formStatus.textContent = message; elements.formStatus.classList.toggle("error-text", Boolean(isError)); }
function statusLabel(status) { return ({ draft: "草稿", published: "已发布", archived: "已归档" })[status] || status; }
function formatDate(value) { return value ? new Date(value).toLocaleString("zh-CN") : "--"; }
function detailMessage(data, fallback) { return Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join("；") : data.detail || fallback; }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value || ""); return node.innerHTML; }

resetForm();
loadFoods().catch((error) => { setState("加载失败"); elements.foodList.textContent = error.message; });
