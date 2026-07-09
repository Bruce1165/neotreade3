function pillClass(kind) {
  if (kind === 'active' || kind === 'entry_ready' || kind === 'stable' || kind === 'buy') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-100'
  }
  if (kind === 'avoid' || kind === 'exit_ready' || kind === 'sell' || kind === 'high') {
    return 'bg-red-50 text-red-700 border-red-100'
  }
  if (kind === 'queued' || kind === 'pullback' || kind === 'medium') {
    return 'bg-amber-50 text-amber-700 border-amber-100'
  }
  if (kind === 'abandoned' || kind === 'blocked') {
    return 'bg-gray-100 text-gray-700 border-gray-200'
  }
  return 'bg-blue-50 text-blue-700 border-blue-100'
}

export default function StatusPill({ kind, label }) {
  return (
    <span className={`inline-flex items-center rounded border px-2 py-1 text-xs ${pillClass(kind)}`}>
      {label}
    </span>
  )
}
