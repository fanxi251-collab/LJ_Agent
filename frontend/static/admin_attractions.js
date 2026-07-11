const elements = Object.fromEntries(
  [
    "adminState", "newAttractionButton", "attractionSearch", "statusFilter", "attractionList",
    "attractionForm", "formTitle", "formStatus", "attractionId", "name", "category", "summary",
    "description", "tags", "address", "openingHours", "duration", "longitude", "latitude",
    "sortOrder", "status", "featured", "placeSearchButton", "archiveButton", "imageInput",
    "imageIsCover", "uploadImageButton", "imageList",
  ].map((id) => [id, document.querySelector(`#${id}`)])
);

let attractions = [];
let selected = null;

elements.attractionForm.addEventListener("submit", saveAttraction);
elements.newAttractionButton.addEventListener("click", resetForm);
elements.attractionSearch.addEventListener("input", renderFilteredAttractions);
elements.statusFilter.addEventListener("change", loadAttractions);
elements.placeSearchButton.addEventListener("click", fillLocationFromAmap);
elements.archiveButton.addEventListener("click", archiveAttraction);
elements.uploadImageButton.addEventListener("click", uploadImage);

async function loadAttractions() {
  setState("加载中");
  const params = new URLSearchParams();
  if (elements.statusFilter.value) params.set("status", elements.statusFilter.value);
  const response = await fetch("/api/admin/attractions" + (params.size ? `?${params}` : ""));
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  attractions = data.attractions || [];
  renderFilteredAttractions();
  setState("管理端在线");
}

function renderFilteredAttractions() {
  const keyword = elements.attractionSearch.value.trim().toLowerCase();
  const visible = attractions.filter((item) => !keyword || item.name.toLowerCase().includes(keyword));
  elements.attractionList.innerHTML = "";
  if (!visible.length) {
    elements.attractionList.textContent = "暂无符合条件的景点。";
    return;
  }
  visible.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `admin-attraction-item${selected?.attraction_id === item.attraction_id ? " active" : ""}`;
    button.innerHTML = `<strong>${escapeHtml(item.name)}</strong><span>${statusLabel(item.status)} · ${escapeHtml(item.category || "未分类")}</span>`;
    button.addEventListener("click", () => selectAttraction(item));
    elements.attractionList.appendChild(button);
  });
}

function selectAttraction(item) {
  selected = item;
  elements.formTitle.textContent = `编辑：${item.name}`;
  elements.formStatus.textContent = `更新于 ${formatDate(item.updated_at)}`;
  elements.attractionId.value = item.attraction_id;
  elements.name.value = item.name;
  elements.category.value = item.category;
  elements.summary.value = item.summary;
  elements.description.value = item.description;
  elements.tags.value = (item.tags || []).join("，");
  elements.address.value = item.address;
  elements.openingHours.value = item.opening_hours;
  elements.duration.value = item.suggested_duration_minutes;
  elements.longitude.value = item.longitude;
  elements.latitude.value = item.latitude;
  elements.sortOrder.value = item.sort_order;
  elements.status.value = item.status;
  elements.featured.checked = item.is_featured;
  renderImages(item.images || []);
  renderFilteredAttractions();
}

function resetForm() {
  selected = null;
  elements.attractionForm.reset();
  elements.attractionId.value = "";
  elements.duration.value = "45";
  elements.sortOrder.value = "0";
  elements.formTitle.textContent = "新建景点";
  elements.formStatus.textContent = "尚未保存";
  elements.imageList.innerHTML = "<p>保存景点后可上传图片。</p>";
  renderFilteredAttractions();
}

async function saveAttraction(event) {
  event.preventDefault();
  const attractionId = elements.attractionId.value;
  const endpoint = attractionId ? `/api/admin/attractions/${attractionId}` : "/api/admin/attractions";
  const response = await fetch(endpoint, {
    method: attractionId ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(formPayload()),
  });
  const data = await response.json();
  if (!response.ok) {
    elements.formStatus.textContent = `保存失败：${data.detail || response.status}`;
    return;
  }
  elements.formStatus.textContent = "保存成功";
  await loadAttractions();
  selectAttraction(attractions.find((item) => item.attraction_id === data.attraction_id) || data);
}

