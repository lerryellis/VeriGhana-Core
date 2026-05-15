import Link from 'next/link'
import { Nav } from '@/components/landing/Nav'
import { Footer } from '@/components/landing/Footer'

export const metadata = {
  title: 'Research — VeriGhana',
  description: 'Ghana-focused research on misinformation, fact-checking, and the information environment. Reports, briefings, and academic outputs from VeriGhana.',
}

const FF_HUB = 'https://fullfact.org/policy/research/'

// External references drawn on by VeriGhana's research programme. Titles refer to
// Full Fact (UK)'s published outputs and each title links directly to the PDF or
// landing page on fullfact.org. Descriptions are original to VeriGhana and
// explain the relevance of each reference to our Ghana-focused work.
type Ref = { title: string; desc: string; url: string; format: 'PDF' | 'Web'; thumb: string; tint: string }

const REFERENCES: Array<Ref> = [
  { thumb: '✓', tint: 'bg-emerald-50 text-emerald-700',  title: 'A checklist for fact checkers',                 desc: 'Editorial discipline that informs our verdict workflow and reviewer checklist.',                              format: 'PDF', url: 'https://fullfact.org/media/uploads/briefing-fact-check-checklist-en.pdf' },
  { thumb: '?', tint: 'bg-amber-50 text-amber-700',      title: 'Communicating uncertainty',                     desc: 'Shapes how we label PARTIAL and UNCORROBORATED verdicts without losing the reader.',                          format: 'PDF', url: 'https://fullfact.org/media/uploads/en-communicating-uncertainty.pdf' },
  { thumb: '◉', tint: 'bg-purple-50 text-purple-700',    title: 'Conspiracy beliefs',                            desc: 'Drivers we test against Ghanaian faith-adjacent and traditional-medicine claims.',                            format: 'PDF', url: 'https://fullfact.org/media/uploads/en-conspiracy-beliefs.pdf' },
  { thumb: '+', tint: 'bg-rose-50 text-rose-700',        title: 'The impact of health misinformation',           desc: 'Comparative work we sharpen with Ghana-specific evidence on GHS messaging.',                                   format: 'PDF', url: 'https://fullfact.org/media/uploads/en-tackling-health-misinfo.pdf' },
  { thumb: '☰', tint: 'bg-sky-50 text-sky-700',          title: 'Media and information literacy',                desc: 'Effectiveness by region; informs how we design reader-side interventions for Ghana.',                         format: 'PDF', url: 'https://fullfact.org/media/uploads/media-information-literacy-lessons.pdf' },
  { thumb: '⚖', tint: 'bg-slate-100 text-slate-700',    title: 'The impact of fact checking',                   desc: 'Evidence that fact-checks affect public figures and media — we replicate in Ghana.',                          format: 'PDF', url: 'https://fullfact.org/media/uploads/impact-fact-checkers-public-figures-media.pdf' },
  { thumb: '↗', tint: 'bg-blue-50 text-blue-700',        title: 'Communicating fact checks online',              desc: 'Attention–accuracy trade-offs applicable to WhatsApp-first distribution in Ghana.',                           format: 'PDF', url: 'https://fullfact.org/media/uploads/how-communicate-fact-checks-online.pdf' },
  { thumb: '◐', tint: 'bg-fuchsia-50 text-fuchsia-700',  title: 'Who believes and shares misinformation?',       desc: 'Cognitive baseline for Ghana-comparative analysis of belief and sharing behaviour.',                          format: 'PDF', url: 'https://fullfact.org/media/uploads/who-believes-shares-misinformation.pdf' },
  { thumb: '≡', tint: 'bg-indigo-50 text-indigo-700',    title: 'Public engagement with the news',               desc: 'Methodological model for our Ghanaian audience-research design.',                                              format: 'PDF', url: 'https://fullfact.org/media/uploads/uk-audience-engagement-politics-information-news.pdf' },
  { thumb: '◊', tint: 'bg-teal-50 text-teal-700',        title: 'Researching misinformation',                    desc: 'Evidence gaps and directions our Ghana research questions are partly structured around.',                     format: 'PDF', url: 'https://fullfact.org/media/uploads/en-2019-20-research-overview.pdf' },
  { thumb: '☑', tint: 'bg-emerald-50 text-emerald-700',  title: 'A checklist for fact checking an election',     desc: 'Editorial discipline transferred to our Ghana 2024 and 2028 election workflows.',                             format: 'PDF', url: 'https://fullfact.org/media/uploads/election-factcheck-checklist.pdf' },
  { thumb: '▲', tint: 'bg-orange-50 text-orange-700',    title: 'Campaign tactics during the 2019 election',     desc: 'Tactic patterns with clear analogues in Ghanaian campaign communication.',                                    format: 'PDF', url: 'https://fullfact.org/media/uploads/ff_election_research_report_final_version_16.12.19.pdf' },
  { thumb: '▼', tint: 'bg-orange-50 text-orange-700',    title: 'Fact checking in the 2019 election',            desc: 'Reference for our Ghana election fact-checking design and editorial lessons.',                                format: 'PDF', url: 'https://fullfact.org/media/uploads/election-factcheck-briefing.pdf' },
  { thumb: '◢', tint: 'bg-slate-100 text-slate-700',    title: 'Political trust in the UK',                     desc: 'Trust distributions we report against — Ghana&apos;s differ structurally.',                                   format: 'PDF', url: 'https://fullfact.org/media/uploads/political-trust-in-the-uk.pdf' },
  { thumb: '₵', tint: 'bg-green-50 text-green-700',      title: 'Understanding of economic terms',               desc: 'Informs how we frame verdicts on cedi, inflation, and GDP claims.',                                            format: 'PDF', url: 'https://fullfact.org/media/uploads/understanding_the_economy_research_briefing.pdf' },
  { thumb: '↺', tint: 'bg-red-50 text-red-700',          title: 'The backfire effect',                           desc: 'We test whether the &ldquo;informs rather than entrenches&rdquo; finding holds in Ghana.',                    format: 'PDF', url: 'https://fullfact.org/media/uploads/backfire_report_fullfact.pdf' },
  { thumb: '♀', tint: 'bg-pink-50 text-pink-700',        title: 'Does fact checking have a women problem?',      desc: 'Demographics that inform our purposive sampling for the qualitative evaluation.',                             format: 'Web', url: 'https://fullfact.org/blog/2018/jul/does-factchecking-have-women-problem/' },
  { thumb: '◔', tint: 'bg-cyan-50 text-cyan-700',        title: 'Audience research for Full Fact',               desc: 'Methodological precedent for our opt-in qualitative evaluation strand.',                                       format: 'PDF', url: 'https://fullfact.org/media/uploads/full_fact_audience_research_final.pdf' },
  { thumb: '✎', tint: 'bg-yellow-50 text-yellow-700',    title: 'What people think about fact checking',         desc: 'We ask the same question in Ghana and report comparative findings.',                                          format: 'PDF', url: 'https://fullfact.org/media/uploads/NatCen-Need_for_fact_checking_in_Britain.pdf' },
]

