import { RefreshCw } from 'lucide-react'

export default function PageHeader({ title, subtitle, onRefresh, loading = false, actions = null }) {
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
        {subtitle ? <div className="text-gray-500 mt-1">{subtitle}</div> : null}
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        {actions}
        {typeof onRefresh === 'function' ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        ) : null}
      </div>
    </div>
  )
}
