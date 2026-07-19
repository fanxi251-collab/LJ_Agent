export const EXPRESSION_DEBOUNCE_MS = 300;
export const NEUTRAL_EXPRESSION = "neutral";

const KEYWORDS = {
  apology: ["抱歉", "无法", "失败", "关闭", "暂停", "不便", "遗憾", "暂不可用"],
  surprise: ["壮观", "惊喜", "罕见", "最大", "最高", "首次", "特别"],
  joy: ["欢迎", "推荐", "值得", "适合", "愉快", "祝您", "精彩", "很美"],
};

function containsAny(text, keywords) {
  return keywords.some((keyword) => text.includes(keyword));
}

export function resolveLive2DExpression({ state = "idle", assistantText = "" } = {}) {
  if (state === "error") return "apology";
  if (state !== "speaking") return NEUTRAL_EXPRESSION;

  const text = String(assistantText || "");
  if (containsAny(text, KEYWORDS.apology)) return "apology";
  if (containsAny(text, KEYWORDS.surprise)) return "surprise";
  if (containsAny(text, KEYWORDS.joy)) return "joy";
  return NEUTRAL_EXPRESSION;
}

export function createExpressionDebouncer(
  onCommit,
  {
    schedule = (callback, delay) => setTimeout(callback, delay),
    cancel = (handle) => clearTimeout(handle),
  } = {},
) {
  let handle = null;
  let committed = NEUTRAL_EXPRESSION;
  let pending = committed;

  function clearPending() {
    if (handle === null) return;
    cancel(handle);
    handle = null;
  }

  function update(expression) {
    const next = expression || NEUTRAL_EXPRESSION;
    if (next === committed || next === pending) return;
    clearPending();
    pending = next;
    handle = schedule(() => {
      handle = null;
      committed = pending;
      onCommit(committed);
    }, EXPRESSION_DEBOUNCE_MS);
  }

  function reset() {
    clearPending();
    pending = NEUTRAL_EXPRESSION;
    committed = NEUTRAL_EXPRESSION;
    onCommit(NEUTRAL_EXPRESSION);
  }

  return {
    update,
    reset,
    dispose: clearPending,
  };
}
