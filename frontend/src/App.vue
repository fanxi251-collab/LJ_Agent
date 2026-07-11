<script setup>
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="visitor-app-shell">
    <aside class="visitor-sidebar">
      <RouterLink class="visitor-brand" to="/visitor/guide">
        <span class="visitor-brand-mark">灵</span>
        <span class="visitor-brand-copy">
          <strong>LingJing AI</strong>
          <small>灵山胜境智慧游览</small>
        </span>
      </RouterLink>
      <nav class="visitor-sidebar-nav" aria-label="游客端导航">
        <RouterLink class="visitor-sidebar-link" to="/visitor/guide" aria-label="AI 智能导游">
          <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 5h16v12H8l-4 3V5Z" />
            <path d="M8 9h8M8 13h5" />
          </svg>
          <span>AI 智能导游</span>
        </RouterLink>
        <RouterLink class="visitor-sidebar-link" to="/visitor/explore" aria-label="景点探索">
          <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="17" cy="6" r="2" />
            <path d="m3 19 6-10 4 6 2-3 6 7H3Z" />
          </svg>
          <span>景点探索</span>
        </RouterLink>
        <RouterLink class="visitor-sidebar-link" to="/visitor/map" aria-label="互动地图">
          <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" />
            <path d="M9 3v15M15 6v15" />
          </svg>
          <span>互动地图</span>
        </RouterLink>
      </nav>
    </aside>
    <section class="visitor-content-shell">
      <RouterView />
    </section>
  </div>
</template>
