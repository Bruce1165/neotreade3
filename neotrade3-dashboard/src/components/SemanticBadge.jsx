import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  buildSemanticStatusTitle,
  getSemanticStatusClasses,
  getSemanticStatusDefinition,
} from './semanticStatus'

export default function SemanticBadge({ semanticKey, label, className = '' }) {
  const definition = getSemanticStatusDefinition(semanticKey)
  const triggerRef = useRef(null)
  const tooltipRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [tooltipStyle, setTooltipStyle] = useState(null)
  const displayLabel = String(label || definition?.label || '--').trim()
  const title = definition ? buildSemanticStatusTitle(semanticKey, displayLabel) : displayLabel
  const badgeClass = definition ? getSemanticStatusClasses(semanticKey) : ''

  useEffect(() => {
    if (!open || !definition) return undefined

    const updatePosition = () => {
      if (!triggerRef.current) return

      const triggerRect = triggerRef.current.getBoundingClientRect()
      const tooltipWidth = 288
      const viewportPadding = 8
      const tooltipHeight = tooltipRef.current?.offsetHeight || 0

      const left = Math.min(
        Math.max(triggerRect.left + triggerRect.width / 2 - tooltipWidth / 2, viewportPadding),
        window.innerWidth - tooltipWidth - viewportPadding
      )

      const preferBelowTop = triggerRect.bottom + 8
      const preferAboveTop = triggerRect.top - tooltipHeight - 8
      const top =
        tooltipHeight > 0 &&
        preferBelowTop + tooltipHeight > window.innerHeight - viewportPadding &&
        preferAboveTop >= viewportPadding
          ? preferAboveTop
          : preferBelowTop

      setTooltipStyle({
        top: `${Math.max(viewportPadding, top)}px`,
        left: `${left}px`,
        width: `${tooltipWidth}px`,
      })
    }

    updatePosition()
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [definition, open, title])

  if (!definition) {
    return (
      <span className={className}>
        {label || '--'}
      </span>
    )
  }

  return (
    <>
      <span className={`relative inline-flex align-middle ${className}`.trim()}>
        <span
          ref={triggerRef}
          tabIndex={0}
          className={`inline-flex items-center px-2 py-1 rounded text-xs border ${badgeClass}`}
          aria-label={title}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
        >
          {displayLabel}
        </span>
      </span>
      {open && typeof document !== 'undefined'
        ? createPortal(
            <span
              ref={tooltipRef}
              className="pointer-events-none fixed z-[9999] rounded-lg border border-gray-200 bg-white p-3 text-left text-xs leading-5 text-gray-700 shadow-lg"
              style={tooltipStyle || { visibility: 'hidden' }}
            >
              <div className="font-semibold text-gray-900">{displayLabel}</div>
              <div className="mt-1">
                <span className="font-medium text-gray-900">一级状态：</span>
                {definition.group}
              </div>
              <div className="mt-1">
                <span className="font-medium text-gray-900">含义：</span>
                {definition.description}
              </div>
              <div className="mt-1">
                <span className="font-medium text-gray-900">触发条件：</span>
                {definition.trigger}
              </div>
              {definition.difference ? (
                <div className="mt-1">
                  <span className="font-medium text-gray-900">区别：</span>
                  {definition.difference}
                </div>
              ) : null}
            </span>,
            document.body
          )
        : null}
    </>
  )
}
