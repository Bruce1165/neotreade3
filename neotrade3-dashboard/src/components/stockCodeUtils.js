const A_SHARE_PREFIXES = new Set([
  '000',
  '001',
  '002',
  '003',
  '300',
  '301',
  '600',
  '601',
  '603',
  '605',
  '688',
]);

export function normalizeStockCode(code) {
  return String(code || '').trim();
}

export function isSupportedAStockCode(code) {
  const normalized = normalizeStockCode(code);
  return /^\d{6}$/.test(normalized) && A_SHARE_PREFIXES.has(normalized.slice(0, 3));
}

export function buildTonghuashunStockUrl(code) {
  const normalized = normalizeStockCode(code);
  if (!isSupportedAStockCode(normalized)) {
    return null;
  }
  return `https://stockpage.10jqka.com.cn/${normalized}/`;
}
