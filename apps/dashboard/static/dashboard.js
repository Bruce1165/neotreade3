const queryParams = new URLSearchParams(window.location.search);
const sourceMode = queryParams.get("source") || "live";
const rawTargetDate = queryParams.get("date");
const devMode = queryParams.get("dev") === "1";
const theme = queryParams.get("theme") || "editorial";
const focusMode = true;
const apiBaseUrl = document.body.dataset.apiBaseUrl;
const effectiveDate = rawTargetDate || new Date().toISOString().slice(0, 10);
let apiKey = "";
let tradingCalendarMeta = null;
let dataControlStageSummary = null;
let factorMatrixIndex = null;
let stockLookupCache = new Map();
const PLACEHOLDER = "—";
const TEXT_LOADING = "加载中…";
const TEXT_SAVING = "保存中…";
const TEXT_RUNNING = "执行中…";
let lastScreenersPayload = null;
let selectedScreenerId = "";
let selectedScreenerConfig = null;
try {
  apiKey = window.localStorage.getItem("neo_api_key") || "";
} catch (error) {
  apiKey = "";
}

try {
  const versionEl = document.getElementById("dashboard-version");
  if (versionEl && document.body && document.body.dataset) {
    const version = document.body.dataset.dashboardJsVersion;
    if (version) versionEl.textContent = String(version);
  }
} catch (error) {
  // ignore
}

function fnv1aHex(input) {
  const str = String(input || "");
  let hash = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) {
    hash ^= str.charCodeAt(i);
    hash = (hash * 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function getV2DbPath() {
  try {
    const value = window.localStorage.getItem("neo_v2_db_path");
    if (value && String(value).trim()) return String(value).trim();
  } catch (error) {
    return "";
  }
  return "";
}

function formatSourceMode(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "stored") return "回放（已保存）";
  return "实时计算";
}

function formatCacheStatus(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "hit") return "命中";
  if (normalized === "miss") return "未命中";
  if (!normalized) return PLACEHOLDER;
  return normalized;
}

function formatRunStatus(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "ok") return "成功";
  if (normalized === "running") return "运行中";
  if (normalized === "blocked") return "阻塞";
  if (normalized === "failed") return "失败";
  if (normalized === "pending_implementation") return "待实现";
  if (normalized === "planned") return "计划中";
  if (!normalized) return "未知";
  return normalized;
}

function formatTaskMessage(value) {
  const raw = String(value || "").trim();
  if (!raw) return "阻塞";
  return raw
    .replace(/\s*\(Task is blocked during plan construction\.\)\s*/gi, "（计划构建阶段阻塞）")
    .replace(/Task is blocked during plan construction\./gi, "计划构建阶段阻塞")
    .replace(/Task execution has not been implemented in NeoTrade3 yet\./gi, "该任务在 NeoTrade3 尚未实现执行。")
    .replace(/\s+/g, " ")
    .trim();
}

function formatTaskLabel(taskId, plannedTask) {
  const id = String(taskId || "").trim();
  if (!id) return "未知任务";
  if (id.startsWith("data_control.")) {
    const stage = id.split(".", 2)[1] || id;
    if (stage === "capture") return "数据主链 · 采集";
    if (stage === "compose") return "数据主链 · 加工";
    if (stage === "publish") return "数据主链 · 发布";
    return `数据主链 · ${stage}`;
  }
  const labId = plannedTask && plannedTask.lab_id ? String(plannedTask.lab_id) : "";
  if (labId === "paper_simulation_lab") return "模拟交易 · 每日运行";
  if (labId === "five_flags_lab") return "老鸭头五图 · 每日扫描";
  if (labId === "cup_handle_lab") return "杯柄 · 每日复核";
  if (labId === "quant_trading_lab") return "量化交易 · 每日分析";
  return id;
}

function formatTaskBlockReason(plannedTask) {
  const reason = plannedTask && plannedTask.skip_reason ? String(plannedTask.skip_reason) : "";
  if (!reason) return "";
  if (reason === "publish_not_successful") return "等待发布闸门通过";
  return reason;
}

function formatUnauthorizedHint(action) {
  const verb = String(action || "").trim();
  if (!verb) {
    return "未授权：请到「管理 → 系统设置」填写正确的 API Key 后重试。";
  }
  return `未授权：请到「管理 → 系统设置」填写正确的 API Key 后再${verb}。`;
}

function formatValidationStatus(value) {
  const normalized = String(value || "").toLowerCase();
  if (!normalized) return PLACEHOLDER;
  if (normalized === "ok") return "通过";
  if (normalized === "failed") return "失败";
  return String(value);
}

document.getElementById("source-mode").textContent = formatSourceMode(sourceMode);
document.getElementById("current-date").textContent = effectiveDate;
document.body.classList.remove("theme-editorial", "theme-industrial");
document.body.classList.add(`theme-${theme}`);
if (devMode) {
  document.body.classList.add("dev-mode");
} else {
  document.body.classList.remove("dev-mode");
}

if (focusMode) {
  document.body.classList.add("focus-mode");
} else {
  document.body.classList.remove("focus-mode");
}

function applyFocusMode() {
  const sections = Array.from(document.querySelectorAll("main > section"));
  if (!focusMode) {
    for (const section of sections) {
      section.hidden = false;
    }
    return;
  }

  const hash = window.location.hash || "#section-overview";
  let targetId = hash.startsWith("#") ? hash.slice(1) : hash;
  if (!sections.some((section) => section.id === targetId)) {
    targetId = "section-overview";
  }
  for (const section of sections) {
    section.hidden = section.id !== targetId;
  }
}

