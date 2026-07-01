const DEFAULT_TIMEOUT_MS = 45000;

function createApiError(message, extra = {}) {
  const error = new Error(message);
  error.code = extra.code || null;
  error.details = extra.details || null;
  error.status = extra.status || null;
  return error;
}

async function fetchApi(endpoint, options = {}, config = {}) {
  const normalized = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = normalized;
  const timeoutMs = Number.isFinite(Number(config?.timeoutMs))
    ? Number(config.timeoutMs)
    : DEFAULT_TIMEOUT_MS;

  let controller = null;
  let timerId = null;
  const mergedOptions = { ...options };
  if (!mergedOptions.signal) {
    controller = new AbortController();
    mergedOptions.signal = controller.signal;
    timerId = window.setTimeout(() => controller.abort(), timeoutMs);
  }

  let response;
  try {
    response = await fetch(url, {
      ...mergedOptions,
      headers: {
        "Content-Type": "application/json",
        ...(mergedOptions.headers || {}),
      },
    });
  } catch (error) {
    if (timerId) window.clearTimeout(timerId);
    if (error && String(error.name || "") === "AbortError") {
      throw new Error("请求超时：后端不可达或响应过慢（/api）");
    }
    throw new Error(`请求失败：后端不可达（/api）`);
  } finally {
    if (timerId) window.clearTimeout(timerId);
  }

  const contentType = response.headers.get("Content-Type") || "";
  const isJson = contentType.toLowerCase().includes("application/json");

  let payload = null;
  if (isJson) {
    payload = await response.json().catch(() => null);
  }

  if (!response.ok) {
    const errorPayload =
      payload && typeof payload.error === "object" && payload.error ? payload.error : null;
    const message =
      (payload && typeof payload.message === "string" && payload.message) ||
      (errorPayload &&
        typeof errorPayload.message === "string" &&
        errorPayload.message) ||
      (payload && typeof payload.error === "string" && payload.error) ||
      `HTTP ${response.status}`;
    throw createApiError(message, {
      code: errorPayload && typeof errorPayload.code === "string" ? errorPayload.code : null,
      details: errorPayload && typeof errorPayload.details === "object" ? errorPayload.details : null,
      status: response.status,
    });
  }

  return isJson ? payload : response.text();
}

export { fetchApi };

export const checkHealth = () => fetchApi("/healthz");
export const getApiDocs = () => fetchApi("/api");
export const getDataStatus = () => fetchApi("/api/data/status");
export const getTradingDay = (date) => fetchApi(`/api/trading-day?date=${date}`);

export const getTradingCalendar = (date) =>
  fetchApi(`/api/trading-calendar/meta?date=${date}`);

export const getBootstrapSummary = (date) =>
  fetchApi(`/api/bootstrap-summary?date=${date}`);

export const getDataControl = (date) =>
  fetchApi(`/api/data-control?date=${date}`);

export const getOrchestration = (date) =>
  fetchApi(`/api/orchestration?date=${date}`);

export const getIssueCenter = (date) =>
  fetchApi(`/api/issue-center?date=${date}`);

export const getLearning = (date) =>
  fetchApi(`/api/learning?date=${date}`);

export const getLabs = (date) =>
  fetchApi(`/api/labs?date=${date}`);

export const getScreeners = (date) =>
  fetchApi(`/api/screeners?date=${date}`);

export const getScreenerRuns = (date) =>
  fetchApi(`/api/screeners/runs?date=${date}`);

export const runScreener = (screenerId, date, apiKey) =>
  fetchApi("/api/screeners/run", {
    method: "POST",
    headers: apiKey ? { "X-API-Key": apiKey } : {},
    body: JSON.stringify({ screener_id: screenerId, date }),
  });

export const runAllScreeners = (date, apiKey) =>
  fetchApi("/api/screeners/bulk-run", {
    method: "POST",
    headers: apiKey ? { "X-API-Key": apiKey } : {},
    body: JSON.stringify({ date }),
  });

export const getStocksCoverage = (date) =>
  fetchApi(`/api/stocks/coverage?date=${date}`);

export const lookupStock = (code, date) =>
  fetchApi(`/api/stocks/lookup?code=${code}&date=${date}`);

export const getHotSectors = () => fetchApi("/api/v1/sectors/hot");

export const getMarketPhase = (date) =>
  fetchApi(`/api/market-phase?date=${date}`);

export const getSectorRotation = (date) =>
  fetchApi(`/api/sector-rotation?date=${date}`);

export const getStockTiering = (date) =>
  fetchApi(`/api/stock-tiering?date=${date}`);

export const getResonanceScore = (codes, date) =>
  fetchApi(`/api/resonance-score?codes=${codes}&date=${date}`);

export const getSignals = (codes, date) =>
  fetchApi(`/api/signals?codes=${codes}&date=${date}`);

export const getFactorMatrix = (date) =>
  fetchApi(`/api/factor-matrix/daily?date=${date}`);

export const runFactorMatrix = (date, apiKey) =>
  fetchApi("/api/factor-matrix/daily/run", {
    method: "POST",
    headers: apiKey ? { "X-API-Key": apiKey } : {},
    body: JSON.stringify({ date }),
  });

export const getMarketIntelligenceReviewBoard = (date, topN = 10) =>
  fetchApi(
    `/api/market-intelligence/review-board?trade_date=${encodeURIComponent(
      date
    )}&top_n=${encodeURIComponent(topN)}`,
    {},
    { timeoutMs: 60000 }
  );

export const getMarketIntelligenceDecisionSummary = (date, topN = 10) =>
  fetchApi(
    `/api/market-intelligence/decision-summary?trade_date=${encodeURIComponent(
      date
    )}&top_n=${encodeURIComponent(topN)}`,
    {},
    { timeoutMs: 60000 }
  );
