const adminUploadForm = document.querySelector("#adminUploadForm");
const adminDocumentInput = document.querySelector("#adminDocumentInput");
const adminUploadButton = document.querySelector("#adminUploadButton");
const adminUploadStatus = document.querySelector("#adminUploadStatus");
const documentCount = document.querySelector("#documentCount");
const documentList = document.querySelector("#documentList");
const documentPreviewPanel = document.querySelector("#documentPreviewPanel");
const documentPreview = document.querySelector("#documentPreview");

adminUploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = adminDocumentInput.files[0];
  if (!file) {
    adminUploadStatus.textContent = "请先选择一个 .txt 或 .md 资料文件。";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  adminUploadButton.disabled = true;
  adminUploadButton.textContent = "解析中";
  try {
    const response = await fetch("/api/admin/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    adminUploadStatus.textContent = `导入成功：${data.document_name}`;
    await loadDocuments();
  } catch (error) {
    adminUploadStatus.textContent = `导入失败：${error.message}`;
  } finally {
    adminUploadButton.disabled = false;
    adminUploadButton.textContent = "上传入库";
  }
});

async function loadDocuments() {
  const response = await fetch("/api/admin/documents");
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  renderDocuments(data.documents || []);
}

function renderDocuments(documents) {
  documentCount.textContent = `${documents.length} 个`;
  documentList.innerHTML = "";
  if (documents.length === 0) {
    documentList.textContent = "暂无上传资料。";
    return;
  }
  for (const item of documents) {
    const row = createDocumentRow(item);
    documentList.appendChild(row);
  }
}

function createDocumentRow(item) {
  const row = document.createElement("article");
  row.className = "source-card";
  const title = document.createElement("div");
  title.className = "source-title";
  const name = document.createElement("span");
  name.textContent = item.document_name;
  const size = document.createElement("span");
  size.textContent = `${Math.ceil(item.file_size / 1024)} KB`;
  const meta = document.createElement("p");
  meta.className = "source-preview";
  meta.textContent = `ID：${item.document_id}；切片：${item.indexed_chunks}；更新时间：${item.updated_at}`;
  const actions = document.createElement("div");
  actions.className = "document-actions";
  actions.append(
    button("预览", () => previewDocument(item.document_id)),
    button("重新解析", () => reindexDocument(item.document_id)),
    button("删除", () => deleteDocument(item.document_id))
  );
  title.append(name, size);
  row.append(title, meta, actions);
  return row;
}

function button(text, onClick) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = text;
  element.addEventListener("click", onClick);
  return element;
}

async function previewDocument(documentId) {
  const response = await fetch(`/api/admin/documents/${documentId}/content`);
  const data = await response.json();
  if (!response.ok) {
    documentPreview.textContent = "";
    documentPreviewPanel.hidden = true;
    adminUploadStatus.textContent = data.detail || `原文预览失败：HTTP ${response.status}`;
    return;
  }
  documentPreview.textContent = data.content;
  documentPreviewPanel.hidden = false;
}

async function reindexDocument(documentId) {
  const response = await fetch(`/api/admin/documents/${documentId}/reindex`, {
    method: "POST",
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  await loadDocuments();
}

async function deleteDocument(documentId) {
  if (!confirm("确认删除这份资料及其向量片段吗？")) {
    return;
  }
  const response = await fetch(`/api/admin/documents/${documentId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  documentPreview.textContent = "";
  documentPreviewPanel.hidden = true;
  await loadDocuments();
}

loadDocuments().catch((error) => {
  documentList.textContent = error.message;
});