function applyNavActive() {
  const hash = window.location.hash || "#section-overview";
  const links = Array.from(document.querySelectorAll(".sidebar-nav a"));
  for (const link of links) {
    const href = link.getAttribute("href") || "";
    link.classList.toggle("is-active", href === hash);
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

function clearElement(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.prototype.toString.call(value) === "[object Object]"
  );
}

function deepMerge(base, override) {
  if (!isPlainObject(base)) base = {};
  if (!isPlainObject(override)) override = {};
  const out = { ...base };
  for (const [key, value] of Object.entries(override)) {
    if (isPlainObject(value) && isPlainObject(out[key])) {
      out[key] = deepMerge(out[key], value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function getLatestTradingDay() {
  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  return maxTradingDay;
}

function buildApiUrl(path) {
  const separator = path.includes("?") ? "&" : "?";
  const parts = [`source=${encodeURIComponent(sourceMode)}`];
  parts.push(`date=${encodeURIComponent(effectiveDate)}`);
  return `${apiBaseUrl}${path}${separator}${parts.join("&")}`;
}

function openScreenerConfigModal({ screenerId } = {}) {
  const modal = document.getElementById("screener-config-modal");
  if (!modal) return;
  modal.hidden = false;
  document.body.classList.add("modal-open");

  if (typeof screenerId === "string" && screenerId.trim()) {
    selectedScreenerId = screenerId.trim();
  }
  const filterEl = document.getElementById("screener-config-filter");
  if (filterEl && typeof screenerId === "string" && screenerId.trim()) {
    filterEl.value = "";
  }
  const selectEl = document.getElementById("screener-config-select");
  if (selectEl && selectedScreenerId) {
    selectEl.value = selectedScreenerId;
  }
  if (lastScreenersPayload) {
    renderScreenerConfigPanel(lastScreenersPayload);
  }
  loadSelectedScreenerConfig();
}

function closeScreenerConfigModal() {
  const modal = document.getElementById("screener-config-modal");
  if (!modal) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
}

function buildFactorMatrixIndex(factorMatrix) {
  const index = {};
  if (!factorMatrix || typeof factorMatrix !== "object") return index;
  const tiers = factorMatrix.tiers && typeof factorMatrix.tiers === "object"
    ? factorMatrix.tiers
    : {};
  const tierLabels = {
    ge_80: ">=80",
    ge_70: ">=70",
    ge_60: ">=60",
  };
  for (const [tierKey, items] of Object.entries(tiers)) {
    if (!Array.isArray(items)) continue;
    for (const candidate of items) {
      if (!candidate || typeof candidate !== "object") continue;
      const code = String(candidate.stock_code || "").trim();
      if (!code) continue;
      const name = String(candidate.stock_name || "").trim() || code;
      const subscores = candidate.subscores && typeof candidate.subscores === "object"
        ? candidate.subscores
        : {};
      const score = Number(subscores.overall ?? candidate.certainty ?? 0);
      const certainty = Number(candidate.certainty ?? score);
      const tier_label = tierLabels[tierKey] || tierKey;
      index[code] = {
        stock_code: code,
        stock_name: name,
        score,
        certainty,
        tier_label,
        sector_lv1: String(candidate.sector_lv1 || "").trim(),
        subscores,
        raw_candidate: candidate,
      };
    }
  }
  return index;
}

async function lookupStocksByCodes(codes) {
  const unique = Array.from(
    new Set(
      (Array.isArray(codes) ? codes : [])
        .map((value) => String(value || "").trim())
        .filter((value) => value)
        .map((value) => value.split(".", 1)[0])
    )
  );
  const missing = unique.filter((code) => !stockLookupCache.has(code));
  if (missing.length === 0) return;

  const chunkSize = 120;
  for (let i = 0; i < missing.length; i += chunkSize) {
    const chunk = missing.slice(i, i + chunkSize);
    const payload = await fetchJson(
      `/api/stocks/lookup?codes=${encodeURIComponent(chunk.join(","))}`
    );
    const items = payload && Array.isArray(payload.items) ? payload.items : [];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const code = String(item.stock_code || "").trim();
      if (!code) continue;
      stockLookupCache.set(code, {
        stock_code: code,
        stock_name: String(item.stock_name || "").trim() || code,
      });
    }
  }
}

async function enrichStockRows(codes) {
  const list = Array.isArray(codes) ? codes : [];
  const normalized = list
    .map((value) => String(value || "").trim())
    .filter((value) => value)
    .map((value) => value.split(".", 1)[0]);

  await lookupStocksByCodes(normalized);

  return normalized.map((code) => {
    const fromMatrix = factorMatrixIndex && factorMatrixIndex[code] ? factorMatrixIndex[code] : null;
    const fromLookup = stockLookupCache.has(code) ? stockLookupCache.get(code) : null;
    const stockName = fromMatrix
      ? fromMatrix.stock_name
      : fromLookup
        ? fromLookup.stock_name
        : code;
    const score = fromMatrix ? fromMatrix.score : null;
    const certainty = fromMatrix ? fromMatrix.certainty : null;
    const tier_label = fromMatrix ? fromMatrix.tier_label : null;
    return {
      stock_code: code,
      stock_name: stockName,
      score,
      certainty,
      tier_label,
    };
  });
}

function formatErrorMessage(error) {
  if (error && error.payload && error.payload.error) {
    const apiError = error.payload.error;
    return `${apiError.code}: ${apiError.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatMeta(payload) {
  const meta = payload && payload._meta ? payload._meta : {};
  const parts = [];

  if (payload && payload.snapshot_source) {
    parts.push(`来源 ${formatSourceMode(payload.snapshot_source)}`);
  }
  if (meta.cache_status) {
    parts.push(`缓存 ${formatCacheStatus(meta.cache_status)}`);
  }

  return parts.length > 0 ? parts.join(" · ") : "";
}

function sumPoolsByKeyword(pools, keywords) {
  const normalized = Array.isArray(pools) ? pools : [];
  const hits = normalized.filter((pool) => {
    if (!pool || typeof pool !== "object") return false;
    const id = String(pool.pool_id || "");
    const name = String(pool.display_name || "");
    const hay = `${id} ${name}`.toLowerCase();
    return keywords.some((keyword) => hay.includes(String(keyword).toLowerCase()));
  });
  if (hits.length === 0) return null;
  return hits.reduce((total, pool) => {
    const count =
      pool && typeof pool.member_count === "number" ? pool.member_count : 0;
    return total + count;
  }, 0);
}

function renderOverviewSummary({
  execDate,
  issuePayload,
  learningPayload,
  factorMatrixPayload,
  orchestrationRunsPayload,
  poolsPayload,
  stockCoveragePayload,
  marketPhasePayload,
  sectorRotationPayload,
  screenersPayload,
}) {
  // ---- 1. 市场阶段卡片 ----
  const mp = marketPhasePayload && marketPhasePayload.market_phase
    ? marketPhasePayload.market_phase
    : null;
  if (mp) {
    const phaseNames = { bull: "牛市", bear: "熊市", range: "震荡", transition: "过渡" };
    const phaseLabel = phaseNames[mp.code] || mp.code || "未知";
    setText("summary-market-phase", phaseLabel);
    setHtml("summary-market-phase-detail",
      mp.display ? `<span style="color:var(--muted)">${mp.display}</span>` : "");
  } else {
    setText("summary-market-phase", "不可用");
  }

  // ---- 2. 高确定性候选卡片 ----
  const factorSummary =
    factorMatrixPayload && factorMatrixPayload.candidates_summary
      ? factorMatrixPayload.candidates_summary
      : {};
  const ge80 = factorSummary.ge_80_count || 0;
  const ge70 = factorSummary.ge_70_count || 0;
  const ge60 = factorSummary.ge_60_count || 0;
  const totalCandidates = factorSummary.candidate_count || 0;
  setText("summary-high-certainty",
    ge80 > 0 ? `${ge80} 只 ≥80%` : (totalCandidates > 0 ? `${totalCandidates} 只候选` : "未生成"));
  setHtml("summary-certainty-detail",
    totalCandidates > 0
      ? `<span style="color:var(--muted)">≥80: ${ge80} | ≥70: ${ge70} | ≥60: ${ge60}</span>`
      : "");

  // ---- 3. 交易信号卡片 ----
  const labResult = factorMatrixPayload && factorMatrixPayload.lab_result
    ? factorMatrixPayload.lab_result
    : (factorMatrixPayload || {});
  const signals = labResult.trading_signals || [];
  const gradeDist = labResult.grade_distribution || {};
  setText("summary-trading-signals",
    signals.length > 0
      ? `${signals.length} 个信号 (A:${gradeDist.A||0} B:${gradeDist.B||0} C:${gradeDist.C||0})`
      : "无信号");
  if (signals.length > 0) {
    const top3 = signals.slice(0, 3).map(s =>
      `<span style="color:var(--accent)">${s.code}</span> ${s.name} <small>${s.grade}</small>`
    ).join(" &nbsp;|&nbsp; ");
    setHtml("summary-signals-detail", top3);
  }

  // ---- 4. Top 板块卡片 ----
  const sr = sectorRotationPayload && sectorRotationPayload.sector_rotation
    ? sectorRotationPayload.sector_rotation
    : null;
  if (sr && Array.isArray(sr.top_sectors) && sr.top_sectors.length > 0) {
    const top5 = sr.top_sectors.slice(0, 5)
      .map((s, i) => `${i+1}. ${s.sector_name || s.name || "?"} (${s.rps_score != null ? s.rps_score.toFixed(1) : "?"})`)
      .join("<br>");
    setHtml("summary-top-sectors", top5);
  } else {
    setText("summary-top-sectors", "不可用");
  }

  // ---- 5. 筛选器命中卡片 ----
  const scrRuns = screenersPayload && Array.isArray(screenersPayload.screener_runs)
    ? screenersPayload.screener_runs : [];
  const totalHits = scrRuns.reduce((sum, r) => sum + (r.hit_count || 0), 0);
  setText("summary-screener-hits",
    scrRuns.length > 0 ? `${scrRuns.length} 个筛选器, ${totalHits} 只命中` : "未运行");

  // ---- 6. 问题与告警 ----
  const issueCenter = issuePayload && issuePayload.issue_center ? issuePayload.issue_center : {};
  const issueCases = Array.isArray(issueCenter.cases) ? issueCenter.cases : [];
  setText("summary-issue-count", String(issueCases.length));
  if (issueCases.length > 0) {
    const issueHtml = issueCases.slice(0, 5).map(c =>
      `<div style="margin:4px 0;padding:4px 8px;background:var(--card);border-radius:4px;">
        <strong>${c.task_id || "?"}</strong> [${c.severity || "?"}] ${c.summary || "无描述"}
      </div>`
    ).join("");
    setHtml("overview-issues-box", issueHtml);
  } else {
    setHtml("overview-issues-box", '<span style="color:var(--muted)">无问题</span>');
  }

  // ---- 运维指标（dev-only，保留原有逻辑） ----
  setText("summary-exec-date", execDate || PLACEHOLDER);

  const runs = orchestrationRunsPayload && Array.isArray(orchestrationRunsPayload.orchestrator_runs)
    ? orchestrationRunsPayload.orchestrator_runs
    : [];
  const latestRun = runs[0] || null;
  if (!latestRun) {
    setText("summary-run-ok", "未运行");
    setText("summary-run-failed", "未运行");
  } else {
  const statusCounts =
    latestRun && latestRun.status_counts && typeof latestRun.status_counts === "object"
      ? latestRun.status_counts
      : null;
  setText(
    "summary-run-ok",
    statusCounts && statusCounts.ok != null ? String(statusCounts.ok) : "0"
  );
  setText(
    "summary-run-failed",
    statusCounts && statusCounts.failed != null ? String(statusCounts.failed) : "0"
  );
  }

  const coverage =
    stockCoveragePayload && stockCoveragePayload.coverage
      ? stockCoveragePayload.coverage
      : {};
  const ashareCount =
    coverage && typeof coverage.priced_stock_count === "number"
      ? coverage.priced_stock_count
      : null;
  setText("summary-pool-ashare", ashareCount == null ? "不可用" : String(ashareCount));
}

/* ============================================================
   全局状态栏渲染
   ============================================================ */
function renderDataStatusBar({ summaryPayload, dataControlPayload }) {
  // 数据更新日期（从 bootstrap-summary 的 target_date 获取）
  const targetDate = summaryPayload && summaryPayload.bootstrap_summary
    ? String(summaryPayload.bootstrap_summary.target_date || "")
    : "";
  const targetDateEl = document.getElementById("data-target-date");
  if (targetDateEl) {
    targetDateEl.textContent = targetDate || "--";
  }

  // 数据管线状态（从 data-control 的 stage_summary 获取）
  const dc = dataControlPayload && dataControlPayload.data_control
    ? dataControlPayload.data_control
    : {};
  const stageSummary = dc.stage_summary || {};
  const stages = stageSummary.stages || {};
  const publishStage = stages.publish || {};
  const publishStatus = String(publishStage.status || "unknown").toLowerCase();

  const pipelineStatusEl = document.getElementById("data-pipeline-status");
  const anomalyWarningEl = document.getElementById("data-anomaly-warning");

  const isOk = publishStatus === "ok";
  const isError = publishStatus === "failed" || publishStatus === "error";

  if (pipelineStatusEl) {
    const dotClass = isOk ? "data-pipeline-dot--ok"
      : isError ? "data-pipeline-dot--error"
      : "data-pipeline-dot--unknown";
    const statusText = isOk ? "正常"
      : isError ? "异常"
      : "未知";
    pipelineStatusEl.innerHTML = `<span class="data-pipeline-dot ${dotClass}"></span>${statusText}`;
  }

  if (anomalyWarningEl) {
    // 显示红色警告的条件：publish 失败 或 数据缺失（没有 target_date）
    const showWarning = isError || !targetDate;
    anomalyWarningEl.hidden = !showWarning;
  }
}

/* ============================================================
   热门板块详情渲染
   ============================================================ */
let cachedSectorRotation = null;
let cachedStockTiering = null;

async function renderSectorDetail() {
  const loadingEl = document.getElementById("sector-detail-loading");
  const contentEl = document.getElementById("sector-detail-content");
  if (!contentEl) return;

  // 加载 sector-rotation 和 stock-tiering 数据
  if (!cachedSectorRotation) {
    try { cachedSectorRotation = await fetchJson("/api/sector-rotation"); } catch (e) { cachedSectorRotation = null; }
  }
  if (!cachedStockTiering) {
    try { cachedStockTiering = await fetchJson("/api/stock-tiering"); } catch (e) { cachedStockTiering = null; }
  }

  if (loadingEl) loadingEl.hidden = true;

  const sr = cachedSectorRotation && cachedSectorRotation.sector_rotation
    ? cachedSectorRotation.sector_rotation
    : null;
  const topSectors = sr && Array.isArray(sr.top_sectors) ? sr.top_sectors : [];

  const st = cachedStockTiering && cachedStockTiering.stock_tiering
    ? cachedStockTiering.stock_tiering
    : null;
  const tierSectors = st && Array.isArray(st.sectors) ? st.sectors : [];

  // 建立 sector -> tiering 数据的索引
  const tieringIndex = {};
  for (const ts of tierSectors) {
    const sectorName = String(ts.sector || "").trim();
    if (sectorName) {
      tieringIndex[sectorName] = ts;
    }
  }

  if (topSectors.length === 0) {
    contentEl.innerHTML = '<div class="section-meta">暂无热门板块数据。</div>';
    return;
  }

  const displayCount = Math.min(topSectors.length, 7);
  const container = document.createDocumentFragment();

  for (let i = 0; i < displayCount; i++) {
    const sector = topSectors[i];
    const sectorName = String(sector.sector_name || sector.sector || sector.name || "未知板块");
    const rps20 = sector.rps_20 != null ? sector.rps_20 : (sector.rps_score != null ? sector.rps_score : null);
    const rps60 = sector.rps_60 != null ? sector.rps_60 : null;
    const isPolicy = Boolean(sector.is_policy_mainline);
    const defaultExpanded = i < 3;

    const tiering = tieringIndex[sectorName] || {};
    const leaders = Array.isArray(tiering.leaders) ? tiering.leaders : [];
    const cores = Array.isArray(tiering.cores) ? tiering.cores : [];
    const followers = Array.isArray(tiering.followers) ? tiering.followers : [];

    const card = document.createElement("div");
    card.className = "sector-card";

    // Header
    const header = document.createElement("div");
    header.className = `sector-card__header${defaultExpanded ? " is-expanded" : ""}`;

    const title = document.createElement("div");
    title.className = "sector-card__title";
    title.innerHTML = `<span class="sector-card__rank">${i + 1}</span>` +
      `<span class="sector-card__name">${sectorName}</span>` +
      (isPolicy ? '<span class="sector-card__policy-tag">政策主线</span>' : "");

    const meta = document.createElement("div");
    meta.style.cssText = "display:flex;align-items:center;gap:8px;";
    meta.innerHTML = `<span class="sector-card__rps">RPS20: ${rps20 != null ? rps20.toFixed(1) : "-"}` +
      (rps60 != null ? ` / RPS60: ${rps60.toFixed(1)}` : "") +
      `</span><span class="sector-card__toggle${defaultExpanded ? " is-expanded" : ""}">&#9660;</span>`;

    header.appendChild(title);
    header.appendChild(meta);
    card.appendChild(header);

    // Body
    const body = document.createElement("div");
    body.className = `sector-card__body${defaultExpanded ? " is-expanded" : ""}`;

    // 龙头股
    if (leaders.length > 0) {
      body.appendChild(buildTierGroup("龙头股", leaders, "leader"));
    }
    // 中军股
    if (cores.length > 0) {
      body.appendChild(buildTierGroup("中军股", cores, "core"));
    }
    // 跟随股
    if (followers.length > 0) {
      body.appendChild(buildTierGroup("跟随股", followers, "follower"));
    }

    if (leaders.length === 0 && cores.length === 0 && followers.length === 0) {
      const empty = document.createElement("div");
      empty.className = "section-meta";
      empty.textContent = "暂无个股分层数据。";
      body.appendChild(empty);
    }

    card.appendChild(body);

    // Toggle 事件
    header.addEventListener("click", () => {
      const isExpanded = body.classList.contains("is-expanded");
      body.classList.toggle("is-expanded");
      header.classList.toggle("is-expanded");
      const toggle = header.querySelector(".sector-card__toggle");
      if (toggle) toggle.classList.toggle("is-expanded");
    });

    container.appendChild(card);
  }

  clearElement(contentEl);
  contentEl.appendChild(container);
}

function buildTierGroup(label, stocks, tierType) {
  const group = document.createElement("div");
  group.className = "sector-tier-group";

  const badgeClass = tierType === "leader" ? "tier-badge--leader"
    : tierType === "core" ? "tier-badge--core"
    : "tier-badge--follower";

  const titleEl = document.createElement("div");
  titleEl.className = "sector-tier-group__title";
  titleEl.innerHTML = `${label}（${stocks.length}只）<span class="tier-badge ${badgeClass}">${
    tierType === "leader" ? "龙头" : tierType === "core" ? "中军" : "跟随"
  }</span>`;
  group.appendChild(titleEl);

  const table = document.createElement("table");
  table.className = "sector-stock-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr>" +
    "<th>代码</th>" +
    "<th>名称</th>" +
    "<th>上涨确定性</th>" +
    "<th>龙头分</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const stock of stocks) {
    const tr = document.createElement("tr");
    const code = String(stock.code || "-");
    const name = String(stock.name || "-");
    const confidence = stock.confidence != null ? stock.confidence : 0;
    const confPct = (confidence * 100).toFixed(1);
    const confClass = confidence >= 0.8 ? "confidence-high"
      : confidence >= 0.6 ? "confidence-mid"
      : "confidence-low";
    const leaderScore = stock.leadership_score != null ? stock.leadership_score.toFixed(1) : "-";

    tr.innerHTML = `<td>${code}</td><td>${name}</td>` +
      `<td class="${confClass}">${confPct}%</td><td>${leaderScore}</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  group.appendChild(table);

  return group;
}

/* ============================================================
   单股票增强信息渲染
   ============================================================ */
async function renderStockEnhancedInfo(stockCode) {
  const container = document.getElementById("stock-enhanced-info");
  if (!container) return;

  const sectorValueEl = document.getElementById("stock-sector-value");
  const tierValueEl = document.getElementById("stock-tier-value");
  const rpsValueEl = document.getElementById("stock-rps-value");
  const hitsValueEl = document.getElementById("stock-screener-hits-value");

  // 重置
  if (sectorValueEl) sectorValueEl.textContent = "查询中...";
  if (tierValueEl) tierValueEl.textContent = "查询中...";
  if (rpsValueEl) rpsValueEl.textContent = "查询中...";
  if (hitsValueEl) hitsValueEl.textContent = "查询中...";
  container.hidden = false;

  // 1. 从 stock-tiering 获取板块归属和分层
  let foundSector = null;
  let foundTier = null;
  let foundRps = null;

  if (!cachedStockTiering) {
    try { cachedStockTiering = await fetchJson("/api/stock-tiering"); } catch (e) { cachedStockTiering = null; }
  }

  const st = cachedStockTiering && cachedStockTiering.stock_tiering
    ? cachedStockTiering.stock_tiering
    : null;
  const tierSectors = st && Array.isArray(st.sectors) ? st.sectors : [];

  for (const ts of tierSectors) {
    const sectorName = String(ts.sector || "").trim();
    // 检查 leaders
    const leaders = Array.isArray(ts.leaders) ? ts.leaders : [];
    for (const s of leaders) {
      if (String(s.code || "") === stockCode) {
        foundSector = sectorName;
        foundTier = "龙头";
        foundRps = s.leadership_score != null ? s.leadership_score : null;
        break;
      }
    }
    if (foundTier) break;
    // 检查 cores
    const cores = Array.isArray(ts.cores) ? ts.cores : [];
    for (const s of cores) {
      if (String(s.code || "") === stockCode) {
        foundSector = sectorName;
        foundTier = "中军";
        foundRps = s.leadership_score != null ? s.leadership_score : null;
        break;
      }
    }
    if (foundTier) break;
    // 检查 followers
    const followers = Array.isArray(ts.followers) ? ts.followers : [];
    for (const s of followers) {
      if (String(s.code || "") === stockCode) {
        foundSector = sectorName;
        foundTier = "跟随";
        foundRps = s.leadership_score != null ? s.leadership_score : null;
        break;
      }
    }
    if (foundTier) break;
  }

  if (sectorValueEl) {
    sectorValueEl.textContent = foundSector || "未找到";
  }
  if (tierValueEl) {
    tierValueEl.textContent = foundTier || "未分层";
  }

  // 2. RPS 评分（从 sector-rotation 或 tiering 数据中获取）
  if (!cachedSectorRotation) {
    try { cachedSectorRotation = await fetchJson("/api/sector-rotation"); } catch (e) { cachedSectorRotation = null; }
  }

  // 如果 tiering 中没有 leadership_score，尝试从 sector-rotation 获取
  if (foundRps == null && cachedSectorRotation) {
    const sr = cachedSectorRotation.sector_rotation || {};
    const topSectors = Array.isArray(sr.top_sectors) ? sr.top_sectors : [];
    // sector-rotation 主要是板块级别的 RPS，个股 RPS 需要从 tiering 获取
  }

  if (rpsValueEl) {
    rpsValueEl.textContent = foundRps != null ? foundRps.toFixed(1) : "暂无数据";
  }

  // 3. 命中的筛选器（从 lastScreenersPayload 中匹配）
  const hitScreeners = [];
  if (lastScreenersPayload) {
    const runs = Array.isArray(lastScreenersPayload.screener_runs)
      ? lastScreenersPayload.screener_runs
      : [];
    for (const run of runs) {
      if (!run || run.status !== "ok") continue;
      const picks = Array.isArray(run.picks) ? run.picks : [];
      const matched = picks.some((p) =>
        p && (String(p.code || "") === stockCode || String(p.stock_code || "") === stockCode)
      );
      if (matched) {
        const registry = lastScreenersPayload.screeners_registry || {};
        const screeners = Array.isArray(registry.screeners) ? registry.screeners : [];
        const screenerDef = screeners.find((s) => String(s.screener_id || "") === String(run.screener_id || ""));
        const displayName = screenerDef
          ? String(screenerDef.display_name || screenerDef.name || run.screener_id)
          : String(run.screener_id || "未知");
        hitScreeners.push(displayName);
      }
    }
  }

  if (hitsValueEl) {
    if (hitScreeners.length > 0) {
      hitsValueEl.innerHTML = hitScreeners
        .map((name) => `<span class="stock-screener-hit-tag">${name}</span>`)
        .join("");
    } else {
      hitsValueEl.textContent = "未命中任何筛选器";
    }
  }
}

function summarizeDataControl(payload) {
  const registry = payload.source_registry || {};
  const sources = Array.isArray(registry.sources) ? registry.sources : [];
  const steps = payload.data_control && payload.data_control.plan
    && Array.isArray(payload.data_control.plan.steps)
    ? payload.data_control.plan.steps.length
    : 0;
  return `来源 ${sources.length}，步骤 ${steps}`;
}

function summarizeLabs(payload) {
  const labs = Array.isArray(payload.labs) ? payload.labs : [];
  const enabledCount = labs.filter((lab) => lab.enabled).length;
  const jobCount = labs.reduce((total, lab) => {
    const jobs = Array.isArray(lab.daily_jobs) ? lab.daily_jobs.length : 0;
    return total + jobs;
  }, 0);
  return `启用 ${enabledCount}/${labs.length}，每日任务 ${jobCount}`;
}

function summarizeOrchestration(payload) {
  const orchestration = payload.orchestration || {};
  const plan = orchestration.plan || {};
  const taskResults = Array.isArray(orchestration.task_results)
    ? orchestration.task_results
    : [];
  const blockedCount = taskResults.filter((result) => result.status === "blocked").length;
  const plannedTasks = Array.isArray(plan.planned_tasks) ? plan.planned_tasks.length : 0;
  const runLedger = orchestration.run_ledger || {};
  const runStatus = runLedger.status || "unknown";
  return `计划 ${plannedTasks}，阻塞 ${blockedCount}，状态 ${formatRunStatus(runStatus)}`;
}

function summarizeIssueCenter(payload) {
  const issueCenter = payload.issue_center || {};
  const cases = Array.isArray(issueCenter.cases) ? issueCenter.cases.length : 0;
  const events = Array.isArray(issueCenter.events) ? issueCenter.events.length : 0;
  return `案例 ${cases}，事件 ${events}`;
}

function summarizeLearning(payload) {
  const learning = payload.learning || {};
  const metrics = learning.metrics || {};
  const candidates = Array.isArray(learning.adjustment_candidates)
    ? learning.adjustment_candidates
    : [];
  const reviewRequired = candidates.filter(
    (candidate) => candidate.decision === "review_required"
  ).length;
  return `候选 ${candidates.length}，需复核 ${reviewRequired}，阻塞任务 ${metrics.blocked_tasks ?? PLACEHOLDER}`;
}

function summarizeScreeners(payload) {
  const registry = payload.screeners_registry || {};
  const screeners = Array.isArray(registry.screeners) ? registry.screeners : [];
  const enabledCount = screeners.filter((screener) => screener.enabled).length;
  const runs = Array.isArray(payload.screener_runs) ? payload.screener_runs : [];
  const okRuns = runs.filter((run) => run.status === "ok").length;
  const pendingRuns = runs.filter((run) => run.status === "pending_implementation").length;
  return `启用 ${enabledCount}/${screeners.length}，运行 ${runs.length}，成功 ${okRuns}，待实现 ${pendingRuns}`;
}

function renderListBox(containerId, title, items) {
  const container = document.getElementById(containerId);
  clearElement(container);

  const heading = document.createElement("h4");
  heading.textContent = title;
  container.appendChild(heading);

  if (!items || items.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "暂无。";
    container.appendChild(empty);
    return;
  }

  const ul = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    if (item instanceof Node) {
      li.appendChild(item);
    } else {
      li.textContent = String(item);
    }
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatMarketStatusBadge(value) {
  const raw = String(value || "").trim();
  if (!raw) return '<span class="mi-badge mi-badge--muted">未知</span>';
  const normalized = raw.toLowerCase();
  let cls = "mi-badge--muted";
  if (["focused", "high", "推荐", "up", "exception"].includes(raw) || ["focused", "high", "up", "exception"].includes(normalized)) {
    cls = "mi-badge--good";
  } else if (["mixed", "medium", "观察", "unknown"].includes(raw) || ["mixed", "medium", "unknown"].includes(normalized)) {
    cls = "mi-badge--warn";
  } else if (["weak", "low", "回避", "down"].includes(raw) || ["weak", "low", "down"].includes(normalized)) {
    cls = "mi-badge--bad";
  }
  return `<span class="mi-badge ${cls}">${escapeHtml(raw)}</span>`;
}

function renderMarketIntelligenceSummary(summaryPayload) {
  const container = document.getElementById("market-intelligence-summary-grid");
  if (!container) return;
  clearElement(container);
  const payload = summaryPayload && typeof summaryPayload === "object" ? summaryPayload : {};
  const summary = payload.summary && typeof payload.summary === "object" ? payload.summary : {};
  const counts = payload.counts && typeof payload.counts === "object" ? payload.counts : {};
  const cards = [
    {
      label: "主线集中度",
      value: summary.mainline_concentration || PLACEHOLDER,
      detail: `推荐 ${counts.recommended ?? 0} · 观察 ${counts.watchlist ?? 0} · 回避 ${counts.avoid ?? 0}`,
    },
    {
      label: "AI 聚焦",
      value: summary.ai_focus || PLACEHOLDER,
      detail: `AI 推荐 ${counts.recommended_ai ?? 0}`,
    },
    {
      label: "K 型干扰",
      value: summary.kshape_interference || PLACEHOLDER,
      detail: `推荐区向下 ${counts.recommended_kshape_down ?? 0} · 观察区向下 ${counts.watch_kshape_down ?? 0}`,
    },
    {
      label: "推荐集中度",
      value: summary.recommendation_concentration || PLACEHOLDER,
      detail: "建议层集中度摘要",
    },
  ];

  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "metric-card";
    article.innerHTML = `
      <div class="metric-label">${escapeHtml(card.label)}</div>
      <div class="metric-value metric-value--large">${formatMarketStatusBadge(card.value)}</div>
      <div class="metric-detail">${escapeHtml(card.detail)}</div>
    `;
    container.appendChild(article);
  }
}

function renderMarketIntelligenceThemes(reviewBoardPayload) {
  const container = document.getElementById("market-intelligence-themes");
  if (!container) return;
  const payload = reviewBoardPayload && typeof reviewBoardPayload === "object" ? reviewBoardPayload : {};
  const themeSummary = payload.theme_summary && typeof payload.theme_summary === "object" ? payload.theme_summary : {};
  const items = Array.isArray(themeSummary.items) ? themeSummary.items : [];
  if (items.length === 0) {
    container.innerHTML = '<div class="summary-line">暂无主线赛道。</div>';
    return;
  }
  const rows = items.slice(0, 8).map((item) => {
    const thematicTags = item && typeof item === "object" && item.thematic_tags && typeof item.thematic_tags === "object"
      ? item.thematic_tags
      : {};
    const kshape = thematicTags.kshape_direction && typeof thematicTags.kshape_direction === "object"
      ? thematicTags.kshape_direction.value
      : PLACEHOLDER;
    const penetration = thematicTags.penetration_stage && typeof thematicTags.penetration_stage === "object"
      ? (Array.isArray(thematicTags.penetration_stage.values) ? thematicTags.penetration_stage.values.join(", ") : thematicTags.penetration_stage.value || PLACEHOLDER)
      : PLACEHOLDER;
    const aiRelated = thematicTags.ai_related && thematicTags.ai_related.result ? "AI" : "非 AI";
    return `
      <tr>
        <td>${escapeHtml(item.concept_name || item.concept_code || PLACEHOLDER)}</td>
        <td>${formatMarketStatusBadge(aiRelated)}</td>
        <td>${formatMarketStatusBadge(kshape)}</td>
        <td>${escapeHtml(penetration || PLACEHOLDER)}</td>
        <td>${escapeHtml(String(item.board_score ?? PLACEHOLDER))}</td>
        <td>${escapeHtml(String(item.config_candidate_count ?? 0))}/${escapeHtml(String(item.institutional_candidate_count ?? 0))}/${escapeHtml(String(item.trading_candidate_count ?? 0))}</td>
      </tr>
    `;
  }).join("");
  container.innerHTML = `
    <div class="summary-line">前 ${Math.min(items.length, 8)} 条主线赛道，顺序沿用后端审阅排序。</div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>赛道</th>
            <th>AI</th>
            <th>K 型</th>
            <th>渗透率</th>
            <th>分数</th>
            <th>候选数</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderMarketIntelligenceCandidates(reviewBoardPayload) {
  const container = document.getElementById("market-intelligence-candidates");
  if (!container) return;
  const payload = reviewBoardPayload && typeof reviewBoardPayload === "object" ? reviewBoardPayload : {};
  const candidateSummary = payload.candidate_summary && typeof payload.candidate_summary === "object" ? payload.candidate_summary : {};
  const items = Array.isArray(candidateSummary.items) ? candidateSummary.items : [];
  if (items.length === 0) {
    container.innerHTML = '<div class="summary-line">暂无建议层候选。</div>';
    return;
  }
  const rows = items.slice(0, 10).map((item) => {
    const leaderSummary = item && typeof item === "object" && item.leader_summary && typeof item.leader_summary === "object"
      ? item.leader_summary
      : {};
    const candidateTypes = Array.isArray(leaderSummary.candidate_types) ? leaderSummary.candidate_types.join(" + ") : PLACEHOLDER;
    const reasons = Array.isArray(item.recommendation_reasons) ? item.recommendation_reasons.slice(0, 2).join("；") : PLACEHOLDER;
    return `
      <tr>
        <td>${escapeHtml(item.stock_code || PLACEHOLDER)}</td>
        <td>${escapeHtml(item.stock_name || PLACEHOLDER)}</td>
        <td>${formatMarketStatusBadge(item.recommendation_status || PLACEHOLDER)}</td>
        <td>${escapeHtml(candidateTypes)}</td>
        <td>${escapeHtml(reasons || PLACEHOLDER)}</td>
      </tr>
    `;
  }).join("");
  container.innerHTML = `
    <div class="summary-line">前 ${Math.min(items.length, 10)} 条建议层候选，按后端建议层排序展示。</div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>状态</th>
            <th>龙头身份</th>
            <th>原因摘要</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderMarketIntelligenceLinks(reviewBoardPayload) {
  const container = document.getElementById("market-intelligence-links");
  if (!container) return;
  const payload = reviewBoardPayload && typeof reviewBoardPayload === "object" ? reviewBoardPayload : {};
  const items = Array.isArray(payload.links) ? payload.links : [];
  if (items.length === 0) {
    container.innerHTML = '<div class="summary-line">暂无候选与赛道联动摘要。</div>';
    return;
  }
  const rows = items.slice(0, 10).map((item) => {
    const matchedThemes = Array.isArray(item.matched_themes)
      ? item.matched_themes.map((entry) => String(entry.concept_name || entry.concept_code || "")).filter((value) => value).join(" / ")
      : "";
    const penetration = Array.isArray(item.penetration_values) ? item.penetration_values.join(", ") : "";
    return `
      <tr>
        <td>${escapeHtml(item.stock_code || PLACEHOLDER)}</td>
        <td>${escapeHtml(item.stock_name || PLACEHOLDER)}</td>
        <td>${escapeHtml(matchedThemes || PLACEHOLDER)}</td>
        <td>${escapeHtml(penetration || PLACEHOLDER)}</td>
        <td>${formatMarketStatusBadge(item.recommendation_status || PLACEHOLDER)}</td>
      </tr>
    `;
  }).join("");
  container.innerHTML = `
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>关联赛道</th>
            <th>渗透率</th>
            <th>建议状态</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderMarketIntelligenceBoard({ reviewBoardPayload, decisionSummaryPayload }) {
  const statusEl = document.getElementById("market-intelligence-status");
  const errorEl = document.getElementById("market-intelligence-error");
  const rawEl = document.getElementById("market-intelligence-raw");
  if (statusEl) statusEl.textContent = "主线审阅已加载。";
  if (errorEl) errorEl.hidden = true;
  if (rawEl) {
    rawEl.textContent = formatJson({
      review_board: reviewBoardPayload,
      decision_summary: decisionSummaryPayload,
    });
  }
  renderMarketIntelligenceSummary(decisionSummaryPayload);
  renderMarketIntelligenceThemes(reviewBoardPayload);
  renderMarketIntelligenceCandidates(reviewBoardPayload);
  renderMarketIntelligenceLinks(reviewBoardPayload);
}

function renderDataControlStageSummary(payload) {
  const dataControl = payload.data_control || {};
  const stageSummary = dataControl.stage_summary || {};
  const stages = stageSummary.stages || {};
  const stageNames = ["capture", "compose", "publish"];
  const stageLabels = {
    capture: "采集",
    compose: "合成",
    publish: "发布",
  };

  const items = stageNames
    .filter((stage) => stages && Object.prototype.hasOwnProperty.call(stages, stage))
    .map((stage) => {
      const entry = stages[stage] || {};
      const status = entry.status || "unknown";
      const message = entry.message || "";
      const label = stageLabels[stage] || stage;
      return `${label}：${formatRunStatus(status)}${message ? `（${formatTaskMessage(message)}）` : ""}`;
    });

  renderListBox("data-control-stage-summary", "阶段摘要", items);
}

function renderOrchestrationBlocked(payload) {
  const orchestration = payload.orchestration || {};
  const plan = orchestration.plan || {};
  const plannedTasks = Array.isArray(plan.planned_tasks) ? plan.planned_tasks : [];
  const plannedIndex = Object.fromEntries(
    plannedTasks.map((task) => [task.task_id, task])
  );
  const taskResults = Array.isArray(orchestration.task_results)
    ? orchestration.task_results
    : [];
  const blocked = taskResults.filter((result) => result.status === "blocked");
  const items = blocked.map(
    (result) => {
      const planned = plannedIndex[result.task_id] || null;
      const label = formatTaskLabel(result.task_id, planned);
      const reason = formatTaskBlockReason(planned);
      return `${label}：${reason ? `${reason}；` : ""}${formatTaskMessage(result.message)}`;
    }
  );
  renderListBox("orchestration-blocked", "阻塞任务", items);
}

function renderIssueCases(payload) {
  const issueCenter = payload.issue_center || {};
  const cases = Array.isArray(issueCenter.cases) ? issueCenter.cases : [];
  const top = cases.slice(0, 10).map((item) => {
    const severity = item.severity || "unknown";
    const taskId = item.task_id || "unknown_task";
    const summary = item.summary || "";
    return `${severity}：${taskId}${summary ? `（${summary}）` : ""}`;
  });
  renderListBox("issue-center-cases", "问题案例（Top 10）", top);
}

function renderLearningCandidates(payload) {
  const learning = payload.learning || {};
  const candidates = Array.isArray(learning.adjustment_candidates)
    ? learning.adjustment_candidates
    : [];
  const top = candidates.slice(0, 10).map((candidate) => {
    const scope = candidate.scope || "unknown";
    const decision = candidate.decision || "unknown";
    const reason = candidate.reason || "";
    return `${decision}：${scope}${reason ? `（${reason}）` : ""}`;
  });
  renderListBox("learning-candidates", "调整候选（Top 10）", top);
}

function renderScreenerRuns(payload, opts) {
  const options = opts && typeof opts === "object" ? opts : {};
  const boxId = String(options.boxId || "screeners-runs");
  const title = String(options.title || "最近运行（Top 12）");
  const box = document.getElementById(boxId);
  if (!box) return;
  clearElement(box);

  const heading = document.createElement("h4");
  heading.textContent = title;
  box.appendChild(heading);

  const runs = Array.isArray(payload.screener_runs) ? payload.screener_runs : [];
  if (runs.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "暂无。";
    box.appendChild(empty);
    return;
  }

  const registry = payload.screeners_registry || {};
  const screeners = Array.isArray(registry.screeners) ? registry.screeners : [];
  const screenerNameIndex = {};
  for (const s of screeners) {
    if (!s || typeof s !== "object") continue;
    const id = String(s.screener_id || "").trim();
    if (!id) continue;
    const name = String(s.display_name || s.name || id).trim() || id;
    screenerNameIndex[id] = name;
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>运行日期</th>" +
    "<th>筛选器</th>" +
    "<th>状态</th>" +
    "<th>命中数</th>" +
    "<th>下载</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const run of runs.slice(0, 12)) {
    const date = String(run.target_date || "").trim();
    const screenerId = String(run.screener_id || "").trim();
    const status = String(run.status || "unknown");
    const picksCount = run.picks_count ?? PLACEHOLDER;
    const name = screenerId && screenerNameIndex[screenerId]
      ? screenerNameIndex[screenerId]
      : screenerId || "-";

    const tr = document.createElement("tr");
    const tdDate = document.createElement("td");
    tdDate.textContent = date || "-";
    const tdName = document.createElement("td");
    tdName.textContent = screenerId ? `${name}（${screenerId}）` : name;
    const tdStatus = document.createElement("td");
    tdStatus.textContent = formatRunStatus(status);
    const tdCount = document.createElement("td");
    tdCount.textContent = String(picksCount);
    const tdDownload = document.createElement("td");
    if (date && screenerId) {
      const link = document.createElement("a");
      link.className = "inline-link";
      link.textContent = "CSV";
      link.href = buildApiUrl(
        `/api/screeners/runs/${encodeURIComponent(date)}/${encodeURIComponent(
          screenerId
        )}/download.csv`
      );
      tdDownload.appendChild(link);
    } else {
      tdDownload.textContent = "-";
    }

    tr.appendChild(tdDate);
    tr.appendChild(tdName);
    tr.appendChild(tdStatus);
    tr.appendChild(tdCount);
    tr.appendChild(tdDownload);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  box.appendChild(tableWrap);
}

function normalizePickCodes(value) {
  if (!Array.isArray(value)) return [];
  const out = [];
  for (const item of value) {
    if (typeof item === "string") {
      const v = item.trim();
      if (v) out.push(v.split(".", 1)[0]);
      continue;
    }
    if (item && typeof item === "object") {
      const code = typeof item.code === "string" ? item.code.trim() : "";
      if (code) out.push(code.split(".", 1)[0]);
    }
  }
  return out;
}

function renderScreenerResultEmpty(message) {
  const meta = document.getElementById("screeners-result-meta");
  const view = document.getElementById("screeners-result-view");
  if (meta) meta.textContent = message || "尚未选择筛选器结果。";
  if (view) view.textContent = "—";
}

function buildScreenerResultTable(rows, options) {
  const title = options && options.title ? String(options.title) : "结果";
  const showFactor = Boolean(options && options.showFactor);
  const wrap = document.createElement("div");
  wrap.className = "screener-result-section";

  const heading = document.createElement("h4");
  heading.textContent = title;
  wrap.appendChild(heading);

  if (!rows || rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "summary-text";
    empty.textContent = "无";
    wrap.appendChild(empty);
    return wrap;
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>序号</th>" +
    "<th>股票</th>" +
    (showFactor ? "<th>矩阵分</th><th>确定性</th><th>档位</th>" : "") +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    const tdIdx = document.createElement("td");
    tdIdx.textContent = String(idx + 1);
    const tdStock = document.createElement("td");
    tdStock.textContent = `${row.stock_name}（${row.stock_code}）`;
    tr.appendChild(tdIdx);
    tr.appendChild(tdStock);
    if (showFactor) {
      const tdScore = document.createElement("td");
      tdScore.textContent =
        row.score == null || Number.isNaN(Number(row.score))
          ? "-"
          : Number(row.score).toFixed(2);
      const tdCert = document.createElement("td");
      tdCert.textContent =
        row.certainty == null || Number.isNaN(Number(row.certainty))
          ? "-"
          : Number(row.certainty).toFixed(2);
      const tdTier = document.createElement("td");
      tdTier.textContent = row.tier_label || "-";
      tr.appendChild(tdScore);
      tr.appendChild(tdCert);
      tr.appendChild(tdTier);
    }
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  wrap.appendChild(tableWrap);
  return wrap;
}

async function showScreenerResult({ targetDate, screenerId } = {}) {
  const date = String(targetDate || effectiveDate || "").trim();
  const id = String(screenerId || "").trim();
  if (!date || !id) {
    renderScreenerResultEmpty("尚未选择筛选器结果。");
    return;
  }

  const meta = document.getElementById("screeners-result-meta");
  const view = document.getElementById("screeners-result-view");
  if (meta) meta.textContent = `加载中：${id}（${date}）`;
  if (view) view.textContent = TEXT_LOADING;

  try {
    const detail = await fetchJson(
      `/api/screeners/runs/${encodeURIComponent(date)}/${encodeURIComponent(id)}`
    );
    const result =
      detail && detail.screener_result && typeof detail.screener_result === "object"
        ? detail.screener_result
        : {};
    const hotCodes = normalizePickCodes(result.hot_picks || result.picks || []);
    const coldCodes = normalizePickCodes(result.cold_picks || []);

    const hotRows = await enrichStockRows(hotCodes);
    const coldRows = await enrichStockRows(coldCodes);
    const showFactor =
      hotRows.some((row) => row.score != null || row.certainty != null)
      || coldRows.some((row) => row.score != null || row.certainty != null);

    if (meta) {
      meta.textContent = `日期 ${date} · 筛选器 ${id} · 热端 ${hotRows.length} · 冷端 ${coldRows.length}`;
    }

    if (!view) return;
    clearElement(view);

    const grid = document.createElement("div");
    grid.className = "screener-result-grid";
    grid.appendChild(buildScreenerResultTable(hotRows, { title: "热端（Hot）", showFactor }));
    grid.appendChild(buildScreenerResultTable(coldRows, { title: "冷端（Cold）", showFactor }));
    view.appendChild(grid);

    if (devMode) {
      setText("screener-result", formatJson(detail));
    }
  } catch (error) {
    const message = `加载失败：${formatErrorMessage(error)}`;
    renderScreenerResultEmpty(message);
    if (devMode) {
      setText("screener-result", message);
    }
  }
}

function findRunForDate(runs, targetDate, screenerId) {
  if (!Array.isArray(runs)) return null;
  const matches = runs.filter(
    (run) => run && run.target_date === targetDate && run.screener_id === screenerId
  );
  if (matches.length === 0) return null;
  matches.sort((a, b) =>
    String(b.requested_at || "").localeCompare(String(a.requested_at || ""))
  );
  return matches[0];
}

function renderScreenersRunner(payload, opts) {
  const options = opts && typeof opts === "object" ? opts : {};
  const runnerId = String(options.runnerId || "screeners-runner");
  const showResultButton = options.showResult !== false;
  const runner = document.getElementById(runnerId);
  if (!runner) return;
  clearElement(runner);

  const heading = document.createElement("h4");
  heading.textContent = devMode ? "运行面板（开发者模式）" : "一键运行（团队模式）";
  runner.appendChild(heading);

  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  const minTradingDay =
    calendar && calendar.min_trading_day ? String(calendar.min_trading_day) : null;
  const isDateBeyondCalendar =
    Boolean(maxTradingDay) && String(effectiveDate) > String(maxTradingDay);

  if (isDateBeyondCalendar) {
    const banner = document.createElement("div");
    banner.className = "status-banner error-banner";
    banner.textContent = `当前选择日期=${effectiveDate}，但本地数据/交易日历仅覆盖 ${minTradingDay || "?"} ~ ${maxTradingDay || "?"}。请切换到最新交易日后再运行筛选器。`;
    runner.appendChild(banner);

    const jump = document.createElement("button");
    jump.className = "btn";
    jump.style.marginTop = "10px";
    jump.textContent = `切换到最新交易日（${maxTradingDay}）`;
    jump.addEventListener("click", (event) => {
      event.preventDefault();
      const dateInput = document.getElementById("control-date");
      if (dateInput) {
        dateInput.value = maxTradingDay;
      }
      const refreshButton = document.getElementById("control-refresh");
      if (refreshButton) {
        refreshButton.click();
      }
    });
    runner.appendChild(jump);
  }

  const controls = document.createElement("div");
  controls.className = "controls";
  controls.style.marginTop = "10px";

  const bulkRunButton = document.createElement("button");
  bulkRunButton.className = "btn";
  bulkRunButton.textContent = "一键运行启用筛选器";
  bulkRunButton.disabled = isDateBeyondCalendar || !isDataReady();
  controls.appendChild(bulkRunButton);

  const bulkHint = document.createElement("span");
  bulkHint.className = "control-meta";
  bulkHint.style.marginLeft = "10px";
  bulkHint.textContent = "说明：团队模式只提供一键运行；单个筛选器的操作仅用于参数调整。";
  controls.appendChild(bulkHint);

  runner.appendChild(controls);

  const runnerStatus = document.createElement("div");
  runnerStatus.className = "section-meta";
  runnerStatus.style.marginTop = "8px";
  runnerStatus.textContent = isDataReady() ? "尚未运行。" : explainNotReady();
  runner.appendChild(runnerStatus);

  const registry = payload.screeners_registry || {};
  const screeners = Array.isArray(registry.screeners) ? registry.screeners : [];
  const runs = Array.isArray(payload.screener_runs) ? payload.screener_runs : [];

  if (screeners.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "暂无已注册筛选器。";
    runner.appendChild(empty);
    return;
  }

  bulkRunButton.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!window.confirm(`确认批量运行“启用筛选器”？\n日期：${computeWorkbenchDate()}`)) {
      return;
    }
    if (!isDataReady()) {
      const message = explainNotReady();
      runnerStatus.textContent = message;
      setText("screener-result", message);
      return;
    }
    bulkRunButton.disabled = true;
    runnerStatus.textContent = "批量运行中...";
    setText("screener-result", "批量运行中...");
    const runDate = computeWorkbenchDate();
    try {
      await postJson("/api/screeners/bulk-run", {
        date: runDate,
        requested_by: "dashboard",
        dry_run: false,
      });
      const refreshed = await fetchJson("/api/screeners");
      setDomainSection("screeners", refreshed, summarizeScreeners(refreshed));
      renderScreenerRuns(refreshed);
      renderScreenersRunner(refreshed);
      const doneMessage = `批量运行完成（日期 ${runDate}）。可在“最近运行”或各池中查看/下载。`;
      runnerStatus.textContent = doneMessage;
      setText("screener-result", doneMessage);
    } catch (error) {
      let message = `批量运行失败：${formatErrorMessage(error)}`;
      const apiError =
        error && error.payload && error.payload.error ? error.payload.error : null;
      if (apiError && apiError.code === "not_trading_day") {
        const calendarHint = tradingCalendarMeta;
        const hintMax =
          calendarHint && calendarHint.max_trading_day
            ? String(calendarHint.max_trading_day)
            : null;
        if (hintMax) {
          message = `批量运行失败：非交易日（当前 ${runDate}）。本地最新交易日 ${hintMax}。请切换日期后重试。`;
        }
      }
      if (apiError && apiError.code === "unauthorized") {
        message = `批量运行失败：${formatUnauthorizedHint("运行")}`;
      }
      runnerStatus.textContent = message;
      setText("screener-result", message);
    } finally {
      bulkRunButton.disabled = isDateBeyondCalendar || !isDataReady();
    }
  });

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>启用</th>" +
    "<th>筛选器</th>" +
    "<th>当日运行</th>" +
    "<th>操作</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const item of screeners) {
    const tr = document.createElement("tr");

    const enabled = Boolean(item.enabled);
    const screenerId = String(item.screener_id || "");
    const name = String(item.display_name || item.name || screenerId);
    const run = findRunForDate(runs, effectiveDate, screenerId);

    const enabledTd = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `pill ${enabled ? "ok" : "bad"}`;
    pill.textContent = enabled ? "启用" : "禁用";
    enabledTd.appendChild(pill);

    const nameTd = document.createElement("td");
    nameTd.textContent = `${name}（${screenerId}）`;

    const runTd = document.createElement("td");
    if (run) {
      const status = String(run.status || "unknown");
      const picksCount = run.picks_count ?? PLACEHOLDER;
      runTd.textContent = `状态 ${formatRunStatus(status)} · 命中数 ${picksCount}`;
    } else {
      runTd.textContent = "无";
    }

    const actionTd = document.createElement("td");
    const actionGroup = document.createElement("div");
    actionGroup.className = "table-actions";
    actionTd.appendChild(actionGroup);
    const paramButton = document.createElement("button");
    paramButton.className = "btn secondary";
    paramButton.textContent = "参数";
    paramButton.disabled = !screenerId;
    paramButton.addEventListener("click", (event) => {
      event.preventDefault();
      openScreenerConfigModal({ screenerId });
    });
    actionGroup.appendChild(paramButton);

    if (showResultButton) {
      const viewResultButton = document.createElement("button");
      viewResultButton.className = "btn secondary";
      viewResultButton.textContent = "结果";
      viewResultButton.disabled = !run || !screenerId;
      viewResultButton.addEventListener("click", (event) => {
        event.preventDefault();
        showScreenerResult({ targetDate: effectiveDate, screenerId });
      });
      actionGroup.appendChild(viewResultButton);
    }

    if (!devMode) {
      const downloadLink = document.createElement("a");
      downloadLink.className = "btn secondary";
      downloadLink.textContent = "下载 CSV";
      downloadLink.href = buildApiUrl(
        `/api/screeners/runs/${encodeURIComponent(
          effectiveDate
        )}/${encodeURIComponent(screenerId)}/download.csv`
      );
      downloadLink.setAttribute("role", "button");
      downloadLink.setAttribute("tabindex", "0");
      downloadLink.style.pointerEvents = run ? "auto" : "none";
      downloadLink.style.opacity = run ? "1" : "0.5";
      actionGroup.appendChild(downloadLink);
    }

    if (devMode) {
      const runButton = document.createElement("button");
      runButton.className = "btn";
      runButton.textContent = "运行";
      runButton.disabled = !enabled || !screenerId || isDateBeyondCalendar;

      const viewButton = document.createElement("button");
      viewButton.className = "btn secondary";
      viewButton.textContent = "查看";
      viewButton.disabled = !screenerId;

      const downloadLink = document.createElement("a");
      downloadLink.className = "btn secondary";
      downloadLink.textContent = "下载 CSV";
      downloadLink.href = buildApiUrl(
        `/api/screeners/runs/${encodeURIComponent(
          effectiveDate
        )}/${encodeURIComponent(screenerId)}/download.csv`
      );

      async function showResult() {
        setText("screener-result", TEXT_LOADING);
        try {
          const detail = await fetchJson(
            `/api/screeners/runs/${encodeURIComponent(
              effectiveDate
            )}/${encodeURIComponent(screenerId)}`
          );
          setText("screener-result", formatJson(detail));
          showScreenerResult({ targetDate: effectiveDate, screenerId });
        } catch (error) {
          setText("screener-result", `加载失败：${formatErrorMessage(error)}`);
        }
      }

      viewButton.addEventListener("click", (event) => {
        event.preventDefault();
        showResult();
      });

      runButton.addEventListener("click", async (event) => {
        event.preventDefault();
        runButton.disabled = true;
        setText("screener-result", TEXT_RUNNING);
        try {
          await postJson("/api/screeners/run", {
            screener_id: screenerId,
            date: effectiveDate,
            requested_by: "dashboard",
            dry_run: false,
            parameters: {},
          });
          await showResult();
          const refreshed = await fetchJson("/api/screeners");
          setDomainSection("screeners", refreshed, summarizeScreeners(refreshed));
          renderScreenerRuns(refreshed);
          renderScreenersRunner(refreshed);
        } catch (error) {
          let message = `执行失败：${formatErrorMessage(error)}`;
          const apiError =
            error && error.payload && error.payload.error
              ? error.payload.error
              : null;
          if (apiError && apiError.code === "not_trading_day") {
            const calendarHint = tradingCalendarMeta;
            const hintMax =
              calendarHint && calendarHint.max_trading_day
                ? String(calendarHint.max_trading_day)
                : null;
            if (hintMax) {
            message = `执行失败：非交易日（当前 ${effectiveDate}）。本地最新交易日 ${hintMax}。请切换日期后重试。`;
            }
          }
          if (apiError && apiError.code === "unauthorized") {
          message = `执行失败：${formatUnauthorizedHint("运行")}`;
          }
          setText("screener-result", message);
        } finally {
          runButton.disabled = !enabled || isDateBeyondCalendar;
        }
      });

      actionGroup.appendChild(runButton);
      actionGroup.appendChild(viewButton);
      actionGroup.appendChild(downloadLink);
    }

    tr.appendChild(enabledTd);
    tr.appendChild(nameTd);
    tr.appendChild(runTd);
    tr.appendChild(actionTd);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  runner.appendChild(table);
}

function computeWorkbenchDate() {
  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  if (maxTradingDay && String(effectiveDate) > String(maxTradingDay)) {
    return maxTradingDay;
  }
  return effectiveDate;
}

function isDataReady() {
  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  if (!maxTradingDay) return false;
  return String(effectiveDate) <= String(maxTradingDay);
}

function explainNotReady() {
  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  if (!maxTradingDay) {
    return "数据没准备好：交易日历不可用或未初始化。先同步/更新数据，再跑筛选器或量化矩阵。";
  }
  if (maxTradingDay && String(effectiveDate) > String(maxTradingDay)) {
    return `数据没准备好：当前日期 ${effectiveDate}，本地数据仅覆盖到最新交易日 ${maxTradingDay}。先切到最新交易日再跑。`;
  }
  return `数据没准备好：请先确认本地数据覆盖到 ${effectiveDate}（最新交易日 ${maxTradingDay}）。`;
}

function extractHitCount(candidate) {
  if (!candidate || typeof candidate !== "object") return null;
  const evidence = candidate.evidence;
  const lines = evidence && Array.isArray(evidence.technical_evidence)
    ? evidence.technical_evidence
    : [];
  for (const line of lines) {
    const match = String(line || "").match(/筛选器命中数：(\d+)/);
    if (match) return Number(match[1]);
  }
  return null;
}

function hasDigits(text) {
  return /\d/.test(String(text || ""));
}

function pickEvidenceLines(lines, maxCount) {
  const list = Array.isArray(lines) ? lines.map((v) => String(v || "").trim()) : [];
  const picked = [];
  for (const line of list) {
    if (!line) continue;
    if (hasDigits(line)) {
      picked.push(line);
      if (picked.length >= maxCount) return picked;
    }
  }
  for (const line of list) {
    if (!line) continue;
    if (picked.includes(line)) continue;
    picked.push(line);
    if (picked.length >= maxCount) return picked;
  }
  return picked;
}

function filterUserEvidence(lines) {
  const list = Array.isArray(lines) ? lines.map((v) => String(v || "").trim()) : [];
  return list.filter((line) => {
    if (!line) return false;
    if (line.includes("db_path")) return false;
    if (line.includes("期望路径")) return false;
    if (line.includes("artifact_path")) return false;
    if (line.includes("表：")) return false;
    if (line.includes("/")) return false;
    return true;
  });
}
function formatNumber(value, digits) {
  const n = Number(value);
  if (!Number.isFinite(n)) return PLACEHOLDER;
  const precision = typeof digits === "number" ? digits : 2;
  return n.toFixed(precision);
}

function buildCandidateCheckLine(opts) {
  const tierLabel = opts && opts.tier_label ? String(opts.tier_label) : "候选";
  const score = opts && Object.prototype.hasOwnProperty.call(opts, "score") ? opts.score : null;
  const certainty = opts && Object.prototype.hasOwnProperty.call(opts, "certainty") ? opts.certainty : null;
  const hitCount = opts && Object.prototype.hasOwnProperty.call(opts, "hit_count") ? opts.hit_count : null;
  const evidence = opts && opts.evidence ? String(opts.evidence) : "";
  const parts = [`入选 ${tierLabel}`];
  parts.push(`评分 ${formatNumber(score, 1)}`);
  parts.push(`确定性 ${formatNumber(certainty, 2)}`);
  if (hitCount != null && Number.isFinite(Number(hitCount))) {
    parts.push(`筛选器命中 ${Number(hitCount)}`);
  }
  if (evidence) {
    parts.push(`证据：${evidence}`);
  }
  return parts.join(" · ");
}


function buildStockCheckSummary(payload) {
  const checks = payload && payload.checks ? payload.checks : {};
  const presence = checks && checks.picks_presence ? checks.picks_presence : {};
  const message = String(presence && presence.message ? presence.message : "无法判断");

  const screenerItems =
    checks && checks.screeners && Array.isArray(checks.screeners.items)
      ? checks.screeners.items
      : [];
  const decided = screenerItems.filter(
    (item) => item && (item.result === true || item.result === false)
  );
  const hits = decided.filter((item) => item && item.result === true);

  const parts = [`结论：${message}`];
  if (decided.length > 0) {
    parts.push(`命中${hits.length}/${decided.length}个筛选器`);
  }
  if (hits.length > 0) {
    const names = hits
      .map((item) => String(item && item.name ? item.name : "").trim())
      .filter((v) => v);
    if (names.length > 0) {
      const preview = names.slice(0, 3).join("、") + (names.length > 3 ? "等" : "");
      parts.push(`命中：${preview}`);
    }
  }

  let evidenceLines = [];
  const universe = checks && checks.universe_filters ? checks.universe_filters : {};
  const baseReasons = Array.isArray(universe.reasons) ? universe.reasons : [];
  const baseEvidence = filterUserEvidence(universe.evidence);

  if (message === "未通过") {
    const firstFail = decided.find((item) => item && item.result === false) || null;
    const failReasons = firstFail && Array.isArray(firstFail.reasons) ? firstFail.reasons : [];
    const failEvidence = firstFail && Array.isArray(firstFail.evidence) ? firstFail.evidence : [];
    evidenceLines = pickEvidenceLines(
      [...filterUserEvidence(failReasons), ...filterUserEvidence(failEvidence), ...filterUserEvidence(baseReasons), ...baseEvidence],
      2
    );
  } else {
    evidenceLines = pickEvidenceLines(
      [...filterUserEvidence(baseReasons), ...baseEvidence],
      2
    );
  }

  if (evidenceLines.length > 0) {
    parts.push(`证据：${evidenceLines.join("；")}`);
  }

  return parts.join("；");
}

function renderEvidenceTable(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>指标</th>" +
    "<th>当前值</th>" +
    "<th>阈值</th>" +
    "<th>结果</th>" +
    "<th>说明</th>" +
    "</tr>";
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const row of list) {
    if (!row || typeof row !== "object") continue;
    const tr = document.createElement("tr");
    const tdMetric = document.createElement("td");
    tdMetric.textContent = String(row.metric ?? "-");
    const tdCurrent = document.createElement("td");
    tdCurrent.textContent = String(row.current ?? "-");
    const tdThreshold = document.createElement("td");
    tdThreshold.textContent = String(row.threshold ?? "-");
    const tdResult = document.createElement("td");
    tdResult.textContent = String(row.result ?? "-");
    const tdNote = document.createElement("td");
    tdNote.textContent = String(row.note ?? "-");
    tr.appendChild(tdMetric);
    tr.appendChild(tdCurrent);
    tr.appendChild(tdThreshold);
    tr.appendChild(tdResult);
    tr.appendChild(tdNote);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function renderStockMatrixBox(stockCode) {
  const box = document.getElementById("stock-matrix-box");
  if (!box) return;
  clearElement(box);

  const heading = document.createElement("h3");
  heading.textContent = "量化矩阵解释";
  box.appendChild(heading);

  const normalized = String(stockCode || "").trim().split(".", 1)[0];
  if (!normalized) {
    const line = document.createElement("div");
    line.className = "summary-line";
    line.textContent = "尚未选择股票。";
    box.appendChild(line);
    return;
  }

  const entry =
    factorMatrixIndex && factorMatrixIndex[normalized] ? factorMatrixIndex[normalized] : null;
  if (!entry) {
    const line = document.createElement("div");
    line.className = "summary-line";
    line.textContent = "量化矩阵中未找到该标的（可能当日矩阵尚未生成或未入候选）。";
    box.appendChild(line);
    return;
  }

  const summary = document.createElement("div");
  summary.className = "summary-line";
  const tier = String(entry.tier_label || PLACEHOLDER);
  const certainty =
    typeof entry.certainty === "number"
      ? entry.certainty.toFixed(2)
      : String(entry.certainty ?? PLACEHOLDER);
  const sector = String(entry.sector_lv1 || PLACEHOLDER);
  summary.textContent = `矩阵档位 ${tier} · 置信度 ${certainty} · 板块 ${sector}`;
  box.appendChild(summary);

  const subscores =
    entry.subscores && typeof entry.subscores === "object" ? entry.subscores : {};
  const pairs = Object.entries(subscores).map(([k, v]) => ({ key: k, value: v }));
  pairs.sort((a, b) => Number(b.value ?? 0) - Number(a.value ?? 0));
  if (pairs.length === 0) {
    const line = document.createElement("div");
    line.textContent = "暂无分项评分。";
    box.appendChild(line);
    return;
  }

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>维度</th><th>评分</th></tr>";
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const item of pairs) {
    const tr = document.createElement("tr");
    const tdK = document.createElement("td");
    tdK.textContent = String(item.key || "-");
    const tdV = document.createElement("td");
    tdV.textContent = String(item.value ?? "-");
    tr.appendChild(tdK);
    tr.appendChild(tdV);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  box.appendChild(table);
}

function renderStockCheckResult(payload) {
  const container = document.getElementById("stock-check-result");
  if (!container) return;
  clearElement(container);

  const stockCode = payload && typeof payload === "object" ? payload.stock_code : null;
  renderStockMatrixBox(stockCode);

  const checks = payload && payload.checks ? payload.checks : {};
  const presence = checks && checks.picks_presence ? checks.picks_presence : {};
  const presenceMessage = String(presence && presence.message ? presence.message : "无法判断");
  const summary = document.createElement("div");
  summary.textContent = `结论：${presenceMessage}`;
  container.appendChild(summary);

  const universe = checks && checks.universe_filters ? checks.universe_filters : {};
  const universeRows = universe && Array.isArray(universe.evidence_table) ? universe.evidence_table : [];
  if (universeRows.length > 0) {
    const h = document.createElement("h4");
    h.textContent = "基础过滤（证据表）";
    h.style.marginTop = "12px";
    container.appendChild(h);
    container.appendChild(renderEvidenceTable(universeRows));
  }

  const screeners =
    checks && checks.screeners && Array.isArray(checks.screeners.items)
      ? checks.screeners.items
      : [];
  if (screeners.length > 0) {
    const h = document.createElement("h4");
    h.textContent = "筛选器检查";
    h.style.marginTop = "12px";
    container.appendChild(h);

    const table = document.createElement("table");
    table.className = "table";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr>" +
      "<th>筛选器</th>" +
      "<th>结论</th>" +
      "<th>原因（摘要）</th>" +
      "</tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const item of screeners) {
      if (!item || typeof item !== "object") continue;
      const tr = document.createElement("tr");
      const tdName = document.createElement("td");
      tdName.textContent = String(item.name || item.screener_id || "-");
      const tdMsg = document.createElement("td");
      tdMsg.textContent = String(item.message || "-");
      const tdReason = document.createElement("td");
      const reasons = Array.isArray(item.reasons) ? item.reasons : [];
      tdReason.textContent = reasons.length > 0 ? String(reasons[0]) : "-";
      tr.appendChild(tdName);
      tr.appendChild(tdMsg);
      tr.appendChild(tdReason);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    container.appendChild(table);

    const focus =
      screeners.find((item) => item && item.result === false) ||
      screeners.find((item) => item && item.result == null) ||
      screeners[0];
    const focusRows =
      focus && typeof focus === "object" && Array.isArray(focus.evidence_table)
        ? focus.evidence_table
        : [];
    if (focusRows.length > 0) {
      const hh = document.createElement("h4");
      hh.textContent = `证据表（${String(focus.name || focus.screener_id || "筛选器")}）`;
      hh.style.marginTop = "12px";
      container.appendChild(hh);
      container.appendChild(renderEvidenceTable(focusRows));
    }
  }

  const tracking = checks && checks.tracking_lists ? checks.tracking_lists : {};
  const trackingItems = tracking && Array.isArray(tracking.items) ? tracking.items : [];
  const trackingMessage = tracking && tracking.message ? String(tracking.message) : "";
  const trackingHeader = document.createElement("h4");
  trackingHeader.textContent = "观察池检查";
  trackingHeader.style.marginTop = "12px";
  container.appendChild(trackingHeader);
  if (trackingMessage) {
    const line = document.createElement("div");
    line.className = "summary-line";
    line.textContent = trackingMessage;
    container.appendChild(line);
  }

  if (trackingItems.length > 0) {
    const table = document.createElement("table");
    table.className = "table";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr>" +
      "<th>池</th>" +
      "<th>类型</th>" +
      "<th>观察时间</th>" +
      "<th>原因</th>" +
      "</tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const item of trackingItems) {
      if (!item || typeof item !== "object") continue;
      const tr = document.createElement("tr");
      const tdName = document.createElement("td");
      tdName.textContent = String(item.list_name || item.list_id || "-");
      const tdType = document.createElement("td");
      tdType.textContent = String(item.list_type || "-");
      const tdTime = document.createElement("td");
      tdTime.textContent = String(item.observed_at || PLACEHOLDER);
      const tdReason = document.createElement("td");
      const reasons = Array.isArray(item.reasons) ? item.reasons : [];
      tdReason.textContent = reasons.length > 0 ? String(reasons[0]) : "-";
      tr.appendChild(tdName);
      tr.appendChild(tdType);
      tr.appendChild(tdTime);
      tr.appendChild(tdReason);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    container.appendChild(table);
  } else {
    const empty = document.createElement("div");
    empty.textContent = "未命中任何观察池。";
    container.appendChild(empty);
  }
}

function flattenSchemaFields(schema, prefix) {
  const root = schema && typeof schema === "object" ? schema : {};
  const basePrefix = prefix ? String(prefix) : "";
  const fields = [];
  const props = root.properties && typeof root.properties === "object" ? root.properties : {};
  for (const [key, child] of Object.entries(props)) {
    const path = basePrefix ? `${basePrefix}.${key}` : String(key);
    const childSchema = child && typeof child === "object" ? child : {};
    const type = childSchema.type;
    if (type === "object") {
      fields.push(...flattenSchemaFields(childSchema, path));
      continue;
    }
    const childProps =
      childSchema.properties && typeof childSchema.properties === "object"
        ? childSchema.properties
        : null;
    if (childProps) {
      fields.push(...flattenSchemaFields(childSchema, path));
      continue;
    }
    const displayName = String(childSchema.x_display_name || childSchema.title || "").trim();
    fields.push({
      path,
      schema: childSchema,
      display_name: displayName,
      description: String(childSchema.description || "").trim(),
      unit: String(childSchema.x_unit || "").trim(),
      group: String(childSchema.x_group || "").trim(),
      min: childSchema.x_min,
      max: childSchema.x_max,
      step: childSchema.x_step,
    });
  }
  fields.sort((a, b) => String(a.path).localeCompare(String(b.path)));
  return fields;
}

function getByPath(obj, path) {
  if (!obj || typeof obj !== "object") return undefined;
  const parts = String(path || "").split(".").filter((v) => v);
  let cur = obj;
  for (const part of parts) {
    if (!cur || typeof cur !== "object") return undefined;
    cur = cur[part];
  }
  return cur;
}

function setByPath(obj, path, value) {
  const parts = String(path || "").split(".").filter((v) => v);
  let cur = obj;
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i];
    if (i === parts.length - 1) {
      cur[part] = value;
      return;
    }
    if (!cur[part] || typeof cur[part] !== "object") {
      cur[part] = {};
    }
    cur = cur[part];
  }
}

function parseParamValue(raw, schema) {
  const trimmed = String(raw ?? "").trim();
  if (!trimmed) return { ok: true, value: undefined };
  if (trimmed.toLowerCase() === "null") return { ok: true, value: null };
  const t = schema && schema.type ? schema.type : null;
  const types = Array.isArray(t) ? t : t ? [t] : [];
  if (types.includes("number") || types.includes("integer")) {
    const n = Number(trimmed);
    if (!Number.isFinite(n)) return { ok: false, value: null };
    if (types.includes("integer")) return { ok: true, value: Math.trunc(n) };
    return { ok: true, value: n };
  }
  if (types.includes("boolean")) {
    const norm = trimmed.toLowerCase();
    if (norm === "true" || norm === "1" || norm === "yes" || norm === "y") return { ok: true, value: true };
    if (norm === "false" || norm === "0" || norm === "no" || norm === "n") return { ok: true, value: false };
    return { ok: false, value: null };
  }
  return { ok: true, value: trimmed };
}

function renderScreenerConfigForm(configPayload) {
  const formRoot = document.getElementById("screener-config-form");
  const statusEl = document.getElementById("screener-config-status");
  const jsonEl = document.getElementById("screener-config-json");
  if (!formRoot || !statusEl || !jsonEl) return;

  const cfg = configPayload && configPayload.screener_config ? configPayload.screener_config : {};
  const schema = cfg.schema || {};
  const defaultParams = cfg.default_parameters || {};
  const currentParams = cfg.current_parameters || {};
  const effective = deepMerge(defaultParams, currentParams);
  const screenerId = String(cfg.screener_id || selectedScreenerId || "");
  const updatedAt = cfg.updated_at ? String(cfg.updated_at) : "";
  statusEl.textContent = `已选择：${screenerId}${updatedAt ? ` · 更新于 ${updatedAt}` : ""}`;
  jsonEl.value = formatJson(currentParams);

  clearElement(formRoot);
  const fields = flattenSchemaFields(schema, "");
  if (fields.length === 0) {
    formRoot.textContent = "该筛选器没有可配置参数。";
    return;
  }

  const props = schema && schema.properties && typeof schema.properties === "object"
    ? schema.properties
    : {};

  const grouped = new Map();
  for (const field of fields) {
    const path = String(field.path || "");
    const parts = path.split(".").filter((v) => v);
    const explicitGroup = String(field.group || "").trim();
    const groupKey = explicitGroup ? explicitGroup : parts.length <= 1 ? "基本" : parts[0];
    if (!grouped.has(groupKey)) grouped.set(groupKey, []);
    grouped.get(groupKey).push(field);
  }

  const orderedGroupKeys = Array.from(grouped.keys());
  orderedGroupKeys.sort((a, b) => String(a).localeCompare(String(b)));
  if (orderedGroupKeys.includes("基本")) {
    orderedGroupKeys.splice(orderedGroupKeys.indexOf("基本"), 1);
    orderedGroupKeys.unshift("基本");
  }

  const maxOpenGroups = 1;
  let openCount = 0;

  for (const groupKey of orderedGroupKeys) {
    const groupFields = grouped.get(groupKey) || [];
    groupFields.sort((a, b) => String(a.path).localeCompare(String(b.path)));
    const rootSchema = groupKey !== "基本" && Object.prototype.hasOwnProperty.call(props, groupKey)
      ? props[groupKey]
      : null;
    const groupLabel = groupKey === "基本"
      ? "基本参数"
      : String(
        rootSchema && typeof rootSchema === "object"
          ? (rootSchema.x_display_name || rootSchema.title || groupKey)
          : groupKey
      ).trim() || groupKey;

    const details = document.createElement("details");
    details.className = "param-group";
    if (openCount < maxOpenGroups) {
      details.open = true;
      openCount += 1;
    }

    const summary = document.createElement("summary");
    summary.textContent = `${groupLabel}（${groupFields.length}）`;
    details.appendChild(summary);

    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    table.className = "table screener-config-table";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr>" +
      "<th>参数</th>" +
      "<th>当前值</th>" +
      "<th>默认值</th>" +
      "<th>说明</th>" +
      "</tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const field of groupFields) {
    const tr = document.createElement("tr");
    tr.dataset.path = field.path;
    tr.dataset.schema = JSON.stringify(field.schema || {});

    const tdKey = document.createElement("td");
    const label = String(field.display_name || "").trim();
    if (label) {
      const main = document.createElement("div");
      main.className = "param-label";
      main.textContent = label;
      const sub = document.createElement("div");
      sub.className = "param-path";
      sub.textContent = field.path;
      tdKey.appendChild(main);
      tdKey.appendChild(sub);
    } else {
      tdKey.textContent = field.path;
    }

    const tdCurrent = document.createElement("td");
    const input = document.createElement("input");
    input.className = "form-input";
    const currentValue = getByPath(currentParams, field.path);
    input.value = currentValue === undefined ? "" : String(currentValue);
    tdCurrent.appendChild(input);

    const tdDefault = document.createElement("td");
    const defaultValue = getByPath(defaultParams, field.path);
    const effectiveValue = getByPath(effective, field.path);
    tdDefault.textContent =
      defaultValue === undefined
        ? PLACEHOLDER
        : String(defaultValue) + (effectiveValue !== undefined ? ` · 生效 ${String(effectiveValue)}` : "");

    const tdDesc = document.createElement("td");
    const descParts = [];
    if (field.description) descParts.push(field.description);
    if (field.unit) descParts.push(`单位：${field.unit}`);
    const hasMin = field.min !== undefined && field.min !== null && String(field.min) !== "";
    const hasMax = field.max !== undefined && field.max !== null && String(field.max) !== "";
    if (hasMin || hasMax) {
      const minLabel = hasMin ? String(field.min) : "?";
      const maxLabel = hasMax ? String(field.max) : "?";
      descParts.push(`范围：${minLabel} ~ ${maxLabel}`);
    }
    const hasStep = field.step !== undefined && field.step !== null && String(field.step) !== "";
    if (hasStep) descParts.push(`步进：${String(field.step)}`);
    tdDesc.textContent = descParts.length ? descParts.join("；") : PLACEHOLDER;

    tr.appendChild(tdKey);
    tr.appendChild(tdCurrent);
    tr.appendChild(tdDefault);
    tr.appendChild(tdDesc);
    tbody.appendChild(tr);
  }
    table.appendChild(tbody);
    wrap.appendChild(table);
    details.appendChild(wrap);
    formRoot.appendChild(details);
  }
}

function buildCurrentParametersFromForm() {
  const formRoot = document.getElementById("screener-config-form");
  if (!formRoot) return { ok: false, params: {}, error: "参数面板不可用。" };
  if (!selectedScreenerConfig || typeof selectedScreenerConfig !== "object") {
    return { ok: false, params: {}, error: "筛选器配置尚未加载。" };
  }
  const cfg =
    selectedScreenerConfig && selectedScreenerConfig.screener_config
      ? selectedScreenerConfig.screener_config
      : {};
  const schema = cfg && cfg.schema ? cfg.schema : {};
  const fields = flattenSchemaFields(schema, "");
  if (fields.length === 0) return { ok: true, params: {}, error: "" };

  const params = {};
  for (const field of fields) {
    const tr = formRoot.querySelector(`tr[data-path="${CSS.escape(field.path)}"]`);
    if (!tr) continue;
    const input = tr.querySelector("input");
    if (!input) continue;
    const raw = String(input.value || "");
    if (!raw.trim()) continue;
    const parsed = parseParamValue(raw, field.schema);
    if (!parsed.ok) {
      return { ok: false, params: {}, error: `参数格式不合法：${field.path}` };
    }
    setByPath(params, field.path, parsed.value);
  }

  return { ok: true, params, error: "" };
}

async function loadSelectedScreenerConfig() {
  const statusEl = document.getElementById("screener-config-status");
  const formRoot = document.getElementById("screener-config-form");
  if (!statusEl || !formRoot) return;
  if (!selectedScreenerId) {
    statusEl.textContent = "尚未选择。";
    formRoot.textContent = "请选择上方筛选器。";
    return;
  }
  statusEl.textContent = TEXT_LOADING;
  formRoot.textContent = TEXT_LOADING;
  try {
    const payload = await fetchJson(`/api/screeners/config/${encodeURIComponent(selectedScreenerId)}`);
    selectedScreenerConfig = payload;
    renderScreenerConfigForm(payload);
  } catch (error) {
    const msg = `加载失败：${formatErrorMessage(error)}`;
    statusEl.textContent = msg;
    formRoot.textContent = msg;
  }
}

function renderScreenerConfigPanel(screenersPayload) {
  lastScreenersPayload = screenersPayload;
  const selectEl = document.getElementById("screener-config-select");
  const filterEl = document.getElementById("screener-config-filter");
  const listEl = document.getElementById("screener-config-list");
  const searchEl = document.getElementById("screener-config-search");
  if (!selectEl && (!listEl || !searchEl)) return;

  const registry = screenersPayload && screenersPayload.screeners_registry ? screenersPayload.screeners_registry : {};
  const screeners = Array.isArray(registry.screeners) ? registry.screeners : [];
  const items = screeners.map((s) => ({
    screener_id: String(s.screener_id || ""),
    display_name: String(s.display_name || s.name || s.screener_id || ""),
    enabled: Boolean(s.enabled),
    category: String(s.category || ""),
  })).filter((s) => s.screener_id);

  if (selectEl) {
    function repaintSelect() {
      const q = filterEl ? String(filterEl.value || "").trim().toLowerCase() : "";
      const filtered = q
        ? items.filter((it) => `${it.display_name} ${it.screener_id}`.toLowerCase().includes(q))
        : items;

      clearElement(selectEl);
      const head = document.createElement("option");
      head.value = "";
      head.textContent = q ? `选择筛选器…（匹配 ${filtered.length}）` : "选择筛选器…";
      selectEl.appendChild(head);
      for (const it of filtered) {
        const opt = document.createElement("option");
        opt.value = it.screener_id;
        opt.textContent = `${it.display_name}（${it.screener_id}）`;
        selectEl.appendChild(opt);
      }
      if (selectedScreenerId) {
        selectEl.value = selectedScreenerId;
      }
    }

    repaintSelect();

    if (!selectEl.dataset.bound) {
      selectEl.addEventListener("change", async () => {
        selectedScreenerId = String(selectEl.value || "").trim();
        await loadSelectedScreenerConfig();
        try {
          selectEl.blur();
        } catch (error) {
          return;
        }
      });
      selectEl.dataset.bound = "1";
    }

    if (filterEl && !filterEl.dataset.bound) {
      filterEl.addEventListener("input", () => {
        repaintSelect();
      });
      filterEl.dataset.bound = "1";
    }

    if (!listEl || !searchEl) {
      return;
    }
  }

  function paint() {
    const q = String(searchEl.value || "").trim().toLowerCase();
    clearElement(listEl);
    const filtered = q
      ? items.filter((it) => (it.display_name + " " + it.screener_id).toLowerCase().includes(q))
      : items;
    if (filtered.length === 0) {
      listEl.textContent = "未找到匹配的筛选器。";
      return;
    }
    for (const it of filtered) {
      const row = document.createElement("div");
      row.className = `screener-config-item${it.screener_id === selectedScreenerId ? " is-active" : ""}`;
      row.dataset.screenerId = it.screener_id;
      const left = document.createElement("div");
      const title = document.createElement("div");
      title.className = "screener-config-item-title";
      title.textContent = it.display_name || it.screener_id;
      const sub = document.createElement("div");
      sub.className = "screener-config-item-sub";
      sub.textContent = `${it.screener_id}${it.category ? ` · ${it.category}` : ""}`;
      left.appendChild(title);
      left.appendChild(sub);

      const pill = document.createElement("span");
      pill.className = `pill ${it.enabled ? "ok" : "bad"}`;
      pill.textContent = it.enabled ? "启用" : "禁用";

      row.appendChild(left);
      row.appendChild(pill);
      row.addEventListener("click", async (event) => {
        event.preventDefault();
        selectedScreenerId = it.screener_id;
        paint();
        await loadSelectedScreenerConfig();
      });
      listEl.appendChild(row);
    }
  }

  searchEl.addEventListener("input", paint);
  paint();
}

function renderWorkbenchCandidates(factorMatrix) {
  const tableRoot = document.getElementById("workbench-qm-table");
  const summaryRoot = document.getElementById("workbench-qm-summary");
  if (!tableRoot || !summaryRoot) return;

  if (!factorMatrix || typeof factorMatrix !== "object") {
    summaryRoot.textContent = "量化矩阵尚未加载。";
    tableRoot.textContent = "量化矩阵尚未加载。";
    return;
  }

  const targetDate = String(factorMatrix.target_date || "");
  const summary = factorMatrix.candidates_summary || {};
  const count = summary.candidate_count ?? PLACEHOLDER;
  const ge80 = summary.ge_80_count ?? PLACEHOLDER;
  const ge70 = summary.ge_70_count ?? PLACEHOLDER;
  const ge60 = summary.ge_60_count ?? PLACEHOLDER;
  summaryRoot.textContent = `日期 ${targetDate || PLACEHOLDER} · 候选 ${count} · >=80 ${ge80} · >=70 ${ge70} · >=60 ${ge60}`;

  const tiers = factorMatrix.tiers || {};
  const groups = [
    { key: "ge_80", label: ">=80" },
    { key: "ge_70", label: ">=70" },
    { key: "ge_60", label: ">=60" },
  ];

  const rows = [];
  for (const group of groups) {
    const items = Array.isArray(tiers[group.key]) ? tiers[group.key] : [];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      rows.push({
        tier: group.label,
        certainty: Number(item.certainty ?? 0),
        stock_code: String(item.stock_code || ""),
        stock_name: String(item.stock_name || ""),
        sector_lv1: String(item.sector_lv1 || "-"),
        subscores: item.subscores || {},
        hit_count: extractHitCount(item),
      });
    }
  }
  rows.sort((a, b) => b.certainty - a.certainty);

  clearElement(tableRoot);
  if (rows.length === 0) {
    tableRoot.textContent = "暂无候选（或当日量化矩阵尚未生成）。";
    return;
  }

  const controls = document.createElement("div");
  controls.className = "table-actions";
  controls.style.marginBottom = "10px";
  const download = document.createElement("a");
  download.className = "btn secondary";
  download.textContent = "下载候选 CSV";
  const dateKey = targetDate || effectiveDate;
  download.href = buildApiUrl(
    `/api/factor-matrix/daily/${encodeURIComponent(dateKey)}/download`
  );
  controls.appendChild(download);
  tableRoot.appendChild(controls);

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>档位</th>" +
    "<th>置信度</th>" +
    "<th>股票</th>" +
    "<th>板块</th>" +
    "<th>技术/情绪</th>" +
    "<th>筛选器命中</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows.slice(0, 50)) {
    const tr = document.createElement("tr");
    const tdTier = document.createElement("td");
    tdTier.textContent = row.tier;
    const tdCert = document.createElement("td");
    tdCert.textContent = row.certainty.toFixed(2);
    const tdStock = document.createElement("td");
    tdStock.textContent = `${row.stock_name}（${row.stock_code}）`;
    const tdSector = document.createElement("td");
    tdSector.textContent = row.sector_lv1;
    const tdScores = document.createElement("td");
    const tech = Number(row.subscores.technical ?? 0).toFixed(1);
    const sent = Number(row.subscores.sentiment ?? 0).toFixed(1);
    tdScores.textContent = `${tech}/${sent}`;
    const tdHits = document.createElement("td");
    tdHits.textContent = row.hit_count == null ? "-" : String(row.hit_count);

    tr.appendChild(tdTier);
    tr.appendChild(tdCert);
    tr.appendChild(tdStock);
    tr.appendChild(tdSector);
    tr.appendChild(tdScores);
    tr.appendChild(tdHits);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tableRoot.appendChild(table);
}

function renderCandidatesMatrix(factorMatrix) {
  const tableRoot = document.getElementById("candidates-qm-table");
  const summaryRoot = document.getElementById("candidates-meta");
  if (!tableRoot || !summaryRoot) return;

  if (!factorMatrix || typeof factorMatrix !== "object") {
    summaryRoot.textContent = "量化矩阵尚未加载。";
    tableRoot.textContent = "量化矩阵尚未加载。";
    return;
  }

  const targetDate = String(factorMatrix.target_date || "");
  const summary = factorMatrix.candidates_summary || {};
  const count = summary.candidate_count ?? PLACEHOLDER;
  const ge80 = summary.ge_80_count ?? PLACEHOLDER;
  const ge70 = summary.ge_70_count ?? PLACEHOLDER;
  const ge60 = summary.ge_60_count ?? PLACEHOLDER;
  summaryRoot.textContent = `日期 ${targetDate || PLACEHOLDER} · 候选 ${count} · >=80 ${ge80} · >=70 ${ge70} · >=60 ${ge60}`;

  const tiers = factorMatrix.tiers || {};
  const groups = [
    { key: "ge_80", label: ">=80" },
    { key: "ge_70", label: ">=70" },
    { key: "ge_60", label: ">=60" },
  ];

  const rows = [];
  for (const group of groups) {
    const items = Array.isArray(tiers[group.key]) ? tiers[group.key] : [];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      rows.push({
        tier: group.label,
        certainty: Number(item.certainty ?? 0),
        stock_code: String(item.stock_code || ""),
        stock_name: String(item.stock_name || ""),
        sector_lv1: String(item.sector_lv1 || "-"),
        subscores: item.subscores || {},
        hit_count: extractHitCount(item),
      });
    }
  }
  rows.sort((a, b) => b.certainty - a.certainty);

  clearElement(tableRoot);
  if (rows.length === 0) {
    tableRoot.textContent = "暂无候选（或当日量化矩阵尚未生成）。";
    return;
  }

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>档位</th>" +
    "<th>置信度</th>" +
    "<th>股票</th>" +
    "<th>板块</th>" +
    "<th>技术/情绪</th>" +
    "<th>筛选器命中</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const limit = 80;
  for (const row of rows.slice(0, limit)) {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => {
      const input = document.getElementById("stock-check-code");
      const btn = document.getElementById("stock-check-run");
      if (input) input.value = row.stock_code;
      window.location.hash = "#section-stock";
      if (btn) btn.click();
    });

    const tdTier = document.createElement("td");
    tdTier.textContent = row.tier;
    const tdCert = document.createElement("td");
    tdCert.textContent = row.certainty.toFixed(2);
    const tdStock = document.createElement("td");
    tdStock.textContent = `${row.stock_name}（${row.stock_code}）`;
    const tdSector = document.createElement("td");
    tdSector.textContent = row.sector_lv1;
    const tdScores = document.createElement("td");
    const tech = Number(row.subscores.technical ?? 0).toFixed(1);
    const sent = Number(row.subscores.sentiment ?? 0).toFixed(1);
    tdScores.textContent = `${tech}/${sent}`;
    const tdHits = document.createElement("td");
    tdHits.textContent = row.hit_count == null ? "-" : String(row.hit_count);

    tr.appendChild(tdTier);
    tr.appendChild(tdCert);
    tr.appendChild(tdStock);
    tr.appendChild(tdSector);
    tr.appendChild(tdScores);
    tr.appendChild(tdHits);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tableRoot.appendChild(table);
}

function renderDailyWorkbench(ctx) {
  const statusEl = document.getElementById("workbench-status");
  const errorEl = document.getElementById("workbench-error");
  const rawEl = document.getElementById("workbench-raw");
  if (!statusEl || !errorEl) return;

  errorEl.hidden = true;

  const calendar = tradingCalendarMeta;
  const maxTradingDay =
    calendar && calendar.max_trading_day ? String(calendar.max_trading_day) : null;
  const minTradingDay =
    calendar && calendar.min_trading_day ? String(calendar.min_trading_day) : null;
  const workbenchDate = computeWorkbenchDate();

  const pinnedHint =
    maxTradingDay && String(effectiveDate) > String(maxTradingDay)
      ? `（已自动切换到最新交易日）`
      : "";
  const ready = isDataReady();
  const readyText = ready ? "就绪（可以跑）" : "未就绪（先更新数据）";
  statusEl.textContent = `当前日期 ${effectiveDate} · 数据状态 ${readyText} · 交易日历 ${minTradingDay || "?"}~${maxTradingDay || "?"} · 执行日期 ${workbenchDate}${pinnedHint}`;

  if (rawEl) {
    rawEl.textContent = formatJson({
      effectiveDate,
      workbenchDate,
      tradingCalendarMeta,
      sourceMode,
      dataReady: ready,
      dataControlStageSummary,
      screeners: ctx && ctx.screeners ? ctx.screeners._meta || "ok" : null,
      factorMatrix: ctx && ctx.factorMatrix ? ctx.factorMatrix._meta || "ok" : null,
      pools: ctx && ctx.pools ? ctx.pools._meta || "ok" : null,
    });
  }

  renderWorkbenchCandidates(ctx ? ctx.factorMatrix : null);
}

function summarizeFactorMatrix(payload) {
  const meta = payload && payload._meta ? payload._meta : {};
  const status = meta.status || "未知";
  const source = formatSourceMode(meta.source || "live");
  const marketContext = payload && payload.market_context ? payload.market_context : {};
  const mp = marketContext.market_phase;
  const marketPhase =
    mp && typeof mp === "object" && mp.display ? String(mp.display) : "未知";
  const focusThemes = Array.isArray(marketContext.focus_themes)
    ? marketContext.focus_themes
    : [];
  const themesPreview =
    focusThemes.length > 0 ? focusThemes.slice(0, 5).join("、") : "无";
  return `状态 ${formatRunStatus(status)} · 来源 ${source} · 市场阶段 ${marketPhase} · 聚焦板块 ${themesPreview}`;
}

function renderFactorMatrixBox(payload) {
  const box = document.getElementById("factor-matrix-box");
  clearElement(box);

  const heading = document.createElement("h4");
  heading.textContent = "候选与评分（量化矩阵）";
  box.appendChild(heading);

  const line = document.createElement("div");
  line.className = "summary-line";
  line.textContent = summarizeFactorMatrix(payload);
  box.appendChild(line);

  const tiers = payload && payload.tiers && typeof payload.tiers === "object" ? payload.tiers : {};
  const groups = [
    { key: "ge_80", label: ">=80" },
    { key: "ge_70", label: ">=70" },
    { key: "ge_60", label: ">=60" },
  ];
  const rows = [];
  for (const group of groups) {
    const items = Array.isArray(tiers[group.key]) ? tiers[group.key] : [];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const code = String(item.stock_code || "").trim();
      if (!code) continue;
      const name = String(item.stock_name || "").trim() || code;
      const subscores = item.subscores && typeof item.subscores === "object" ? item.subscores : {};
      const score = Number(subscores.overall ?? item.certainty ?? 0);
      const certainty = Number(item.certainty ?? score);
      const evidence = item.evidence && typeof item.evidence === "object" ? item.evidence : {};
      const hitCount = extractHitCount(item);
      const evidenceLines = pickEvidenceLines(
        filterUserEvidence(evidence.technical_evidence),
        2
      ).join("；");
      const check = buildCandidateCheckLine({
        tier_label: group.label,
        score,
        certainty,
        hit_count: hitCount,
        evidence: evidenceLines,
      });
      rows.push({
        tier: group.label,
        stock_code: code,
        stock_name: name,
        score,
        certainty,
        check,
      });
    }
  }
  rows.sort((a, b) => b.certainty - a.certainty);

  if (rows.length > 0) {
    const table = document.createElement("table");
    table.className = "table";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr>" +
      "<th>档位</th>" +
      "<th>代码</th>" +
      "<th>名称</th>" +
      "<th>评分</th>" +
      "<th>确定性</th>" +
      "<th>CHECK（一句话）</th>" +
      "</tr>";
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const row of rows.slice(0, 50)) {
      const tr = document.createElement("tr");
      const tdTier = document.createElement("td");
      tdTier.textContent = row.tier;
      const tdCode = document.createElement("td");
      tdCode.textContent = row.stock_code;
      const tdName = document.createElement("td");
      tdName.textContent = row.stock_name;
      const tdScore = document.createElement("td");
      tdScore.textContent =
        row.score == null ? "-" : Number(row.score).toFixed(2);
      const tdCert = document.createElement("td");
      tdCert.textContent =
        row.certainty == null ? "-" : Number(row.certainty).toFixed(2);
      const tdReason = document.createElement("td");
      tdReason.textContent = row.check || "-";
      tr.appendChild(tdTier);
      tr.appendChild(tdCode);
      tr.appendChild(tdName);
      tr.appendChild(tdScore);
      tr.appendChild(tdCert);
      tr.appendChild(tdReason);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    table.style.marginTop = "12px";
    box.appendChild(table);
  } else {
    const empty = document.createElement("div");
    empty.style.marginTop = "12px";
    empty.textContent = "暂无候选（或量化矩阵尚未生成）。";
    box.appendChild(empty);
  }

  const actions = document.createElement("div");
  actions.className = "controls";
  actions.style.marginTop = "10px";

  const runButton = document.createElement("button");
  runButton.className = "btn";
  runButton.textContent = "运行并落盘";
  runButton.disabled = !isDataReady();
  runButton.addEventListener("click", async () => {
    if (!isDataReady()) {
      setText("factor-matrix", explainNotReady());
      return;
    }
    runButton.disabled = true;
    try {
      await postJson("/api/factor-matrix/daily/run", {
        date: effectiveDate,
        requested_by: "dashboard",
        dry_run: false,
        debug: false,
      });
      const refreshed = await fetchJson("/api/factor-matrix/daily");
      setText("factor-matrix-meta", formatMeta(refreshed));
      setText("factor-matrix", formatJson(refreshed));
      renderFactorMatrixBox(refreshed);
    } catch (error) {
      setText("factor-matrix", `执行失败：${formatErrorMessage(error)}`);
    } finally {
      runButton.disabled = !isDataReady();
    }
  });

  const download = document.createElement("a");
  download.className = "btn secondary";
  download.textContent = "下载 JSON";
  download.href = buildApiUrl(
    `/api/factor-matrix/daily/${encodeURIComponent(effectiveDate)}/download`
  );

  actions.appendChild(runButton);
  actions.appendChild(download);
  box.appendChild(actions);
}

