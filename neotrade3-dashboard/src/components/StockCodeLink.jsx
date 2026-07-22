import { buildTonghuashunStockUrl, normalizeStockCode } from './stockCodeUtils';

export default function StockCodeLink({ code, className = '', children = null }) {
  const normalized = normalizeStockCode(code);
  const href = buildTonghuashunStockUrl(normalized);
  const text = children ?? normalized ?? '--';

  if (!href) {
    return <span className={className}>{text}</span>;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className={className}
      title={`在同花顺中打开 ${normalized}`}
    >
      {text}
    </a>
  );
}
