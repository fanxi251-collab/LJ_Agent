const elements = Object.fromEntries(
  [
    "adminState", "pendingCount", "processingCount", "resolvedCount", "feedbackSearch",
    "feedbackStatus", "feedbackCategory", "feedbackRating", "feedbackList", "feedbackForm",
    "feedbackEmpty", "feedbackFields", "feedbackTitle", "feedbackCreated", "feedbackMeta",
    "feedbackContent", "updateStatus", "adminReply",
  ].map((id) => [id, document.querySelector(`#${id}`)])
);

const categoryLabels = {
  service: "服务体验", environment: "环境卫生", facility: "设施指引",
  food: "餐饮体验", guide: "导游讲解", other: "其他",
};
const statusLabels = { pending: "待处理", processing: "处理中", resolved: "已解决" };
let feedback = [];
let selected = null;

elements.feedbackForm.addEventListener("submit", updateFeedback);
[elements.feedbackSearch, elements.feedbackStatus, elements.feedbackCategory, elements.feedbackRating]
  .forEach((element) => element.addEventListener(element === elements.feedbackSearch ? "input" : "change", loadFeedback));

async function loadFeedback() {
  elements.adminState.textContent = "加载中";
  const params = new URLSearchParams();
  if (elements.feedbackSearch.value.trim()) params.set("q", elements.feedbackSearch.value.trim());
  if (elements.feedbackStatus.value) params.set("status", elements.feedbackStatus.value);
  if (elements.feedbackCategory.value) params.set("category", elements.feedbackCategory.value);
  if (elements.feedbackRating.value) params.set("rating", elements.feedbackRating.value);
  const response = await fetch("/api/admin/feedback" + (params.size ? `?${params}` : ""));
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  feedback = data.feedback || [];
  renderSummary();
  renderList();
  if (selected) {
    const refreshed = feedback.find((item) => item.feedback_id === selected.feedback_id);
    if (refreshed) selectFeedback(refreshed);
  }
  elements.adminState.textContent = "管理端在线";
}

function renderSummary() {
  elements.pendingCount.textContent = feedback.filter((item) => item.status === "pending").length;
  elements.processingCount.textContent = feedback.filter((item) => item.status === "processing").length;
  elements.resolvedCount.textContent = feedback.filter((item) => item.status === "resolved").length;
}

function renderList() {
  elements.feedbackList.innerHTML = "";
  if (!feedback.length) return void (elements.feedbackList.textContent = "暂无符合条件的游客反馈。");
  feedback.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `feedback-admin-item${selected?.feedback_id === item.feedback_id ? " active" : ""}`;
    const heading = document.createElement("span");
    heading.innerHTML = `<strong>${escapeHtml(categoryLabels[item.category] || item.category)}</strong><em class="is-${item.status}">${escapeHtml(statusLabels[item.status] || item.status)}</em>`;
    const content = document.createElement("p");
    content.textContent = item.content;
    const meta = document.createElement("small");
    meta.textContent = `${"★".repeat(item.rating)} · ${formatDate(item.created_at)}`;
    button.append(heading, content, meta);
    button.addEventListener("click", () => selectFeedback(item));
    elements.feedbackList.appendChild(button);
  });
}

function selectFeedback(item) {
  selected = item;
  elements.feedbackEmpty.hidden = true;
  elements.feedbackFields.hidden = false;
  elements.feedbackTitle.textContent = `${categoryLabels[item.category] || item.category} · ${"★".repeat(item.rating)}`;
  elements.feedbackCreated.textContent = formatDate(item.created_at);
  elements.feedbackMeta.innerHTML = "";
  appendMeta("反馈编号", item.feedback_id);
  appendMeta("联系方式", item.contact || "未提供");
  appendMeta("匿名游客", item.visitor_id);
  elements.feedbackContent.textContent = item.content;
  elements.updateStatus.value = item.status;
  elements.adminReply.value = item.admin_reply || "";
  renderList();
}

function appendMeta(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  elements.feedbackMeta.append(term, description);
}

async function updateFeedback(event) {
  event.preventDefault();
  if (!selected) return;
  elements.adminState.textContent = "正在保存";
  const response = await fetch(`/api/admin/feedback/${selected.feedback_id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: elements.updateStatus.value, admin_reply: elements.adminReply.value.trim() }),
  });
  const data = await response.json();
  if (!response.ok) {
    elements.adminState.textContent = data.detail || "保存失败";
    return;
  }
  selected = data;
  await loadFeedback();
  elements.adminState.textContent = "处理结果已保存";
}

function formatDate(value) { return value ? new Date(value).toLocaleString("zh-CN") : "--"; }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value || ""); return node.innerHTML; }

loadFeedback().catch((error) => { elements.adminState.textContent = "加载失败"; elements.feedbackList.textContent = error.message; });
