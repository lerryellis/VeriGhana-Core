'use client'

interface Props {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  totalItems: number
  pageSize: number
}

export function Pagination({ page, totalPages, onPageChange, totalItems, pageSize }: Props) {
  if (totalPages <= 1) return null
  const start = (page - 1) * pageSize + 1
  const end   = Math.min(page * pageSize, totalItems)

  return (
    <div className="flex items-center justify-between pt-4">
      <span className="text-xs text-slate-400 font-mono-vg">
        {start}–{end} of {totalItems}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ← Prev
        </button>
        {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
          let p: number
          if (totalPages <= 5) {
            p = i + 1
          } else if (page <= 3) {
            p = i + 1
          } else if (page >= totalPages - 2) {
            p = totalPages - 4 + i
          } else {
            p = page - 2 + i
          }
          return (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              className={`text-xs w-8 h-8 rounded-lg transition-colors ${
                p === page
                  ? 'bg-[#0f2240] text-white'
                  : 'text-slate-500 hover:bg-slate-100'
              }`}
            >
              {p}
            </button>
          )
        })}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  )
}
