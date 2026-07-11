# Visitor Sidebar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the visitor top navigation with a shared fixed left sidebar across the guide, explore, and map routes.

**Architecture:** Keep navigation in the root Vue `App.vue` so every visitor route shares one source of truth. Use a two-column CSS shell on desktop and a compact icon rail below 760px; the existing routed views remain independent and the AI history sidebar stays inside the guide view.

**Tech Stack:** Vue 3, Vue Router 4, CSS, pytest static frontend regression tests, Vite.

## Global Constraints

- Keep AI guide, attraction explore, and interactive map behavior unchanged.
- Use inline SVG icons; add no icon dependency.
- Keep code files below 800 lines where practical.
- Comments must state both what the code does and why it is needed.

---

### Task 1: Shared visitor sidebar shell

**Files:**
- Modify: `tests/test_frontend.py`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/visitor-pages.css`

**Interfaces:**
- Consumes: Vue Router routes `/visitor/guide`, `/visitor/explore`, `/visitor/map`.
- Produces: `.visitor-sidebar`, `.visitor-sidebar-link`, and `.visitor-content-shell` layout contracts.

- [ ] **Step 1: Write the failing regression test**

```python
def test_visitor_root_uses_shared_left_sidebar_navigation():
    app_source = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    page_styles = Path("frontend/src/visitor-pages.css").read_text(encoding="utf-8")
    assert "visitor-sidebar" in app_source
    assert "visitor-content-shell" in app_source
    assert "visitor-global-header" not in app_source
    assert app_source.count("visitor-sidebar-icon") == 3
    assert "grid-template-columns: 232px minmax(0, 1fr)" in page_styles
    assert "overflow-y: auto" in page_styles
    assert "@media (max-width: 760px)" in page_styles
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest -q tests/test_frontend.py::test_visitor_root_uses_shared_left_sidebar_navigation`

Expected: FAIL because `App.vue` still contains `visitor-global-header` and no sidebar.

- [ ] **Step 3: Implement the root sidebar**

Replace the root template with this structure and provide one distinct inline SVG per route:

```vue
<div class="visitor-app-shell">
  <aside class="visitor-sidebar">
    <RouterLink class="visitor-brand" to="/visitor/guide">
      <span class="visitor-brand-mark">灵</span>
      <span class="visitor-brand-copy"><strong>LingJing AI</strong><small>灵山胜境智慧游览</small></span>
    </RouterLink>
    <nav class="visitor-sidebar-nav" aria-label="游客端导航">
      <RouterLink class="visitor-sidebar-link" to="/visitor/guide" aria-label="AI 智能导游">
        <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v12H8l-4 3V5Z" /></svg>
        <span>AI 智能导游</span>
      </RouterLink>
      <RouterLink class="visitor-sidebar-link" to="/visitor/explore" aria-label="景点探索">
        <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 19 6-10 4 6 2-3 6 7H3Z" /></svg>
        <span>景点探索</span>
      </RouterLink>
      <RouterLink class="visitor-sidebar-link" to="/visitor/map" aria-label="互动地图">
        <svg class="visitor-sidebar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" /></svg>
        <span>互动地图</span>
      </RouterLink>
    </nav>
  </aside>
  <section class="visitor-content-shell"><RouterView /></section>
</div>
```

CSS requirements:

```css
.visitor-app-shell { height: 100vh; display: grid; grid-template-columns: 232px minmax(0, 1fr); overflow: hidden; }
.visitor-sidebar { height: 100vh; display: grid; grid-template-rows: auto 1fr; }
.visitor-content-shell { min-width: 0; height: 100vh; overflow-y: auto; }
.visitor-sidebar-link.router-link-active::before { content: ""; position: absolute; left: 0; }
@media (max-width: 760px) { .visitor-app-shell { grid-template-columns: 76px minmax(0, 1fr); } }
```

- [ ] **Step 4: Run focused tests and production build**

Run: `python -m pytest -q tests/test_frontend.py`

Expected: all frontend tests pass.

Run: `cd frontend && npm run build`

Expected: Vite exits with code 0.

- [ ] **Step 5: Run full regression**

Run: `python -m pytest -q`

Expected: all tests pass with zero failures.

- [ ] **Step 6: Commit the sidebar implementation**

```powershell
git add frontend/src/App.vue frontend/src/visitor-pages.css tests/test_frontend.py
git commit -m "feat: add shared visitor sidebar navigation"
```
