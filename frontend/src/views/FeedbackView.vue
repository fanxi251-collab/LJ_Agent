<script setup>
import { onMounted, reactive, ref } from "vue";
import { getOrCreateVisitorId } from "../lib/visitorIdentity";

const visitorId = getOrCreateVisitorId();
const categories = [
  ["service", "服务体验"], ["environment", "环境卫生"], ["facility", "设施指引"],
  ["food", "餐饮体验"], ["guide", "导游讲解"], ["other", "其他"],
];
const form = reactive({ rating: 5, category: "service", content: "", contact: "" });
const submitting = ref(false);
const submitState = ref("");
const submittedId = ref("");
const history = ref([]);
const historyState = ref("正在读取处理进度...");
let requestId = createRequestId();

function createRequestId() {
  return `feedback_${window.crypto?.randomUUID?.().replaceAll("-", "") || Date.now()}`;
}

async function loadHistory() {
  try {
    const response = await fetch(`/api/visitor/feedback?visitor_id=${encodeURIComponent(visitorId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    history.value = data.feedback || [];
    historyState.value = history.value.length ? "" : "你还没有提交过反馈。";
  } catch (error) {
    historyState.value = `处理进度加载失败：${error.message}`;
  }
}

async function submitFeedback() {
  if (submitting.value) return;
  submitting.value = true;
  submitState.value = "正在提交...";
  try {
    const response = await fetch("/api/visitor/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitor_id: visitorId,
        request_id: requestId,
        rating: form.rating,
        category: form.category,
        content: form.content.trim(),
        contact: form.contact.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail?.[0]?.msg || data.detail || `HTTP ${response.status}`);
    submittedId.value = data.feedback_id;
    submitState.value = "提交成功";
    form.content = "";
    form.contact = "";
    requestId = createRequestId();
    await loadHistory();
  } catch (error) {
    submitState.value = `提交失败：${error.message}`;
  } finally {
    submitting.value = false;
  }
}

function statusLabel(status) {
  return ({ pending: "待处理", processing: "处理中", resolved: "已解决" })[status] || status;
}

function categoryLabel(category) {
  return categories.find(([value]) => value === category)?.[1] || "其他";
}

onMounted(loadHistory);
</script>

<template>
  <main class="content-view feedback-view">
    <section class="feedback-hero">
      <div class="feedback-story">
        <p class="section-kicker">YOUR VOICE MATTERS</p>
        <h1>每一次回应，都让旅程更好</h1>
        <p>你的感受将直接进入服务处理队列。无需登录，我们只使用当前浏览器中的匿名游客标识关联进度。</p>
        <ol><li><span>01</span><div><strong>留下感受</strong><small>评分并描述真实体验</small></div></li><li><span>02</span><div><strong>服务跟进</strong><small>工作人员查看并处理</small></div></li><li><span>03</span><div><strong>回来查看</strong><small>在本页面读取处理回复</small></div></li></ol>
        <div class="privacy-note"><strong>隐私说明</strong><p>联系方式完全可选，仅在管理详情中可见；系统不记录 IP，也不会公开你的反馈。</p></div>
      </div>

      <form class="feedback-form-card" @submit.prevent="submitFeedback">
        <div><p class="section-kicker">VISITOR FEEDBACK</p><h2>这次体验，值得几颗星？</h2></div>
        <fieldset class="rating-field"><legend>总体评分</legend><div class="star-rating"><label v-for="score in 5" :key="score"><input v-model.number="form.rating" type="radio" name="rating" :value="score" /><span :class="{ active: score <= form.rating }" aria-hidden="true">★</span><em>{{ score }} 星</em></label></div></fieldset>
        <fieldset class="category-field"><legend>反馈类型</legend><div><label v-for="item in categories" :key="item[0]"><input v-model="form.category" type="radio" name="category" :value="item[0]" /><span>{{ item[1] }}</span></label></div></fieldset>
        <label class="feedback-text-field">具体内容<textarea v-model="form.content" required minlength="10" maxlength="1000" placeholder="请描述你遇到的情况或希望我们改进的地方"></textarea><small>{{ form.content.length }} / 1000</small></label>
        <label>联系方式（可选）<input v-model="form.contact" maxlength="120" placeholder="手机或邮箱，仅用于必要回访" /></label>
        <button class="feedback-submit" type="submit" :disabled="submitting || form.content.trim().length < 10">{{ submitting ? "正在提交" : "提交反馈" }}</button>
        <p class="feedback-submit-state" role="status">{{ submitState }}</p>
        <div v-if="submittedId" class="feedback-success"><span>✓</span><div><strong>已收到你的反馈</strong><p>反馈编号：{{ submittedId }} · 当前状态：待处理</p></div></div>
      </form>
    </section>

    <section class="feedback-history">
      <div class="view-section-heading"><div><p class="section-kicker">FOLLOW UP</p><h2>我的反馈进度</h2></div><button type="button" @click="loadHistory">刷新进度</button></div>
      <p v-if="historyState" class="view-notice">{{ historyState }}</p>
      <div v-else class="feedback-history-grid">
        <article v-for="item in history" :key="item.feedback_id">
          <div><span :class="`feedback-status is-${item.status}`">{{ statusLabel(item.status) }}</span><small>{{ new Date(item.created_at).toLocaleString("zh-CN") }}</small></div>
          <h3>{{ categoryLabel(item.category) }} · {{ "★".repeat(item.rating) }}</h3><p>{{ item.content }}</p>
          <blockquote v-if="item.admin_reply"><strong>服务回复</strong>{{ item.admin_reply }}</blockquote><small>编号 {{ item.feedback_id }}</small>
        </article>
      </div>
    </section>
  </main>
</template>