const THEMES = [
  { title: 'Misinformation propagation',     desc: 'How false claims travel through Ghanaian WhatsApp groups, X, Facebook, TikTok, and the role of forwarded media.' },
  { title: 'Health misinformation',          desc: 'Tracking vaccine, malaria, cholera, and traditional-remedy claims against Ghana Health Service and NMIMR evidence.' },
  { title: 'Economic claims',                desc: 'Fact-checking cedi depreciation, inflation, GDP, IMF programme, and Bank of Ghana announcements.' },
  { title: 'Election integrity',             desc: 'Verifying campaign promises, polling-station rumours, and EC Ghana statements across the 2024 and 2028 cycles.' },
  { title: 'Local-language information',     desc: 'How misinformation spreads in Twi, Ga, Ewe, Hausa, and Dagbani beyond English-language news.' },
  { title: 'Government accountability',      desc: 'Verifying ministerial statements, parliamentary claims, agency press releases, and public-sector performance data.' },
  { title: 'Religious & traditional claims', desc: 'Where evidence applies, where pluralism is owed, and where harm must be flagged.' },
  { title: 'Diaspora & migration',           desc: 'Embassy notices, visa rumours, and remittance claims flowing into and out of Ghanaian diaspora communities.' },
]

const VG_OUTPUTS = [
  {
    type: 'Dissertation',     year: '2026', status: 'In review',
    title: 'VeriGhana: A Domain-Specific Retrieval-Augmented Fact-Checking Platform for Ghana',
    venue: 'MSc Computer Science, GIMPA',
    desc: 'Design Science Research project building and evaluating a production fact-checking system over a corpus of 64+ trusted Ghanaian news and government sources.',
  },
  {
    type: 'Working paper',   year: '2026', status: 'Draft',
    title: 'The Six-Strategy HTML Scraping Cascade: Architecture for Heterogeneous African News Sites',
    venue: 'VeriGhana Technical Report 2026/01',
    desc: 'A replicable engineering pattern for ingesting articles from Ghanaian newsrooms whose page architectures vary from server-rendered WordPress to JavaScript-rendered SPAs.',
  },
  {
    type: 'Briefing',        year: '2026', status: 'Forthcoming',
    title: 'Qualitative Evaluation of an AI Fact-Checker: Five Themes from Ghanaian Users',
    venue: 'VeriGhana Briefing Series',
    desc: 'Thematic analysis of structured open-ended responses from journalists, researchers, students, educators, and general-public users of the live VeriGhana platform.',
  },
]

