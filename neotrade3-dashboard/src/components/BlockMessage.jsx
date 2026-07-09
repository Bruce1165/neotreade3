import { STATUS_COPY } from './statusCopy'

function toneClass(tone) {
  if (tone === 'red') return 'bg-red-50 border-red-200 text-red-700'
  if (tone === 'amber') return 'bg-amber-50 border-amber-200 text-amber-800'
  if (tone === 'green') return 'bg-emerald-50 border-emerald-200 text-emerald-700'
  return 'bg-gray-50 border-gray-200 text-gray-600'
}

export default function BlockMessage({ tone = 'gray', message, onRetry, retryLabel = STATUS_COPY.retry }) {
  return (
    <div className={`rounded-lg border p-4 text-sm flex items-center justify-between gap-3 ${toneClass(tone)}`}>
      <span>{message}</span>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1 rounded bg-white text-gray-700 border border-gray-200 hover:bg-gray-50"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  )
}
