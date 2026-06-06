async function fetchApi(endpoint, options = {}) {
  const normalized = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = normalized;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const contentType = response.headers.get("Content-Type") || "";
  const isJson = contentType.toLowerCase().includes("application/json");

  if (!response.ok) {
    const errorPayload = isJson ? await response.json().catch(() => null) : null;
    const message =
      (errorPayload && errorPayload.message) ||
      (errorPayload &&
        errorPayload.error &&
        typeof errorPayload.error.message === "string" &&
        errorPayload.error.message) ||
      `HTTP ${response.status}`;
    throw new Error(message);
  }

  return isJson ? response.json() : response.text();
}

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