function renderPoolsBox(payload) {
  const box = document.getElementById("pools-box");
  clearElement(box);

  const heading = document.createElement("h4");
  heading.textContent = "各池列表";
  box.appendChild(heading);

  const manualBox = document.createElement("div");
  manualBox.className = "section-box";

  const manualTitle = document.createElement("h4");
  manualTitle.textContent = "手工监控池（保存为当日快照）";
  manualBox.appendChild(manualTitle);

  const row1 = document.createElement("div");
  row1.className = "form-row";

  const poolIdInput = document.createElement("input");
  poolIdInput.className = "form-input";
  poolIdInput.placeholder = "池 ID（例如：watch_A）";

  const displayNameInput = document.createElement("input");
  displayNameInput.className = "form-input";
  displayNameInput.placeholder = "显示名（可选）";

  row1.appendChild(poolIdInput);
  row1.appendChild(displayNameInput);
  manualBox.appendChild(row1);

  const membersInput = document.createElement("textarea");
  membersInput.className = "form-textarea";
  membersInput.placeholder = "成员代码（换行或逗号分隔）\n例如：\n000001\n600519";
  membersInput.rows = 5;
  manualBox.appendChild(membersInput);

  function extractStockCodes(text) {
    const raw = String(text || "");
    const hits = raw.match(/\b\d{6}\b/g) || [];
    return Array.from(new Set(hits.map((v) => v.trim()).filter((v) => v))).sort();
  }

  const fileRow = document.createElement("div");
  fileRow.className = "form-row";

  const fileInput = document.createElement("input");
  fileInput.className = "form-input";
  fileInput.type = "file";
  fileInput.accept = ".csv,.txt,.text";
  fileRow.appendChild(fileInput);

  const fileHint = document.createElement("div");
  fileHint.className = "form-hint";
  fileHint.textContent = "支持 CSV/TXT。会自动提取 6 位股票代码。";
  fileRow.appendChild(fileHint);

  manualBox.appendChild(fileRow);

  fileInput.addEventListener("change", async () => {
    const files = fileInput.files ? Array.from(fileInput.files) : [];
    const first = files[0] || null;
    if (!first) return;
    try {
      const text = await first.text();
      const codes = extractStockCodes(text);
      membersInput.value = codes.join("\n");
    } catch (error) {
      setText("pool-detail", `读取文件失败：${String(error && error.message ? error.message : error)}`);
    }
  });

  const row2 = document.createElement("div");
  row2.className = "form-row";

  const saveButton = document.createElement("button");
  saveButton.className = "btn";
  saveButton.textContent = "保存当日快照";

  const hint = document.createElement("div");
  hint.className = "form-hint";
  hint.textContent = "需要 API Key 才能保存。";

  saveButton.addEventListener("click", async () => {
    const rawPoolId = String(poolIdInput.value || "").trim();
    const rawDisplayName = String(displayNameInput.value || "").trim();
    const rawMembers = String(membersInput.value || "");
    const members = extractStockCodes(rawMembers);

    if (!rawPoolId) {
      setText("pool-detail", "请先填写池 ID。");
      return;
    }
    if (members.length === 0) {
      setText("pool-detail", "请先填写成员代码。");
      return;
    }
    if (!window.confirm(`确认保存当日快照？\n日期：${effectiveDate}\n池：${rawPoolId}\n成员数：${members.length}`)) {
      return;
    }

    saveButton.disabled = true;
    setText("pool-detail", TEXT_SAVING);
    try {
      const result = await postJson("/api/pools/manual/snapshot", {
        date: effectiveDate,
        pool_id: rawPoolId,
        display_name: rawDisplayName || null,
        members,
        requested_by: "dashboard",
        dry_run: false,
      });
      setText("pool-detail", formatJson(result));
      const refreshed = await fetchJson("/api/pools");
      setText("pools-meta", formatMeta(refreshed));
      setText("pools", formatJson(refreshed));
      renderPoolsBox(refreshed);
    } catch (error) {
      setText("pool-detail", `保存失败：${formatErrorMessage(error)}`);
    } finally {
      saveButton.disabled = false;
    }
  });

  row2.appendChild(saveButton);
  row2.appendChild(hint);
  manualBox.appendChild(row2);
  box.appendChild(manualBox);

  const pools = Array.isArray(payload.pools) ? payload.pools : [];
  if (pools.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "暂无池。";
    box.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>池</th>" +
    "<th>成员数</th>" +
    "<th>新增</th>" +
    "<th>移除</th>" +
    "<th>操作</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const item of pools) {
    const poolId = String(item.pool_id || "");
    const displayName = String(item.display_name || poolId);
    const memberCount = item.member_count ?? "未知";
    const addedCount = item.added_count ?? "未知";
    const removedCount = item.removed_count ?? "未知";

    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = `${displayName}（${poolId}）`;

    const countTd = document.createElement("td");
    countTd.textContent = String(memberCount);

    const addedTd = document.createElement("td");
    addedTd.textContent = String(addedCount);

    const removedTd = document.createElement("td");
    removedTd.textContent = String(removedCount);

    const actionTd = document.createElement("td");
    const actionGroup = document.createElement("div");
    actionGroup.className = "table-actions";
    actionTd.appendChild(actionGroup);

    const viewButton = document.createElement("button");
    viewButton.className = "btn secondary";
    viewButton.textContent = "查看";
    viewButton.addEventListener("click", async (event) => {
      event.preventDefault();
      setText("pool-detail", TEXT_LOADING);
      const membersMeta = document.getElementById("pool-members-meta");
      const membersTable = document.getElementById("pool-members-table");
      if (membersMeta) membersMeta.textContent = TEXT_LOADING;
      if (membersTable) membersTable.textContent = TEXT_LOADING;
      try {
        const detail = await fetchJson(`/api/pools/${encodeURIComponent(poolId)}`);
        setText("pool-detail", formatJson(detail));
        await renderPoolMembers(detail);
      } catch (error) {
        setText("pool-detail", `加载失败：${formatErrorMessage(error)}`);
        if (membersMeta) membersMeta.textContent = `加载失败：${formatErrorMessage(error)}`;
        if (membersTable) membersTable.textContent = `加载失败：${formatErrorMessage(error)}`;
      }
    });

    const download = document.createElement("a");
    download.className = "btn secondary";
    download.textContent = "下载 CSV";
    download.href = buildApiUrl(
      `/api/pools/${encodeURIComponent(poolId)}/download.csv`
    );

    actionGroup.appendChild(viewButton);
    actionGroup.appendChild(download);

    tr.appendChild(nameTd);
    tr.appendChild(countTd);
    tr.appendChild(addedTd);
    tr.appendChild(removedTd);
    tr.appendChild(actionTd);
    tbody.appendChild(tr);
  }

  table.appendChild(tbody);
  box.appendChild(table);
}

