'use client'

export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="bg-[#0f2240] hover:bg-[#1a3a6e] text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
    >
      Download / Print PDF
    </button>
  )
}
