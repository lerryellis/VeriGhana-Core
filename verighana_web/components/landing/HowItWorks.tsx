const steps = [
  {
    num: '01',
    title: 'Continuous Source Monitoring',
    desc: 'Our scraper crawls 60+ Ghanaian government portals and media outlets every 6 hours via GitHub Actions, storing articles in a Supabase database.',
  },
  {
    num: '02',
    title: 'AI Semantic Embedding',
    desc: "Each article is converted into a 3072-dimension vector using Gemini's embedding model, enabling semantic search that goes beyond simple keyword matching.",
  },
  {
    num: '03',
    title: 'Cascading Verification',
    desc: 'Your claim is matched against indexed content at multiple similarity thresholds. Gemini AI reads the top matches and returns a scored verdict with source citations.',
  },
]

export function HowItWorks() {
  return (
    <section id="how" className="py-20 px-[5%] bg-[#f8fafc] text-center">
      <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Under the hood</p>
      <h2 className="font-display text-3xl font-extrabold text-[#0f2240] tracking-tight mb-2">How VeriGhana Works</h2>
      <p className="text-slate-500 mb-12">Three layers of AI verification, updated every six hours.</p>

      <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
        {steps.map(s => (
          <div key={s.num} className="bg-white border border-slate-200 rounded-xl p-6 text-left shadow-sm hover:shadow-md transition-shadow">
            <div className="font-display text-3xl font-extrabold text-blue-600/20 mb-3">{s.num}</div>
            <div className="font-display font-bold text-[#0f2240] mb-2">{s.title}</div>
            <div className="text-sm text-slate-500 leading-relaxed">{s.desc}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