async function renderPoolMembers(detailPayload) {
  const metaEl = document.getElementById("pool-members-meta");
  const tableEl = document.getElementById("pool-members-table");
  if (!metaEl || !tableEl) return;

  if (!detailPayload || typeof detailPayload !== "object") {
    metaEl.textContent = "尚未选择";
    tableEl.textContent = "尚未选择";
    return;
  }
  const pool = detailPayload.pool || {};
  const poolId = String(pool.pool_id || "");
  const displayName = String(pool.display_name || poolId);
  const memberCount = pool.member_count ?? "未知";
  const added = Array.isArray(pool.added) ? pool.added : [];
  const removed = Array.isArray(pool.removed) ? pool.removed : [];
  const members = Array.isArray(pool.members) ? pool.members : [];

  metaEl.textContent = `${displayName}（${poolId}） · 成员 ${memberCount} · 新增 ${added.length} · 移除 ${removed.length}`;

  clearElement(tableEl);
  if (members.length === 0) {
    tableEl.textContent = "该池当日暂无成员。";
    return;
  }

  let rows = [];
  try {
    rows = await enrichStockRows(members);
  } catch (error) {
    rows = members.map((code) => ({
      stock_code: String(code || "").trim(),
      stock_name: String(code || "").trim(),
      score: null,
      certainty: null,
    }));
  }

  const actions = document.createElement("div");
  actions.className = "table-actions";
  actions.style.marginBottom = "10px";

  const download = document.createElement("a");
  download.className = "btn secondary";
  download.textContent = "下载 CSV";
  download.href = buildApiUrl(`/api/pools/${encodeURIComponent(poolId)}/download.csv`);
  actions.appendChild(download);

  if (added.length > 0 || removed.length > 0) {
    const diff = document.createElement("div");
    diff.className = "control-meta";
    diff.style.marginTop = "8px";
    const addedPreview = added.slice(0, 20).join("、");
    const removedPreview = removed.slice(0, 20).join("、");
    const addedLine = added.length > 0 ? `新增：${addedPreview}${added.length > 20 ? "…" : ""}` : "";
    const removedLine = removed.length > 0 ? `移除：${removedPreview}${removed.length > 20 ? "…" : ""}` : "";
    diff.textContent = [addedLine, removedLine].filter((x) => x).join(" | ");
    actions.appendChild(diff);
  }

  tableEl.appendChild(actions);

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr>" +
    "<th>#</th>" +
    "<th>代码</th>" +
    "<th>名称</th>" +
    "<th>评分</th>" +
    "<th>确定性</th>" +
    "<th>CHECK（一句话）</th>" +
    "<th>操作</th>" +
    "</tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i] || {};
    const code = String(row.stock_code || "");
    const tr = document.createElement("tr");

    const tdRank = document.createElement("td");
    tdRank.textContent = String(i + 1);
    const tdCode = document.createElement("td");
    tdCode.textContent = code;
    const tdName = document.createElement("td");
    tdName.textContent = String(row.stock_name || code);
    const tdScore = document.createElement("td");
    tdScore.textContent =
      row.score == null || Number.isNaN(Number(row.score))
        ? "-"
        : Number(row.score).toFixed(2);
    const tdCert = document.createElement("td");
    tdCert.textContent =
      row.certainty == null || Number.isNaN(Number(row.certainty))
        ? "-"
        : Number(row.certainty).toFixed(2);
    const tdCheck = document.createElement("td");
    const tierLabel = row.tier_label ? String(row.tier_label) : "候选";
    if (row.score == null || row.certainty == null) {
      tdCheck.textContent = `未入选候选 · 评分 ${PLACEHOLDER} · 确定性 ${PLACEHOLDER}`;
    } else {
      tdCheck.textContent = buildCandidateCheckLine({
        tier_label: tierLabel,
        score: row.score,
        certainty: row.certainty,
        hit_count: null,
        evidence: "",
      });
    }
    const tdAction = document.createElement("td");

    const checkBtn = document.createElement("button");
    checkBtn.className = "btn secondary";
    checkBtn.textContent = "检查";
    checkBtn.addEventListener("click", (event) => {
      event.preventDefault();
      const input = document.getElementById("stock-check-code");
      const run = document.getElementById("stock-check-run");
      if (input) input.value = code;
      if (run) run.click();
      window.location.hash = "#section-screeners";
    });
    const actionGroup = document.createElement("div");
    actionGroup.className = "table-actions";
    actionGroup.appendChild(checkBtn);
    tdAction.appendChild(actionGroup);

    tr.appendChild(tdRank);
    tr.appendChild(tdCode);
    tr.appendChild(tdName);
    tr.appendChild(tdScore);
    tr.appendChild(tdCert);
    tr.appendChild(tdCheck);
    tr.appendChild(tdAction);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tableEl.appendChild(table);
}