export default function ResearchPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Nav />

      {/* Hero — sober, hub-style */}
      <header className="px-[5%] py-16 border-b border-slate-200 bg-white">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-3">Research</p>
          <h1 className="font-display font-extrabold text-3xl md:text-4xl text-[#0f2240] mb-4 leading-tight">
            Evidence-grounded research for Ghana&apos;s information environment.
          </h1>
          <p className="text-base text-slate-600 leading-relaxed max-w-3xl">
            Knowing what is accurate is half the fight. We also study how falsehoods travel, how beliefs are formed, and what interventions fact-checkers can use to be most effective — in Ghana.
          </p>
          <p className="text-xs text-slate-400 mt-3 italic">
            Framing adapted from Full Fact (UK), <a href="https://fullfact.org/policy/research/" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-700">fullfact.org/policy/research</a>.
          </p>
        </div>
      </header>

      {/* In-page anchor nav */}
      <nav className="sticky top-16 z-30 bg-white/95 backdrop-blur border-b border-slate-200 px-[5%]">
        <div className="max-w-4xl mx-auto flex gap-6 overflow-x-auto py-3 text-sm">
          <a href="#remit"      className="text-slate-500 hover:text-[#0f2240] whitespace-nowrap">Remit</a>
          <a href="#themes"     className="text-slate-500 hover:text-[#0f2240] whitespace-nowrap">Themes</a>
          <a href="#outputs"    className="text-slate-500 hover:text-[#0f2240] whitespace-nowrap">Our outputs</a>
          <a href="#references" className="text-slate-500 hover:text-[#0f2240] whitespace-nowrap">References</a>
          <a href="#contact"    className="text-slate-500 hover:text-[#0f2240] whitespace-nowrap">Contact</a>
        </div>
      </nav>

      {/* Remit */}
      <section id="remit" className="px-[5%] py-14 border-b border-slate-200">
        <div className="max-w-4xl mx-auto grid md:grid-cols-[180px_1fr] gap-8">
          <h2 className="font-display font-bold text-sm text-slate-400 uppercase tracking-widest pt-1">Remit</h2>
          <div className="text-slate-600 leading-relaxed space-y-4 text-base">
            <p>
              Most academic and industry research on automated fact-checking is built on English-language sources from the United States and Western Europe. The findings, source corpora, and assumptions about what an ordinary citizen needs to verify a claim are shaped by those settings. Ghana&apos;s information environment is different.
            </p>
            <p>
              Our remit, borrowing the formulation used by Full Fact, is to put reliable evidence at the heart of public debate &mdash; in our case, public debate in Ghana. Every dataset we build is sampled from Ghanaian sources. Every evaluation is conducted with Ghanaian respondents. Every published finding is open-access and reproducible from the public repository.
            </p>
          </div>
        </div>
      </section>

      {/* Themes */}
      <section id="themes" className="px-[5%] py-14 border-b border-slate-200">
        <div className="max-w-4xl mx-auto grid md:grid-cols-[180px_1fr] gap-8">
          <div>
            <h2 className="font-display font-bold text-sm text-slate-400 uppercase tracking-widest pt-1">Themes</h2>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">Eight areas that account for most of the high-impact misinformation observed in Ghana.</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-x-8 gap-y-5">
            {THEMES.map(t => (
              <div key={t.title} className="border-l-2 border-blue-100 pl-4 py-1 hover:border-blue-500 transition-colors">
                <h3 className="font-display font-semibold text-[#0f2240] text-sm mb-1">{t.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{t.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* VeriGhana outputs */}
      <section id="outputs" className="px-[5%] py-14 border-b border-slate-200">
        <div className="max-w-4xl mx-auto grid md:grid-cols-[180px_1fr] gap-8">
          <div>
            <h2 className="font-display font-bold text-sm text-slate-400 uppercase tracking-widest pt-1">Our outputs</h2>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">Published and forthcoming from the VeriGhana research programme. Open-access.</p>
          </div>
          <div className="space-y-6">
            {VG_OUTPUTS.map(o => (
              <article key={o.title} className="pb-6 border-b border-slate-100 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2 mb-2 text-[0.65rem] font-mono-vg uppercase tracking-wider">
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{o.type}</span>
                  <span className="text-slate-400">{o.year}</span>
                  <span className={`px-2 py-0.5 rounded-full ml-auto ${
                    o.status === 'In review' ? 'bg-amber-100 text-amber-700' :
                    o.status === 'Draft'     ? 'bg-slate-100 text-slate-500' :
                                                'bg-green-100 text-green-700'
                  }`}>{o.status}</span>
                </div>
                <h3 className="font-display font-bold text-base text-[#0f2240] mb-1 leading-snug">{o.title}</h3>
                <p className="text-xs text-slate-500 mb-2 font-mono-vg">{o.venue}</p>
                <p className="text-sm text-slate-600 leading-relaxed">{o.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* References — Full Fact catalogue, our descriptions, direct links */}
      <section id="references" className="px-[5%] py-14 border-b border-slate-200 bg-slate-50">
        <div className="max-w-4xl mx-auto grid md:grid-cols-[180px_1fr] gap-8">
          <div>
            <h2 className="font-display font-bold text-sm text-slate-400 uppercase tracking-widest pt-1">References</h2>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Published work by <a href={FF_HUB} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline hover:text-blue-500">Full Fact (UK)</a> that informs our Ghana-focused research. Each title links directly to the report PDF or page on fullfact.org. Descriptions are original to VeriGhana and explain how each is relevant to our work.
            </p>
          </div>
          <ol className="grid sm:grid-cols-2 gap-2.5 list-none">
            {REFERENCES.map(r => (
              <li key={r.title}>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex gap-3 bg-white border border-slate-200 hover:border-blue-400 hover:shadow-sm rounded-md p-3 transition-all h-full"
                >
                  <div className={`shrink-0 w-12 h-12 rounded-md flex items-center justify-center text-xl font-bold ${r.tint}`} aria-hidden>
                    {r.thumb}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-2 mb-0.5">
                      <h3 className="font-display font-semibold text-[0.8rem] text-[#0f2240] leading-snug group-hover:text-blue-600 flex-1">
                        {r.title}
                        <span className="text-blue-500 ml-1 text-[0.65rem]" aria-hidden>↗</span>
                      </h3>
                      <span className={`shrink-0 font-mono-vg text-[0.55rem] uppercase tracking-wider px-1.5 py-0.5 rounded ${
                        r.format === 'PDF' ? 'bg-red-50 text-red-600 border border-red-100'
                                            : 'bg-blue-50 text-blue-600 border border-blue-100'
                      }`}>
                        {r.format}
                      </span>
                    </div>
                    <p className="text-[0.7rem] text-slate-500 leading-relaxed">{r.desc}</p>
                  </div>
                </a>
              </li>
            ))}
          </ol>
          <div className="md:col-start-2">
            <p className="text-xs text-slate-500 italic mt-2">
              Full Fact is the UK&apos;s independent fact-checking charity (registered charity no. 1158683). All linked reports are hosted on, and available open-access from, fullfact.org. VeriGhana is not affiliated with Full Fact; these references are listed under fair-use academic citation, and every link sends the reader directly to the original source.
            </p>
          </div>
        </div>
      </section>

      {/* Contact / participate */}
      <section id="contact" className="px-[5%] py-14">
        <div className="max-w-4xl mx-auto grid md:grid-cols-[180px_1fr] gap-8">
          <h2 className="font-display font-bold text-sm text-slate-400 uppercase tracking-widest pt-1">Contact</h2>
          <div>
            <p className="text-slate-600 text-base leading-relaxed mb-5">
              If you&apos;re a researcher, journalist, or institution working on Ghana&apos;s information environment, we want to hear from you. To participate in the live qualitative evaluation strand, sign in and complete the optional research questions in the feedback form.
            </p>
            <div className="flex gap-3 flex-wrap">
              <Link
                href="/app/feedback"
                className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
              >
                Participate in research →
              </Link>
              <Link
                href="/app/verify"
                className="bg-white hover:bg-slate-50 text-[#0f2240] text-sm font-medium px-5 py-2.5 rounded-lg border border-slate-300 transition-colors"
              >
                Try VeriGhana
              </Link>
              <a
                href="mailto:ellis.lamptey@bolt.eu"
                className="bg-white hover:bg-slate-50 text-slate-600 text-sm font-medium px-5 py-2.5 rounded-lg border border-slate-300 transition-colors"
              >
                Contact lead researcher
              </a>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