async function fillLocationFromAmap() {
  const keyword = elements.name.value.trim();
  if (!keyword) return setFormStatus("请先填写景点名称。", true);
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

async function archiveAttraction() {
  const attractionId = elements.attractionId.value;
  if (!attractionId || !confirm("确认归档当前景点吗？图片会保留。")) return;
  const response = await fetch(`/api/admin/attractions/${attractionId}`, { method: "DELETE" });
  const data = await response.json();
  if (!response.ok) return setFormStatus(data.detail || "归档失败。", true);
  resetForm();
  await loadAttractions();
  setState("景点已归档");
}

async function uploadImage() {
  const attractionId = elements.attractionId.value;
  const file = elements.imageInput.files[0];
  if (!attractionId) return setFormStatus("请先保存景点。", true);
  if (!file) return setFormStatus("请选择一张图片。", true);
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({ is_cover: String(elements.imageIsCover.checked), sort_order: "0" });
  const response = await fetch(`/api/admin/attractions/${attractionId}/images?${params}`, {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) return setFormStatus(data.detail || "图片上传失败。", true);
  elements.imageInput.value = "";
  await refreshSelected(attractionId);
  setFormStatus("图片上传成功。", false);
}

function renderImages(images) {
  elements.imageList.innerHTML = "";
  if (!images.length) return void (elements.imageList.textContent = "暂无图片。发布前请设置封面。 ");
  images.forEach((image) => {
    const card = document.createElement("article");
    card.className = "admin-image-card";
    card.innerHTML = `<img src="${image.url}" alt="景点图片" /><span>${image.is_cover ? "当前封面" : `排序 ${image.sort_order}`}</span>`;
    const actions = document.createElement("div");
    actions.className = "upload-actions";
    if (!image.is_cover) actions.append(actionButton("设为封面", () => updateImage(image, true)));
    actions.append(actionButton("删除", () => deleteImage(image)));
    card.appendChild(actions);
    elements.imageList.appendChild(card);
  });
}

async function updateImage(image, isCover) {
  await fetch(`/api/admin/attractions/${image.attraction_id}/images/${image.image_id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_cover: isCover, sort_order: image.sort_order }),
  });
  await refreshSelected(image.attraction_id);
}

async function deleteImage(image) {
  if (!confirm("确认只删除这张图片吗？")) return;
  const response = await fetch(`/api/admin/attractions/${image.attraction_id}/images/${image.image_id}`, { method: "DELETE" });
  if (!response.ok) return setFormStatus("图片删除失败。", true);
  await refreshSelected(image.attraction_id);
}

async function refreshSelected(attractionId) {
  const response = await fetch(`/api/admin/attractions/${attractionId}`);
  const data = await response.json();
  if (response.ok) {
    await loadAttractions();
    selectAttraction(data);
  }
}

function formPayload() {
  return {
    name: elements.name.value.trim(), summary: elements.summary.value.trim(),
    description: elements.description.value.trim(), category: elements.category.value.trim(),
    tags: elements.tags.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean),
    address: elements.address.value.trim(), opening_hours: elements.openingHours.value.trim(),
    suggested_duration_minutes: Number(elements.duration.value || 0),
    longitude: Number(elements.longitude.value), latitude: Number(elements.latitude.value),
    is_featured: elements.featured.checked, sort_order: Number(elements.sortOrder.value || 0),
    status: elements.status.value,
  };
}

function actionButton(label, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function setState(message) { elements.adminState.textContent = message; }
function setFormStatus(message, isError) {
  elements.formStatus.textContent = message;
  elements.formStatus.classList.toggle("error-text", Boolean(isError));
}
function statusLabel(status) { return ({ draft: "草稿", published: "已发布", archived: "已归档" })[status] || status; }
function formatDate(value) { return value ? new Date(value).toLocaleString("zh-CN") : "--"; }
function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value || "");
  return node.innerHTML;
}

resetForm();
loadAttractions().catch((error) => {
  setState("加载失败");
  elements.attractionList.textContent = error.message;
});