async function renderLabSection(opts) {
  const labsPayload = opts && opts.labsPayload ? opts.labsPayload : null;
  const labId = String(opts.labId || "");
  const metaId = String(opts.metaId || "");
  const boxId = String(opts.boxId || "");
  const rawId = String(opts.rawId || "");

  const metaEl = document.getElementById(metaId);
  const boxEl = document.getElementById(boxId);
  const rawEl = document.getElementById(rawId);
  if (!metaEl || !boxEl) return;

  const labs = labsPayload && Array.isArray(labsPayload.labs) ? labsPayload.labs : [];
  const lab = labs.find((item) => item && String(item.lab_id || "") === labId) || null;
  const displayName = lab && lab.display_name ? String(lab.display_name) : labId;
  const enabled = lab ? Boolean(lab.enabled) : false;

  metaEl.textContent = `${displayName} · 状态 ${enabled ? "启用" : "禁用"}`;
  clearElement(boxEl);

  const actions = document.createElement("div");
  actions.className = "controls";
  actions.style.marginTop = "10px";

  const runButton = document.createElement("button");
  runButton.className = "btn";
  runButton.textContent = "运行（当日）";
  runButton.disabled = !enabled || !isDataReady();

  const download = document.createElement("a");
  download.className = "btn secondary";
  download.textContent = "下载 JSON";
  download.href = buildApiUrl(
    `/api/labs/runs/${encodeURIComponent(effectiveDate)}/${encodeURIComponent(
      labId
    )}/download`
  );
  actions.appendChild(runButton);
  actions.appendChild(download);
  boxEl.appendChild(actions);

  const statusLine = document.createElement("div");
  statusLine.className = "section-meta";
  statusLine.style.marginTop = "10px";
  boxEl.appendChild(statusLine);

  const content = document.createElement("div");
  content.style.marginTop = "10px";
  boxEl.appendChild(content);

  async function refresh() {
    statusLine.textContent = "加载当日结果中...";
    clearElement(content);
    try {
      const detail = await fetchJson(
        `/api/labs/runs/${encodeURIComponent(effectiveDate)}/${encodeURIComponent(
          labId
        )}`
      );
      if (rawEl) rawEl.textContent = formatJson(detail);
      const result = detail && detail.lab_result ? detail.lab_result : {};
      const artifacts = result && result.artifacts ? result.artifacts : {};
      statusLine.textContent = "当日已运行。";

      if (labId === "cup_handle_lab") {
        const report = artifacts.cup_handle_daily_report || {};
        const candidates = Array.isArray(report.candidates) ? report.candidates : [];
        const msg = String(report.message || "");
        const headline = document.createElement("div");
        headline.textContent = `候选=${candidates.length}${msg ? ` | ${msg}` : ""}`;
        content.appendChild(headline);

        if (candidates.length > 0) {
          const list = document.createElement("div");
          list.className = "section-box";
          list.style.marginTop = "10px";
          list.textContent = candidates.join("、");
          content.appendChild(list);
        }
      } else if (labId === "five_flags_lab") {
        const scan = artifacts.five_flags_scan_results || {};
        const pool = Array.isArray(scan.pool) ? scan.pool : [];
        const msg = String(scan.message || "");
        const headline = document.createElement("div");
        headline.textContent = `输入池=${pool.length}${msg ? ` | ${msg}` : ""}`;
        content.appendChild(headline);
        if (pool.length > 0) {
          const list = document.createElement("div");
          list.className = "section-box";
          list.style.marginTop = "10px";
          list.textContent = pool.slice(0, 200).join("、") + (pool.length > 200 ? "…" : "");
          content.appendChild(list);
        }
      } else {
        content.textContent = "该实验室展示尚未定制。";
      }
    } catch (error) {
      if (rawEl) rawEl.textContent = `加载失败：${formatErrorMessage(error)}`;
      const apiError = error && error.payload && error.payload.error ? error.payload.error : null;
      if (apiError && apiError.code === "lab_run_not_found") {
        statusLine.textContent = "当日尚未运行。";
      } else {
        statusLine.textContent = `加载失败：${formatErrorMessage(error)}`;
      }
      content.textContent = "";
    } finally {
      runButton.disabled = !enabled || !isDataReady();
    }
  }

  runButton.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!isDataReady()) {
      statusLine.textContent = explainNotReady();
      return;
    }
    runButton.disabled = true;
    statusLine.textContent = "运行中...";
    try {
      await postJson("/api/labs/run", {
        date: effectiveDate,
        lab_id: labId,
        requested_by: "dashboard",
        dry_run: false,
      });
      await refresh();
    } catch (error) {
      statusLine.textContent = `运行失败：${formatErrorMessage(error)}`;
    } finally {
      runButton.disabled = !enabled || !isDataReady();
    }
  });

  await refresh();
}

