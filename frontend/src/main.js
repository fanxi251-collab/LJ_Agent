import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import GuideView from "./views/GuideView.vue";
import ExploreView from "./views/ExploreView.vue";
import MapView from "./views/MapView.vue";
import "./styles.css";
import "./visitor-pages.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/visitor", redirect: "/visitor/guide" },
    { path: "/visitor/guide", component: GuideView },
    { path: "/visitor/explore", component: ExploreView },
    { path: "/visitor/map", component: MapView },
    { path: "/:pathMatch(.*)*", redirect: "/visitor/guide" },
  ],
});

createApp(App).use(router).mount("#app");
