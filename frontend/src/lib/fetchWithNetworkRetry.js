function waitFor(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function fetchWithNetworkRetry(input, options = {}) {
  const {
    fetchImpl = globalThis.fetch,
    retries = 1,
    wait = waitFor,
    delayMs = 400,
    ...fetchOptions
  } = options;
  let attempt = 0;
  while (true) {
    try {
      return await fetchImpl(input, fetchOptions);
    } catch (error) {
      if (attempt >= retries) throw error;
      attempt += 1;
      // 只重试没有收到 HTTP 响应的短暂断线，避免服务刚重载时立即展示失败状态。
      await wait(delayMs * attempt);
    }
  }
}