function buildRoadmapPayload() {
  return {
    v1: {
      title: "NeoTrade3 v1（最小可运行中枢）",
      must_have: [
        "数据主链：source registry + capture/compose/publish + 质量闸门",
        "每日总编排：单一 orchestrator 入口 + 统一台账",
        "实验室统一注册：杯柄 / 模拟交易 / 老鸭头五图 / 量化交易",
        "问题池：运行结果聚合为 issue cases/events",
        "学习闭环：指标评估 + 调整候选 + 审计记录",
        "新 Dashboard：按全链路运营视角展示状态与阻塞点",
      ],
      non_goals: [
        "不一次性迁移全部旧脚本",
        "不把 NeoTrade2 旧 UI 直接照搬",
        "不做黑箱自动改参直接上线",
        "BaoStock 暂不进入同日例行编排",
      ],
    },
    current_focus: [
      "把迁移台账接入控制台，并按域拆解推进",
      "把“阻塞任务/问题池”做成一眼可读的行动清单",
      "把实验室与筛选器的真实运行证据链固定（artifact/ledger）",
    ],
  };
}

function renderRoadmapBox() {
  const payload = buildRoadmapPayload();
  setText("roadmap", formatJson(payload));
  const items = [
    `v1 必做：${payload.v1.must_have.length} 项`,
    `v1 非目标：${payload.v1.non_goals.length} 项`,
    `当前焦点：${payload.current_focus.join("；")}`,
  ];
  renderListBox("roadmap-box", payload.v1.title, items);
}

function renderNextActions(orchestrationPayload, issuePayload, learningPayload) {
  const orchestration = orchestrationPayload.orchestration || {};
  const plan = orchestration.plan || {};
  const plannedTasks = Array.isArray(plan.planned_tasks) ? plan.planned_tasks : [];
  const plannedIndex = Object.fromEntries(
    plannedTasks.map((task) => [task.task_id, task])
  );
  const taskResults = Array.isArray(orchestration.task_results)
    ? orchestration.task_results
    : [];
  const blocked = taskResults.filter((result) => result.status === "blocked");
  const issueCenter = issuePayload.issue_center || {};
  const issueCases = Array.isArray(issueCenter.cases) ? issueCenter.cases : [];
  const learning = learningPayload.learning || {};
  const candidates = Array.isArray(learning.adjustment_candidates)
    ? learning.adjustment_candidates
    : [];
  const reviewRequired = candidates.filter(
    (candidate) => candidate.decision === "review_required"
  );

  const items = [];
  if (blocked.length > 0) {
    items.push(`当前阻塞：${blocked.length} 个（优先处理第一项）`);
    const first = blocked[0];
    const planned = plannedIndex[first.task_id] || null;
    const label = formatTaskLabel(first.task_id, planned);
    const reason = formatTaskBlockReason(planned);
    items.push(`下一步：解除 ${label}${reason ? `（${reason}）` : ""}`);
  } else {
    items.push("当前无阻塞任务。");
  }

  if (issueCases.length > 0) {
    items.push(`问题池：${issueCases.length} 个案例（优先处理高严重度）`);
  } else {
    items.push("问题池：暂无案例。");
  }

  if (reviewRequired.length > 0) {
    items.push(`学习候选：${reviewRequired.length} 个需复核。`);
  } else {
    items.push("学习候选：暂无需复核项。");
  }

  renderListBox("next-actions", "下一步行动清单", items);
}

function formatCoverageLine(domainLabel, coverage) {
  const scope = (coverage && coverage.scope) || {};
  const status = coverage && coverage.status ? coverage.status : "unknown";
  const inventoryCount = coverage && typeof coverage.inventory_count === "number"
    ? coverage.inventory_count
    : PLACEHOLDER;
  const mappedCount = coverage && typeof coverage.mapped_count === "number"
    ? coverage.mapped_count
    : PLACEHOLDER;
  const missingCount = coverage && typeof coverage.missing_count === "number"
    ? coverage.missing_count
    : PLACEHOLDER;
  const extraCount = coverage && typeof coverage.extra_count === "number"
    ? coverage.extra_count
    : PLACEHOLDER;
  const scopeDomain = scope && scope.domain ? scope.domain : "";
  return `${domainLabel}${scopeDomain ? `（${scopeDomain}）` : ""}：状态 ${formatRunStatus(status)} · 清单 ${inventoryCount} · 已映射 ${mappedCount} · 缺失 ${missingCount} · 额外 ${extraCount}`;
}

function renderMigrationCoverage(coverageByDomain) {
  const items = [
    formatCoverageLine("策略与实验室", coverageByDomain.strategy_and_lab),
    formatCoverageLine("助手", coverageByDomain.assistant),
    formatCoverageLine("运维", coverageByDomain.operations),
    formatCoverageLine("筛选器", coverageByDomain.screeners),
  ];
  renderListBox("migration-coverage", "迁移覆盖率（清单 vs 映射）", items);
}

