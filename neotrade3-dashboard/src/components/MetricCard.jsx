export default function MetricCard({ title, value, subtitle, badge = null, emphasis = 'default' }) {
  const valueClass =
    emphasis === 'positive'
      ? 'text-emerald-600'
      : emphasis === 'negative'
        ? 'text-red-600'
        : 'text-gray-900'

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-gray-500 mb-2">{title}</div>
          <div className={`text-2xl font-bold mb-1 ${valueClass}`}>{value}</div>
          {subtitle ? <div className="text-sm text-gray-500">{subtitle}</div> : null}
        </div>
        {badge}
      </div>
    </div>
  )
}
