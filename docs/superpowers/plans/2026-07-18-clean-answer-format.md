# Clean Answer Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove inline Markdown wrappers from finalized realtime answers before they are displayed or persisted.

**Architecture:** Add a shared, deterministic inline-Markdown cleaner to the existing answer formatter. Invoke it at the start of realtime answer finalization so every contract branch, final event, and persisted history receives the same clean text while supported block markers remain intact.

**Tech Stack:** Python 3, regular expressions, pytest

## Global Constraints

- Preserve `###` headings, `-` list markers, line breaks, and existing frontend parsing behavior.
- Do not add a Markdown renderer or HTML output.
- Persist only the finalized clean answer.
- Keep the implementation deterministic and independent of model prompting.

---

### Task 1: Shared inline formatting cleaner

**Files:**
- Modify: `src/lingjing_ai/rag/answer_formatter.py`
- Test: `tests/test_answer_formatter.py`

**Interfaces:**
- Produces: `clean_inline_markdown(text: str) -> str`
- Preserves: block-level `###` and `-` prefixes and all line breaks

- [ ] **Step 1: Write the failing tests**

Add tests asserting that emphasis, code, strike-through, and link wrappers are removed while headings and lists remain unchanged.

- [ ] **Step 2: Run the formatter tests and verify failure**

Run: `python -m pytest tests/test_answer_formatter.py -q`

Expected: collection or assertion failure because `clean_inline_markdown` is not implemented.

- [ ] **Step 3: Implement the minimal cleaner**

Use bounded regular expressions for Markdown links, code spans, strong emphasis, strike-through, and single emphasis. Return an empty string for empty input and preserve whitespace and block structure.

- [ ] **Step 4: Run formatter tests**

Run: `python -m pytest tests/test_answer_formatter.py -q`

Expected: all formatter tests pass.

### Task 2: Realtime finalization integration

**Files:**
- Modify: `src/lingjing_ai/realtime/answer_contract.py`
- Test: `tests/test_answer_contract.py`
- Test: `tests/test_realtime_session.py`

**Interfaces:**
- Consumes: `clean_inline_markdown(text: str) -> str`
- Produces: `FinalizedAnswer.text` without inline Markdown wrappers

- [ ] **Step 1: Write the failing contract test**

Pass `**游览建议**：请提前确认开放时间。` to `finalize_answer()` and assert the result contains `游览建议：请提前确认开放时间。` with no `**`.

- [ ] **Step 2: Run the contract test and verify failure**

Run: `python -m pytest tests/test_answer_contract.py -q`

Expected: the new assertion fails because the realtime contract currently returns model text unchanged.

- [ ] **Step 3: Clean text before contract completion**

Call `clean_inline_markdown()` before route completeness checks and source-fact supplementation. Leave deterministic route and source blocks unchanged.

- [ ] **Step 4: Run realtime tests**

Run: `python -m pytest tests/test_answer_contract.py tests/test_realtime_session.py -q`

Expected: all tests pass and the final event/persisted answer use the finalized clean text.

- [ ] **Step 5: Run regression verification**

Run: `python -m pytest -q`

Expected: the full test suite passes.