function renderMigrationFocus(mappingPayload) {
  const payload = mappingPayload.feature_mapping || {};
  const statusCounts = payload.status_counts_total || {};
  const total = payload.mapping_count_total ?? PLACEHOLDER;
  const implemented = statusCounts.implemented ?? 0;
  const scaffolded = statusCounts.scaffolded ?? 0;
  const planned = statusCounts.planned ?? 0;
  const deferred = statusCounts.deferred ?? 0;

  const items = [
    `筛选器台账：总计 ${total} · 已实现 ${implemented} · 已搭架 ${scaffolded} · 计划中 ${planned} · 延后 ${deferred}`,
  ];

  const candidates = Array.isArray(payload.mappings) ? payload.mappings : [];
  const topPlanned = candidates
    .filter((item) => item.migration_status === "planned")
    .slice(0, 8)
    .map((item) => `${item.feature_id}：${item.feature_name || "未命名"}`);
  if (topPlanned.length > 0) {
    items.push(`待迁移优先队列（Top 8）：${topPlanned.join("；")}`);
  }

  renderListBox("migration-focus", "迁移焦点（筛选器域）", items);
}

function renderConfigContracts(payload) {
  const meta = payload && payload._meta ? payload._meta : {};
  const report =
    payload && payload.config_contracts ? payload.config_contracts : {};
  const contracts = report && report.contracts ? report.contracts : [];
  const okCount = Array.isArray(contracts)
    ? contracts.filter((item) => item.status === "ok").length
    : 0;
  const failedCount = Array.isArray(contracts)
    ? contracts.filter((item) => item.status === "failed").length
    : 0;
  const items = [
    `契约 ${Array.isArray(contracts) ? contracts.length : 0} · 通过 ${okCount} · 失败 ${failedCount}`,
    `校验 ${formatValidationStatus(meta.validation_status)}`,
  ];
  renderListBox("config-contracts-box", "配置契约状态", items);
  setText("config-contracts", formatJson(payload));
}

function setDomainSection(sectionId, payload, summaryText) {
  setText(`${sectionId}-summary`, summaryText);
  setText(`${sectionId}-meta`, formatMeta(payload));
  setText(sectionId, formatJson(payload));
}

async function fetchJson(path) {
  const response = await fetch(buildApiUrl(path));
  let payload = null;

  try {
    payload = await response.json();
  } catch (error) {
    throw new Error(`non-json response from ${path}: ${error}`);
  }

  if (!response.ok) {
    const apiMessage =
      payload && payload.error
        ? `${payload.error.code}: ${payload.error.message}`
        : `${response.status} ${response.statusText}`;
    const requestError = new Error(apiMessage);
    requestError.payload = payload;
    requestError.status = response.status;
    throw requestError;
  }

  return payload;
}

async function postJson(path, body) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
  };
  if (apiKey && apiKey.trim()) {
    headers["X-API-Key"] = apiKey.trim();
  }
  const response = await fetch(buildApiUrl(path), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    throw new Error(`non-json response from POST ${path}: ${error}`);
  }

  if (!response.ok) {
    const apiMessage =
      payload && payload.error
        ? `${payload.error.code}: ${payload.error.message}`
        : `${response.status} ${response.statusText}`;
    const requestError = new Error(apiMessage);
    requestError.payload = payload;
    requestError.status = response.status;
    throw requestError;
  }

  return payload;
}

async function loadDashboard() {
  const statusElement = document.getElementById("global-status");
  const errorElement = document.getElementById("global-error");

  try {
    if (statusElement) {
      statusElement.textContent = "脚本已加载，正在拉取数据...";
    }
    let factorMatrixPayload = null;
    let poolsPayload = null;

    try {
      tradingCalendarMeta = await fetchJson("/api/trading-calendar/meta");
    } catch (error) {
      tradingCalendarMeta = null;
    }
    const execDate = computeWorkbenchDate();

    const [
      summary,
      dataControl,
      labs,
      orchestration,
      issueCenter,
      learning,
      screeners,
      stockCoverage,
    ] = await Promise.all([
      fetchJson(`/api/bootstrap-summary?date=${encodeURIComponent(execDate)}`),
      fetchJson(`/api/data-control?date=${encodeURIComponent(execDate)}`),
      fetchJson("/api/labs"),
      fetchJson(`/api/orchestration?date=${encodeURIComponent(execDate)}`),
      fetchJson(`/api/issue-center?date=${encodeURIComponent(execDate)}`),
      fetchJson(`/api/learning?date=${encodeURIComponent(execDate)}`),
      fetchJson(`/api/screeners?date=${encodeURIComponent(execDate)}`),
      fetchJson(`/api/stocks/coverage?date=${encodeURIComponent(execDate)}`),
    ]);

    errorElement.hidden = true;
    statusElement.textContent = "各域快照加载完成。";
    setText("overview", formatJson(summary));
    setDomainSection("data-control", dataControl, summarizeDataControl(dataControl));
    setDomainSection("labs", labs, summarizeLabs(labs));
    setDomainSection(
      "orchestration",
      orchestration,
      summarizeOrchestration(orchestration)
    );
    setDomainSection(
      "issue-center",
      issueCenter,
      summarizeIssueCenter(issueCenter)
    );
    setDomainSection("learning", learning, summarizeLearning(learning));
    setDomainSection("screeners", screeners, summarizeScreeners(screeners));

    const dc = dataControl && dataControl.data_control ? dataControl.data_control : {};
    dataControlStageSummary = dc && dc.stage_summary ? dc.stage_summary : null;

    renderDataControlStageSummary(dataControl);
    renderOrchestrationBlocked(orchestration);
    renderIssueCases(issueCenter);
    renderLearningCandidates(learning);
    renderScreenerRuns(screeners);
    renderScreenerRuns(screeners, { boxId: "team-screeners-runs", title: "筛选器运行记录（Top 12）" });
    renderScreenersRunner(screeners);
    renderScreenersRunner(screeners, { runnerId: "team-screeners-runner", showResult: false });
    renderScreenerConfigPanel(screeners);
    await renderLabSection({
      labsPayload: labs,
      labId: "cup_handle_lab",
      metaId: "cup-handle-meta",
      boxId: "cup-handle-box",
      rawId: "cup-handle-raw",
    });
    await renderLabSection({
      labsPayload: labs,
      labId: "five_flags_lab",
      metaId: "five-flags-meta",
      boxId: "five-flags-box",
      rawId: "five-flags-raw",
    });
    renderRoadmapBox();
    setText("screener-result", "尚未选择");

    try {
      const factorMatrix = await fetchJson(
        `/api/factor-matrix/daily?date=${encodeURIComponent(execDate)}`
      );
      factorMatrixPayload = factorMatrix;
      factorMatrixIndex = buildFactorMatrixIndex(factorMatrix);
      setText("factor-matrix-meta", formatMeta(factorMatrix));
      setText("factor-matrix", formatJson(factorMatrix));
      renderFactorMatrixBox(factorMatrix);
      renderCandidatesMatrix(factorMatrix);
    } catch (error) {
      const message = `加载失败：${formatErrorMessage(error)}`;
      setText("factor-matrix-meta", "加载失败");
      setText("factor-matrix", message);
      renderListBox("factor-matrix-box", "当日因子矩阵", [message]);
      setText("candidates-meta", message);
      renderListBox("candidates-qm-table", "当日候选", [message]);
    }

    try {
      const pools = await fetchJson(`/api/pools?date=${encodeURIComponent(execDate)}`);
      poolsPayload = pools;
      setText("pools-meta", formatMeta(pools));
      setText("pools", formatJson(pools));
      renderPoolsBox(pools);
      setText("pool-detail", "尚未选择");
      const membersMeta = document.getElementById("pool-members-meta");
      const membersTable = document.getElementById("pool-members-table");
      if (membersMeta) membersMeta.textContent = "尚未选择";
      if (membersTable) membersTable.textContent = "尚未选择";
    } catch (error) {
      const message = `加载失败：${formatErrorMessage(error)}`;
      setText("pools-meta", "加载失败");
      setText("pools", message);
      setText("pool-detail", message);
      const membersMeta = document.getElementById("pool-members-meta");
      const membersTable = document.getElementById("pool-members-table");
      if (membersMeta) membersMeta.textContent = message;
      if (membersTable) membersTable.textContent = message;
      renderListBox("pools-box", "各池列表", [message]);
    }

    let orchestrationRunsPayload = null;
    try {
      orchestrationRunsPayload = await fetchJson(
        `/api/orchestration/runs?date=${encodeURIComponent(execDate)}&limit=1`
      );
    } catch (error) {
      orchestrationRunsPayload = null;
    }

    // 获取市场阶段、板块轮动数据（用于分析总览卡片）
    let marketPhasePayload = null;
    let sectorRotationPayload = null;
    try { marketPhasePayload = await fetchJson("/api/market-phase"); } catch (e) { /* ignore */ }
    try { sectorRotationPayload = await fetchJson("/api/sector-rotation"); } catch (e) { /* ignore */ }

    try {
      const [reviewBoardPayload, decisionSummaryPayload] = await Promise.all([
        fetchJson("/api/market-intelligence/review-board?top_n=10"),
        fetchJson("/api/market-intelligence/decision-summary?top_n=10"),
      ]);
      renderMarketIntelligenceBoard({
        reviewBoardPayload,
        decisionSummaryPayload,
      });
    } catch (error) {
      const statusEl = document.getElementById("market-intelligence-status");
      const errorEl = document.getElementById("market-intelligence-error");
      const rawEl = document.getElementById("market-intelligence-raw");
      const message = `加载失败：${formatErrorMessage(error)}`;
      if (statusEl) statusEl.textContent = "主线审阅加载失败。";
      if (errorEl) {
        errorEl.hidden = false;
        errorEl.textContent = message;
      }
      if (rawEl) rawEl.textContent = message;
      renderListBox("market-intelligence-themes", "主线赛道", [message]);
      renderListBox("market-intelligence-candidates", "建议层候选", [message]);
      renderListBox("market-intelligence-links", "联动摘要", [message]);
    }

    renderOverviewSummary({
      execDate,
      issuePayload: issueCenter,
      learningPayload: learning,
      factorMatrixPayload: factorMatrixPayload,
      orchestrationRunsPayload,
      poolsPayload,
      stockCoveragePayload: stockCoverage,
      marketPhasePayload,
      sectorRotationPayload,
      screenersPayload: screeners,
    });

    // 渲染全局数据状态栏
    renderDataStatusBar({ summaryPayload: summary, dataControlPayload: dataControl });

    // 渲染热门板块详情
    renderSectorDetail();

    renderDailyWorkbench({
      summary,
      dataControl,
      labs,
      orchestration,
      issueCenter,
      learning,
      screeners,
      factorMatrix: factorMatrixPayload,
      pools: poolsPayload,
    });

    try {
      const configContracts = await fetchJson("/api/config-contracts");
      renderConfigContracts(configContracts);
    } catch (error) {
      const message = `加载失败：${formatErrorMessage(error)}`;
      setText("config-contracts", message);
      renderListBox("config-contracts-box", "配置契约状态", [message]);
    }

    try {
      const [
        coverageStrategyAndLab,
        coverageAssistant,
        coverageOperations,
        coverageScreeners,
        mappingScreeners,
      ] = await Promise.all([
        fetchJson("/api/migration/feature-mapping-coverage?domain=strategy_and_lab"),
        fetchJson("/api/migration/feature-mapping-coverage?domain=assistant"),
        fetchJson("/api/migration/feature-mapping-coverage?domain=operations"),
        fetchJson("/api/migration/feature-mapping-coverage?domain=screeners"),
        fetchJson("/api/migration/feature-mapping?domain=screeners"),
      ]);

      const coverageByDomain = {
        strategy_and_lab: coverageStrategyAndLab.feature_mapping_coverage,
        assistant: coverageAssistant.feature_mapping_coverage,
        operations: coverageOperations.feature_mapping_coverage,
        screeners: coverageScreeners.feature_mapping_coverage,
      };
      setText("migration", formatJson({ coverageByDomain, mappingScreeners }));
      renderMigrationCoverage(coverageByDomain);
      renderMigrationFocus(mappingScreeners);
    } catch (error) {
      const message = `加载失败：${formatErrorMessage(error)}`;
      setText("migration", message);
      renderListBox("migration-coverage", "迁移覆盖率（清单 vs 映射）", [
        message,
      ]);
      renderListBox("migration-focus", "迁移焦点（筛选器域）", [message]);
    }
  } catch (error) {
    const message = `仪表盘加载失败：${formatErrorMessage(error)}`;
    statusElement.textContent = "各域快照加载失败。";
    errorElement.hidden = false;
    errorElement.textContent = message;
    setText("summary-exec-date", "不可用");
    setText("summary-run-ok", "不可用");
    setText("summary-run-failed", "不可用");
    setText("summary-issue-cases", "不可用");
    setText("summary-learning", "不可用");
    setText("summary-pool-ashare", "不可用");
    setText("summary-pool-five-flags", "不可用");
    setText("summary-pool-quant", "不可用");
    setText("summary-pool-triple-turtle", "不可用");
    setText("overview", message);
    setText("data-control-summary", message);
    setText("labs-summary", message);
    setText("orchestration-summary", message);
    setText("issue-center-summary", message);
    setText("learning-summary", message);
    setText("screeners-summary", message);
    setText("data-control-meta", "加载失败");
    setText("labs-meta", "加载失败");
    setText("orchestration-meta", "加载失败");
    setText("issue-center-meta", "加载失败");
    setText("learning-meta", "加载失败");
    setText("screeners-meta", "加载失败");
    setText("data-control", message);
    setText("labs", message);
    setText("orchestration", message);
    setText("issue-center", message);
    setText("learning", message);
    setText("screeners", message);
    setText("roadmap", message);
    setText("migration", message);
    setText("config-contracts", message);
    setText("factor-matrix-meta", "加载失败");
    setText("factor-matrix", message);
    setText("candidates-meta", "加载失败");
    setText("pools-meta", "加载失败");
    setText("pools", message);
    setText("pool-detail", message);
    setText("screener-result", message);

    renderListBox("roadmap-box", "路线图", [message]);
    renderListBox("data-control-stage-summary", "阶段摘要", [message]);
    renderListBox("orchestration-blocked", "阻塞任务", [message]);
    renderListBox("issue-center-cases", "问题案例（Top 10）", [message]);
    renderListBox("learning-candidates", "调整候选（Top 10）", [message]);
    renderListBox("screeners-runs", "最近运行（Top 12）", [message]);
    renderListBox("screeners-runner", "运行面板", [message]);
    renderListBox("factor-matrix-box", "当日因子矩阵", [message]);
    renderListBox("candidates-qm-table", "当日候选", [message]);
    renderListBox("pools-box", "各池列表", [message]);
    renderListBox("migration-coverage", "迁移覆盖率（清单 vs 映射）", [message]);
    renderListBox("migration-focus", "迁移焦点（筛选器域）", [message]);
    renderListBox("config-contracts-box", "配置契约状态", [message]);
  }
}

function initClock() {
  const el = document.getElementById("current-time");
  if (!el) return;
  const tick = () => {
    el.textContent = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };
  tick();
  setInterval(tick, 1000);
}

