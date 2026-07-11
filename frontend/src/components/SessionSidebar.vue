<script setup>
defineProps({
  sessions: { type: Array, required: true },
  currentSessionId: { type: String, required: true },
  status: { type: String, required: true },
});

defineEmits(["new-session", "load-session", "delete-current-session"]);
</script>

<template>
  <section class="session-sidebar">
    <div class="session-brand">
      <span class="brand-dot">灵</span>
      <strong>历史会话</strong>
    </div>

    <button class="new-session-button" type="button" @click="$emit('new-session')">
      + 开启新对话
    </button>

    <div class="session-status">{{ status }}</div>

    <div id="sessionList" class="session-list">
      <button
        v-if="!sessions.length"
        class="session-item active"
        type="button"
        @click="$emit('new-session')"
      >
        当前新会话
      </button>
      <template v-else>
        <button
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === currentSessionId }"
          type="button"
          :title="session.title"
          @click="$emit('load-session', session.session_id)"
        >
          {{ session.title || "历史会话" }}
        </button>
      </template>
    </div>

    <button class="delete-session-button" type="button" @click="$emit('delete-current-session')">
      删除当前会话
    </button>
  </section>
</template>
