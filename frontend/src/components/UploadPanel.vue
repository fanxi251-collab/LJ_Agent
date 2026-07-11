<script setup>
import { ref } from "vue";

const emit = defineEmits(["uploaded"]);
const fileInput = ref(null);
const status = ref("支持 UTF-8 编码的 .txt / .md 单文件。");
const isUploading = ref(false);
const successMessage = ref("");

async function uploadDocument() {
  const file = fileInput.value?.files?.[0];
  if (!file) {
    status.value = "请先选择一个 .txt 或 .md 资料文件。";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  isUploading.value = true;
  successMessage.value = "";
  status.value = "正在上传并解析资料...";

  try {
    const response = await fetch("/api/rag/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    status.value = `导入成功：${data.document_name}，新增 ${data.indexed_chunks} 个知识片段。`;
    successMessage.value = `资料上传成功，已自动解析入库，可立即提问。文件：${data.document_name}`;
    emit("uploaded");
  } catch (error) {
    status.value = `导入失败：${error.message}`;
  } finally {
    isUploading.value = false;
  }
}
</script>

<template>
  <form class="upload-panel" @submit.prevent="uploadDocument">
    <div>
      <p class="section-kicker">知识库资料</p>
      <h2>上传资料并自动解析</h2>
      <p class="upload-status">{{ status }}</p>
    </div>
    <div class="upload-actions">
      <label class="file-picker" for="documentInput">选择资料</label>
      <input id="documentInput" ref="fileInput" name="file" type="file" accept=".txt,.md" />
      <button type="submit" :disabled="isUploading">
        {{ isUploading ? "解析中" : "上传入库" }}
      </button>
    </div>
    <p v-if="successMessage" class="success-notice">{{ successMessage }}</p>
  </form>
</template>