function initControls() {
  const dateInput = document.getElementById("control-date");
  const apiKeyInput = document.getElementById("control-api-key");
  const apiKeyToggle = document.getElementById("control-api-key-toggle");
  const apiKeyClear = document.getElementById("control-api-key-clear");
  const apiKeyStatus = document.getElementById("control-api-key-status");
  const devCheckbox = document.getElementById("control-dev");
  const refreshButton = document.getElementById("control-refresh");
  const liveLink = document.getElementById("source-live");
  const storedLink = document.getElementById("source-stored");
  const v2DbPathInput = document.getElementById("control-v2-db-path");
  const syncV2Button = document.getElementById("control-sync-v2-daily-prices");
  const managementResult = document.getElementById("management-result");
  const wbSync = document.getElementById("wb-sync");
  const wbJumpLatest = document.getElementById("wb-jump-latest");
  const wbBulkRun = document.getElementById("wb-bulk-run");
  const wbQmRun = document.getElementById("wb-qm-run");
  const wbResult = document.getElementById("workbench-result");
  const wbError = document.getElementById("workbench-error");
  const screenerConfigClose = document.getElementById("screener-config-close");
  const screenerConfigModal = document.getElementById("screener-config-modal");
  const screenerConfigSave = document.getElementById("screener-config-save");
  const screenerConfigReset = document.getElementById("screener-config-reset");
  const screenerConfigJson = document.getElementById("screener-config-json");
  const screenerConfigStatus = document.getElementById("screener-config-status");
  const screenerConfigForm = document.getElementById("screener-config-form");
  const stockCheckCode = document.getElementById("stock-check-code");
  const stockCheckRun = document.getElementById("stock-check-run");
  const stockCheckStatus = document.getElementById("stock-check-status");
  const stockCheckResult = document.getElementById("stock-check-result");
  const stockCheckRaw = document.getElementById("stock-check-raw");
  const overviewRunDaily = document.getElementById("overview-run-daily");
  const overviewRunStatus = document.getElementById("overview-run-status");
  const overviewRunResult = document.getElementById("overview-run-result");

  const fallbackDate = new Date().toISOString().slice(0, 10);
  if (dateInput) {
    dateInput.value = rawTargetDate || fallbackDate;
  }
  if (apiKeyInput) {
    apiKeyInput.value = apiKey;
  }
  if (devCheckbox) {
    devCheckbox.checked = devMode;
  }

  function updateApiKeyStatus() {
    if (!apiKeyStatus) return;
    const value = String(apiKey || "").trim();
    if (!value) {
      apiKeyStatus.textContent = "API Key：未设置";
      return;
    }
    apiKeyStatus.textContent = `API Key：已保存（len=${value.length}，指纹=${fnv1aHex(value)}）`;
  }

  updateApiKeyStatus();
  if (v2DbPathInput) {
    v2DbPathInput.value = v2DbPathInput.value || getV2DbPath();
    v2DbPathInput.addEventListener("input", () => {
      try {
        window.localStorage.setItem(
          "neo_v2_db_path",
          String(v2DbPathInput.value || "")
        );
      } catch (error) {
        return;
      }
    });
  }

  function updateSourceLinks() {
    if (!dateInput) return;
    const dateValue = dateInput.value || fallbackDate;
    const liveParams = new URLSearchParams();
    liveParams.set("source", "live");
    if (theme) liveParams.set("theme", theme);
    if (dateValue !== fallbackDate) {
      liveParams.set("date", dateValue);
    }
    if (devCheckbox && devCheckbox.checked) {
      liveParams.set("dev", "1");
    } else {
      liveParams.delete("dev");
    }
    if (liveLink) {
      liveLink.href = `?${liveParams.toString()}`;
    }

    const storedParams = new URLSearchParams();
    storedParams.set("source", "stored");
    if (theme) storedParams.set("theme", theme);
    if (dateValue !== fallbackDate) {
      storedParams.set("date", dateValue);
    }
    if (devCheckbox && devCheckbox.checked) {
      storedParams.set("dev", "1");
    } else {
      storedParams.delete("dev");
    }
    if (storedLink) {
      storedLink.href = `?${storedParams.toString()}`;
    }
  }

  function rebuildUrl() {
    if (!dateInput) return;
    const params = new URLSearchParams(window.location.search);
    const dateValue = dateInput.value || fallbackDate;
    if (dateValue === fallbackDate) {
      params.delete("date");
    } else {
      params.set("date", dateValue);
    }
    params.set("source", sourceMode);
    if (devCheckbox && devCheckbox.checked) {
      params.set("dev", "1");
    } else {
      params.delete("dev");
    }
    window.location.search = params.toString();
  }

  updateSourceLinks();
  if (refreshButton) {
    refreshButton.addEventListener("click", rebuildUrl);
  }
  if (dateInput) {
    dateInput.addEventListener("change", () => {
      updateSourceLinks();
      rebuildUrl();
    });
  }
  if (devCheckbox) {
    devCheckbox.addEventListener("change", () => {
      updateSourceLinks();
      rebuildUrl();
    });
  }
  if (apiKeyInput) {
    apiKeyInput.addEventListener("input", () => {
      apiKey = String(apiKeyInput.value || "");
      try {
        window.localStorage.setItem("neo_api_key", apiKey);
      } catch (error) {
        return;
      }
      updateApiKeyStatus();
    });
  }

  if (apiKeyToggle && apiKeyInput) {
    apiKeyToggle.addEventListener("click", (event) => {
      event.preventDefault();
      const currentType = String(apiKeyInput.type || "").toLowerCase();
      const nextType = currentType === "password" ? "text" : "password";
      apiKeyInput.type = nextType;
      apiKeyToggle.textContent = nextType === "password" ? "显示" : "隐藏";
    });
  }

  if (apiKeyClear && apiKeyInput) {
    apiKeyClear.addEventListener("click", (event) => {
      event.preventDefault();
      apiKey = "";
      apiKeyInput.value = "";
      try {
        window.localStorage.removeItem("neo_api_key");
      } catch (error) {
        return;
      }
      updateApiKeyStatus();
    });
  }

  if (syncV2Button && v2DbPathInput && managementResult) {
    syncV2Button.addEventListener("click", async (event) => {
      event.preventDefault();
      syncV2Button.disabled = true;
      managementResult.textContent = "同步中...";
      try {
        const payload = await postJson("/api/data-control/sync-daily-prices", {
          source_db_path: String(v2DbPathInput.value || "").trim(),
          requested_by: "dashboard",
          dry_run: false,
          rebuild_trading_calendar: true,
        });
        managementResult.textContent = formatJson(payload);
      } catch (error) {
        managementResult.textContent = `同步失败：${formatErrorMessage(error)}`;
      } finally {
        syncV2Button.disabled = false;
      }
    });
  }

  function summarizeOrchestratorRun(runLedger) {
    if (!runLedger || typeof runLedger !== "object") return "执行完成，但返回结构不可识别。";
    const targetDate = String(runLedger.target_date || "") || PLACEHOLDER;
    const status = String(runLedger.status || "") || PLACEHOLDER;
    const taskCount = runLedger.task_count ?? PLACEHOLDER;
    const publishSucceeded = runLedger.publish_succeeded ? "是" : "否";
    const requestedAt = String(runLedger.requested_at || "") || PLACEHOLDER;
    const statusCounts = runLedger.status_counts && typeof runLedger.status_counts === "object"
      ? runLedger.status_counts
      : {};
    const okCount = statusCounts.ok ?? 0;
    const failedCount = statusCounts.failed ?? 0;
    const blockedCount = statusCounts.blocked ?? 0;
    const skippedCount = statusCounts.skipped ?? 0;
    const pendingCount = statusCounts.pending_implementation ?? 0;
    return [
      `执行日期：${targetDate}`,
      `状态：${status}`,
      `任务数：${taskCount}（通过 ${okCount} / 失败 ${failedCount} / 阻塞 ${blockedCount} / 跳过 ${skippedCount} / 待实现 ${pendingCount}）`,
      `发布闸门：${publishSucceeded}`,
      `触发时间：${requestedAt}`,
    ].join("\n");
  }

  if (overviewRunDaily && overviewRunStatus && overviewRunResult) {
    overviewRunDaily.addEventListener("click", async (event) => {
      event.preventDefault();
      const latestTradingDay = getLatestTradingDay();
      if (!latestTradingDay) {
        overviewRunStatus.textContent = "无法执行：交易日历不可用（trading-calendar/meta 未加载）。";
        return;
      }
      const dateHint =
        latestTradingDay !== String(effectiveDate)
          ? `\n提示：该按钮固定使用本地最新交易日（${latestTradingDay}），与页面日期（${effectiveDate}）无关。`
          : "";
      if (
        !window.confirm(
          `确认运行“今日任务”？\n执行日期：${latestTradingDay}\n模式：真实运行并发布${dateHint}`
        )
      ) {
        return;
      }
      overviewRunDaily.disabled = true;
      overviewRunStatus.textContent = TEXT_RUNNING;
      overviewRunResult.textContent = TEXT_RUNNING;
      try {
        const payload = await postJson("/api/orchestration/run", {
          date: latestTradingDay,
          publish_succeeded: true,
          requested_by: "dashboard",
          dry_run: false,
        });
        const runLedger = payload && payload.orchestrator_run ? payload.orchestrator_run : null;
        overviewRunStatus.textContent = "执行完成。";
        overviewRunResult.textContent = summarizeOrchestratorRun(runLedger);
        await loadDashboard();
      } catch (error) {
        const apiError =
          error && error.payload && error.payload.error ? error.payload.error : null;
        if (apiError && apiError.code === "unauthorized") {
          const message = formatUnauthorizedHint("运行");
          overviewRunStatus.textContent = message;
          overviewRunResult.textContent = message;
        } else if (apiError && apiError.code === "not_trading_day") {
          const message = `执行失败：非交易日（${latestTradingDay}）。`;
          overviewRunStatus.textContent = message;
          overviewRunResult.textContent = message;
        } else {
          const message = `执行失败：${formatErrorMessage(error)}`;
          overviewRunStatus.textContent = message;
          overviewRunResult.textContent = message;
        }
      } finally {
        overviewRunDaily.disabled = false;
      }
    });
  }

  function showWorkbenchError(message) {
    if (!wbError) return;
    wbError.hidden = false;
    wbError.textContent = message;
  }

  function clearWorkbenchError() {
    if (!wbError) return;
    wbError.hidden = true;
    wbError.textContent = PLACEHOLDER;
  }

  if (wbJumpLatest) {
    wbJumpLatest.addEventListener("click", (event) => {
      event.preventDefault();
      const calendar = tradingCalendarMeta;
      const maxTradingDay =
        calendar && calendar.max_trading_day
          ? String(calendar.max_trading_day)
          : null;
      if (!maxTradingDay) {
        showWorkbenchError("无法获取本地最新交易日（trading_calendar/meta 不可用）。");
        return;
      }
      const dateInput = document.getElementById("control-date");
      if (dateInput) {
        dateInput.value = maxTradingDay;
      }
      const refreshButton = document.getElementById("control-refresh");
      if (refreshButton) {
        refreshButton.click();
      }
    });
  }

  if (wbSync && wbResult) {
    wbSync.addEventListener("click", async (event) => {
      event.preventDefault();
      clearWorkbenchError();
      wbSync.disabled = true;
      wbResult.textContent = "同步中...";
      try {
        const payload = await postJson("/api/data-control/sync-daily-prices", {
          source_db_path: getV2DbPath(),
          requested_by: "dashboard_workbench",
          dry_run: false,
          rebuild_trading_calendar: true,
        });
        const summary =
          payload && payload._meta && payload._meta.status === "ok"
            ? "同步完成。"
            : "同步已完成（请刷新查看最新状态）。";
        wbResult.textContent = summary;
        tradingCalendarMeta = await fetchJson("/api/trading-calendar/meta");
        renderDailyWorkbench({ factorMatrix: null, pools: null, screeners: null });
      } catch (error) {
        const apiError =
          error && error.payload && error.payload.error ? error.payload.error : null;
        if (apiError && apiError.code === "unauthorized") {
          showWorkbenchError(
            formatUnauthorizedHint("同步")
          );
        } else {
          showWorkbenchError(`同步失败：${formatErrorMessage(error)}`);
        }
        wbResult.textContent = `同步失败：${formatErrorMessage(error)}`;
      } finally {
        wbSync.disabled = false;
      }
    });
  }

  if (wbBulkRun && wbResult) {
    wbBulkRun.addEventListener("click", async (event) => {
      event.preventDefault();
      clearWorkbenchError();
      const runDate = computeWorkbenchDate();
      if (!window.confirm(`确认批量运行“启用筛选器”？\n日期：${runDate}`)) {
        return;
      }
      if (!isDataReady()) {
        const message = explainNotReady();
        showWorkbenchError(message);
        wbResult.textContent = message;
        return;
      }
      wbBulkRun.disabled = true;
      wbResult.textContent = "批量运行中...";
      try {
        const payload = await postJson("/api/screeners/bulk-run", {
          date: runDate,
          requested_by: "dashboard_workbench",
          dry_run: false,
        });
        const runCount =
          payload && payload.bulk_run ? payload.bulk_run.run_count ?? PLACEHOLDER : PLACEHOLDER;
        wbResult.textContent = `批量运行完成（日期 ${runDate} · 运行数 ${runCount}）。`;

        const screeners = await fetchJson("/api/screeners");
        setDomainSection("screeners", screeners, summarizeScreeners(screeners));
        renderScreenerRuns(screeners);
        renderScreenerRuns(screeners, { boxId: "team-screeners-runs", title: "筛选器运行记录（Top 12）" });
        renderScreenersRunner(screeners);
        renderScreenersRunner(screeners, { runnerId: "team-screeners-runner", showResult: false });

        try {
          const pools = await fetchJson("/api/pools");
          setText("pools-meta", formatMeta(pools));
          setText("pools", formatJson(pools));
          renderPoolsBox(pools);
        } catch (error) {
          showWorkbenchError(`监控池刷新失败：${formatErrorMessage(error)}`);
        }

        const factorMatrix = await fetchJson("/api/factor-matrix/daily");
        factorMatrixIndex = buildFactorMatrixIndex(factorMatrix);
        setText("factor-matrix-meta", formatMeta(factorMatrix));
        setText("factor-matrix", formatJson(factorMatrix));
        renderFactorMatrixBox(factorMatrix);
        renderDailyWorkbench({ factorMatrix, pools: null, screeners });
      } catch (error) {
        const apiError =
          error && error.payload && error.payload.error ? error.payload.error : null;
        if (apiError && apiError.code === "unauthorized") {
          showWorkbenchError(
            formatUnauthorizedHint("运行")
          );
        } else if (apiError && apiError.code === "not_trading_day") {
          const calendarHint = tradingCalendarMeta;
          const hintMax =
            calendarHint && calendarHint.max_trading_day
              ? String(calendarHint.max_trading_day)
              : null;
          showWorkbenchError(
            `非交易日：运行日期 ${runDate} · 本地最新交易日 ${hintMax || "未知"}。`
          );
        } else {
          showWorkbenchError(`运行失败：${formatErrorMessage(error)}`);
        }
        wbResult.textContent = `运行失败：${formatErrorMessage(error)}`;
      } finally {
        wbBulkRun.disabled = false;
      }
    });
  }

  if (wbQmRun && wbResult) {
    wbQmRun.addEventListener("click", async (event) => {
      event.preventDefault();
      clearWorkbenchError();
      const runDate = computeWorkbenchDate();
      if (!window.confirm(`确认生成“当日因子矩阵”？\n日期：${runDate}`)) {
        return;
      }
      if (!isDataReady()) {
        const message = explainNotReady();
        showWorkbenchError(message);
        wbResult.textContent = message;
        return;
      }
      wbQmRun.disabled = true;
      wbResult.textContent = "生成量化矩阵中...";
      try {
        const payload = await postJson("/api/factor-matrix/daily/run", {
          date: runDate,
          requested_by: "dashboard_workbench",
          dry_run: false,
          debug: false,
        });
        wbResult.textContent = `量化矩阵生成完成（日期 ${runDate}）。`;
        const factorMatrix = await fetchJson("/api/factor-matrix/daily");
        factorMatrixIndex = buildFactorMatrixIndex(factorMatrix);
        setText("factor-matrix-meta", formatMeta(factorMatrix));
        setText("factor-matrix", formatJson(factorMatrix));
        renderFactorMatrixBox(factorMatrix);
        renderCandidatesMatrix(factorMatrix);
        renderDailyWorkbench({ factorMatrix, pools: null, screeners: null });
      } catch (error) {
        const apiError =
          error && error.payload && error.payload.error ? error.payload.error : null;
        if (apiError && apiError.code === "unauthorized") {
          showWorkbenchError(
            formatUnauthorizedHint("运行")
          );
        } else if (apiError && apiError.code === "not_trading_day") {
          const calendarHint = tradingCalendarMeta;
          const hintMax =
            calendarHint && calendarHint.max_trading_day
              ? String(calendarHint.max_trading_day)
              : null;
          showWorkbenchError(
            `非交易日：运行日期 ${runDate} · 本地最新交易日 ${hintMax || "未知"}。`
          );
        } else {
          showWorkbenchError(`生成失败：${formatErrorMessage(error)}`);
        }
        wbResult.textContent = `生成失败：${formatErrorMessage(error)}`;
      } finally {
        wbQmRun.disabled = false;
      }
    });
  }

  async function saveScreenerConfig() {
    if (
      !screenerConfigJson ||
      !screenerConfigStatus ||
      !screenerConfigSave
    ) {
      return;
    }
    const screenerId = String(selectedScreenerId || "").trim();
    if (!screenerId) return;
    let obj = null;
    const rawJson = String(screenerConfigJson.value || "").trim();
    const shouldUseJson = rawJson && rawJson !== "{}";
    if (shouldUseJson) {
      try {
        obj = JSON.parse(rawJson);
      } catch (error) {
        screenerConfigStatus.textContent = "保存失败：原始参数 JSON 不是合法格式。";
        return;
      }
    } else {
      const built = buildCurrentParametersFromForm();
      if (!built.ok) {
        screenerConfigStatus.textContent = `保存失败：${built.error}`;
        return;
      }
      obj = built.params;
      screenerConfigJson.value = formatJson(obj);
    }
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      screenerConfigStatus.textContent = "保存失败：参数必须是 JSON 对象（{}）。";
      return;
    }
    screenerConfigSave.disabled = true;
    screenerConfigStatus.textContent = TEXT_SAVING;
    try {
      await postJson(`/api/screeners/config/${encodeURIComponent(screenerId)}`, {
        current_parameters: obj,
        requested_by: "dashboard",
      });
      screenerConfigStatus.textContent = `已保存：${screenerId}（下一次运行将使用新参数）`;
      await loadSelectedScreenerConfig();
    } catch (error) {
      const apiError =
        error && error.payload && error.payload.error ? error.payload.error : null;
      if (apiError && apiError.code === "unauthorized") {
        screenerConfigStatus.textContent = `保存失败：${formatUnauthorizedHint("保存")}`;
      } else {
        screenerConfigStatus.textContent = `保存失败：${formatErrorMessage(error)}`;
      }
    } finally {
      screenerConfigSave.disabled = false;
    }
  }

  async function resetScreenerConfig() {
    if (
      !screenerConfigStatus ||
      !screenerConfigReset ||
      !screenerConfigForm
    ) {
      return;
    }
    const screenerId = String(selectedScreenerId || "").trim();
    if (!screenerId) return;
    screenerConfigReset.disabled = true;
    screenerConfigStatus.textContent = "重置中...";
    try {
      await postJson(`/api/screeners/config/${encodeURIComponent(screenerId)}`, {
        current_parameters: {},
        requested_by: "dashboard",
      });
      screenerConfigStatus.textContent = `已重置：${screenerId}（已恢复默认参数）`;
      await loadSelectedScreenerConfig();
    } catch (error) {
      const apiError =
        error && error.payload && error.payload.error ? error.payload.error : null;
      if (apiError && apiError.code === "unauthorized") {
        screenerConfigStatus.textContent = `重置失败：${formatUnauthorizedHint("重置")}`;
      } else {
        screenerConfigStatus.textContent = `重置失败：${formatErrorMessage(error)}`;
      }
    } finally {
      screenerConfigReset.disabled = false;
    }
  }

  async function runStockCheck() {
    if (
      !stockCheckCode ||
      !stockCheckRun ||
      !stockCheckStatus ||
      !stockCheckResult ||
      !stockCheckRaw
    ) {
      return;
    }
    const raw = String(stockCheckCode.value || "").trim();
    if (!raw) {
      stockCheckStatus.textContent = "请先填写股票代码。";
      return;
    }
    let normalized = raw;
    const prefixed = raw.match(/^(sz|sh|bj)(\d{6})$/i);
    if (prefixed) {
      normalized = prefixed[2];
    } else {
      const dotted = raw.split(".", 1)[0];
      if (dotted && dotted !== raw) {
        normalized = dotted;
      }
    }
    stockCheckRun.disabled = true;
    stockCheckStatus.textContent = "检查中...";
    stockCheckResult.textContent = "检查中...";
    stockCheckRaw.textContent = "检查中...";
    try {
      const payload = await fetchJson(
        `/api/check-stock?code=${encodeURIComponent(normalized)}`
      );
      stockCheckRaw.textContent = formatJson(payload);
      renderStockCheckResult(payload);
      stockCheckStatus.textContent = `已完成：${normalized}`;
      // 渲染个股增强信息（板块归属、分层、RPS、筛选器命中）
      renderStockEnhancedInfo(normalized);
    } catch (error) {
      stockCheckStatus.textContent = `检查失败：${formatErrorMessage(error)}`;
      stockCheckResult.textContent = `检查失败：${formatErrorMessage(error)}`;
      stockCheckRaw.textContent = `检查失败：${formatErrorMessage(error)}`;
    } finally {
      stockCheckRun.disabled = false;
    }
  }

  if (screenerConfigSave) {
    screenerConfigSave.addEventListener("click", (event) => {
      event.preventDefault();
      saveScreenerConfig();
    });
  }
  if (screenerConfigReset) {
    screenerConfigReset.addEventListener("click", (event) => {
      event.preventDefault();
      resetScreenerConfig();
    });
  }

  if (screenerConfigClose) {
    screenerConfigClose.addEventListener("click", (event) => {
      event.preventDefault();
      closeScreenerConfigModal();
    });
  }

  if (screenerConfigModal) {
    screenerConfigModal.addEventListener("click", (event) => {
      if (event.target === screenerConfigModal) {
        closeScreenerConfigModal();
      }
    });
  }

  window.addEventListener("keydown", (event) => {
    if (String(event.key || "").toLowerCase() !== "escape") return;
    const modal = document.getElementById("screener-config-modal");
    if (!modal || modal.hidden) return;
    closeScreenerConfigModal();
  });

  const legacyConfigId = document.getElementById("screener-config-id");
  const legacyConfigLoad = document.getElementById("screener-config-load");
  if (legacyConfigId && legacyConfigLoad) {
    legacyConfigLoad.addEventListener("click", (event) => {
      event.preventDefault();
      selectedScreenerId = String(legacyConfigId.value || "").trim();
      loadSelectedScreenerConfig();
    });
  }
  if (stockCheckRun) {
    stockCheckRun.addEventListener("click", (event) => {
      event.preventDefault();
      runStockCheck();
    });
  }

  // 筛选器增强：一键运行全部按钮（醒目版）
  const bulkRunHighlight = document.getElementById("screeners-bulk-run-highlight");
  const bulkRunHint = document.getElementById("screeners-bulk-run-hint");
  if (bulkRunHighlight) {
    bulkRunHighlight.addEventListener("click", async (event) => {
      event.preventDefault();
      const runDate = computeWorkbenchDate();
      if (!isDataReady()) {
        if (bulkRunHint) bulkRunHint.textContent = explainNotReady();
        return;
      }
      if (!window.confirm(`确认一键运行全部已启用筛选器？\n日期：${runDate}`)) {
        return;
      }
      bulkRunHighlight.disabled = true;
      if (bulkRunHint) bulkRunHint.textContent = "批量运行中...";
      try {
        await postJson("/api/screeners/bulk-run", {
          date: runDate,
          requested_by: "dashboard",
          dry_run: false,
        });
        const refreshed = await fetchJson("/api/screeners");
        lastScreenersPayload = refreshed;
        setDomainSection("screeners", refreshed, summarizeScreeners(refreshed));
        renderScreenerRuns(refreshed);
        renderScreenerRuns(refreshed, { boxId: "team-screeners-runs", title: "筛选器运行记录（Top 12）" });
        renderScreenersRunner(refreshed);
        renderScreenersRunner(refreshed, { runnerId: "team-screeners-runner", showResult: false });
        renderScreenerConfigPanel(refreshed);
        if (bulkRunHint) bulkRunHint.textContent = `批量运行完成（日期 ${runDate}）。`;
      } catch (error) {
        let message = `批量运行失败：${formatErrorMessage(error)}`;
        const apiError = error && error.payload && error.payload.error ? error.payload.error : null;
        if (apiError && apiError.code === "not_trading_day") {
          const calendarHint = tradingCalendarMeta;
          const hintMax = calendarHint && calendarHint.max_trading_day ? String(calendarHint.max_trading_day) : null;
          if (hintMax) {
            message = `批量运行失败：非交易日（当前 ${runDate}）。本地最新交易日 ${hintMax}。`;
          }
        }
        if (apiError && apiError.code === "unauthorized") {
          message = `批量运行失败：${formatUnauthorizedHint("运行")}`;
        }
        if (bulkRunHint) bulkRunHint.textContent = message;
      } finally {
        bulkRunHighlight.disabled = false;
      }
    });
  }
}

function reportFatalDashboardError(error) {
  const statusElement = document.getElementById("global-status");
  const errorElement = document.getElementById("global-error");
  const message =
    error && typeof error === "object" && error.message
      ? String(error.message)
      : String(error || "unknown error");
  if (statusElement) statusElement.textContent = "仪表盘脚本初始化失败。";
  if (errorElement) {
    errorElement.hidden = false;
    errorElement.textContent = `仪表盘脚本错误：${message}`;
  }
}

window.addEventListener("error", (event) => {
  reportFatalDashboardError(event && event.error ? event.error : event && event.message ? event.message : event);
});
window.addEventListener("unhandledrejection", (event) => {
  reportFatalDashboardError(event && event.reason ? event.reason : event);
});

try {
  initControls();
} catch (error) {
  reportFatalDashboardError(error);
}
try {
  initClock();
} catch (error) {
  reportFatalDashboardError(error);
}
try {
  Promise.resolve(loadDashboard()).catch(reportFatalDashboardError);
} catch (error) {
  reportFatalDashboardError(error);
}

window.addEventListener("hashchange", () => {
  applyFocusMode();
  applyNavActive();
});

applyFocusMode();
applyNavActive();
