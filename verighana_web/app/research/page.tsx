import Link from 'next/link'
import { Nav } from '@/components/landing/Nav'
import { Footer } from '@/components/landing/Footer'

export const metadata = {
  title: 'Research — VeriGhana',
  description: 'Ghana-focused research on misinformation, fact-checking, and the information environment. Reports, briefings, and academic outputs from VeriGhana.',
}

const THEMES = [
  {
    icon: '🗳️',
    title: 'Elections & Political Claims',
    desc: 'Verifying campaign promises, polling-station rumours, and ECG-related claims across Ghana\'s 2024 and 2028 election cycles.',
    tags: ['Elections', 'NDC', 'NPP', 'EC Ghana'],
  },
  {
    icon: '💊',
    title: 'Health Misinformation',
    desc: 'Tracking false claims about COVID-19 vaccines, traditional remedies, cholera outbreaks, malaria prevention, and Ghana Health Service guidance.',
    tags: ['GHS', 'NMIMR', 'Vaccines'],
  },
  {
    icon: '💵',
    title: 'Economic Claims',
    desc: 'Fact-checking cedi-depreciation narratives, inflation figures, GDP statistics, IMF programme claims, and Bank of Ghana announcements.',
    tags: ['BoG', 'GSS', 'IMF', 'Cedi'],
  },
  {
    icon: '🗣️',
    title: 'Local-Language Information',
    desc: 'How misinformation spreads in Twi, Ga, Ewe, Hausa, and Dagbani — and what verification looks like beyond English-language news.',
    tags: ['Twi', 'Ga', 'Ewe', 'Hausa'],
  },
  {
    icon: '📱',
    title: 'WhatsApp & Social Platforms',
    desc: 'Mapping how false claims propagate through Ghanaian WhatsApp groups, X/Twitter, Facebook, TikTok, and the role of forwarded media.',
    tags: ['WhatsApp', 'X', 'TikTok'],
  },
  {
    icon: '🏛️',
    title: 'Government Accountability',
    desc: 'Verifying ministerial statements, parliamentary claims, agency press releases, and public-sector performance data.',
    tags: ['MoF', 'Parliament', 'GRA'],
  },
  {
    icon: '⛪',
    title: 'Religious & Traditional Claims',
    desc: 'Treating faith-adjacent and traditional-medicine claims with care: where evidence applies, where pluralism is owed, and where harm must be flagged.',
    tags: ['Faith', 'Traditional Medicine'],
  },
  {
    icon: '🌍',
    title: 'Diaspora & Migration',
    desc: 'Information flowing into and out of Ghanaian diaspora communities — embassy notices, visa rumours, and remittance claims.',
    tags: ['Diaspora', 'Migration'],
  },
]

const PUBLICATIONS = [
  {
    type: 'Dissertation',
    year: '2026',
    title: 'VeriGhana: A Domain-Specific Retrieval-Augmented Fact-Checking Platform for Ghana',
    author: 'Ellis Lamptey',
    venue: 'MSc Computer Science, Ghana Institute of Management and Public Administration (GIMPA)',
    summary: 'Design Science Research project building and evaluating a production fact-checking system over a corpus of 64+ trusted Ghanaian news and government sources, with multi-provider AI verification cascade and pgvector semantic retrieval.',
    status: 'In review',
  },
  {
    type: 'Working paper',
    year: '2026',
    title: 'The Six-Strategy HTML Scraping Cascade: Architecture for Heterogeneous African News Sites',
    author: 'Ellis Lamptey',
    venue: 'VeriGhana Technical Report 2026/01',
    summary: 'A replicable engineering pattern for ingesting articles from Ghanaian newsrooms whose page architectures range from server-rendered WordPress to JavaScript-rendered SPAs, including a Playwright-based fallback for sites that block conventional scrapers.',
    status: 'Draft',
  },
  {
    type: 'Briefing',
    year: '2026',
    title: 'Qualitative Evaluation of an AI Fact-Checker: Five Themes from Ghanaian Users',
    author: 'Ellis Lamptey',
    venue: 'VeriGhana Briefing Series',
    summary: 'Thematic analysis of structured open-ended responses from journalists, researchers, students, educators, and general-public users of the live VeriGhana platform — what builds trust, what blocks adoption, and how citation transparency changes the user experience.',
    status: 'Forthcoming',
  },
]

const PARTNERS = [
  { name: 'GIMPA', desc: 'Ghana Institute of Management and Public Administration — dissertation supervision and institutional review.' },
  { name: 'GhanaFact', desc: 'Reference benchmark for established Ghanaian fact-checking practice; comparative work in progress.' },
  { name: 'MFWA', desc: 'Media Foundation for West Africa — context on the broader regional information environment.' },
  { name: 'Penplusbytes', desc: 'Ghanaian civic-tech and media accountability NGO whose work has informed our source selection.' },
]

export default function ResearchPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Nav />

      {/* Hero */}
      <header className="px-[5%] py-20 text-center" style={{ background: 'linear-gradient(150deg,#c8b5a2 0%,#ddd3c4 25%,#ede8e0 50%,#cddce8 80%,#b4cce0 100%)' }}>
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-700 uppercase tracking-widest mb-3">Research</p>
          <h1 className="font-display font-extrabold text-3xl md:text-5xl text-[#0f2240] mb-4 leading-tight">
            Evidence-grounded research for Ghana&apos;s information environment.
          </h1>
          <p className="text-base md:text-lg text-slate-700 leading-relaxed">
            Knowing what is accurate is half the fight for a better information environment. We also need to understand how falsehoods travel, how beliefs are formed, and what interventions fact-checkers can use to be most effective &mdash; in Ghana.
          </p>
          <p className="text-xs text-slate-500 mt-3 italic">
            Framing adapted from Full Fact (UK), <a href="https://fullfact.org/policy/research/" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-700">fullfact.org/policy/research</a>.
          </p>
        </div>
      </header>

      {/* Mission */}
      <section className="px-[5%] py-16 bg-white">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Our remit</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-4">Ghana-specific. Open. Reproducible.</h2>
          <div className="text-slate-600 leading-relaxed space-y-4 text-base">
            <p>
              Most academic and industry research on automated fact-checking is built on English-language sources from the United States and Western Europe. The findings, the source corpora, and the assumptions about what an &ldquo;ordinary citizen&rdquo; needs to verify a claim are shaped by those settings. Ghana&apos;s information environment is different — different sources, different platforms, different verification habits, different languages, different stakes.
            </p>
            <p>
              Our remit, borrowing the formulation used by Full Fact (UK), is to <em>put reliable evidence at the heart of public debate</em> &mdash; in our case, public debate in Ghana. Every dataset we build is sampled from Ghanaian sources. Every evaluation is conducted with Ghanaian respondents. Every published finding is open-access and reproducible from the public repository. We are a small project: this is not a substitute for the work done by GhanaFact, the Ghana Journalists Association, or the country&apos;s established media houses. It is an attempt to add a public, technical, transparent layer to the same effort.
            </p>
          </div>
        </div>
      </section>

      {/* Research Questions — adapted from Full Fact's research themes */}
      <section className="px-[5%] py-16 bg-white border-t border-slate-100">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Research questions</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-3">What we&apos;re trying to find out</h2>
          <p className="text-slate-500 mb-10 max-w-2xl">
            Six questions structure our work. They borrow the question framing pioneered by Full Fact&apos;s research programme and re-anchor it in Ghana&apos;s context.
          </p>

          <div className="space-y-4">
            {[
              { q: 'How do falsehoods actually travel in Ghana?', detail: 'Mapping the routes — WhatsApp forwards, X threads, Facebook reels, talk radio call-ins — that move a claim from origin to mass audience, and the points at which intervention is feasible.' },
              { q: 'What drives belief in conspiracy claims, and what works against them?',  detail: 'Borrowing from Full Fact\'s work on conspiracy beliefs, examining whether the same drivers apply in Ghana and which counter-strategies translate, particularly around faith-adjacent and traditional-medicine claims.' },
              { q: 'What is the impact of health misinformation across Ghana?', detail: 'Full Fact\'s comparative work on health misinformation across Africa, Latin America, and the UK gives us a baseline; we sharpen the African leg with Ghana-specific evidence on vaccines, cholera response, malaria treatments, and Ghana Health Service messaging.' },
              { q: 'Does fact-checking actually change minds — or does it backfire?', detail: 'Full Fact has documented evidence that fact-checking generally informs rather than polarises (the &ldquo;backfire effect&rdquo; is rare). We test whether that finding holds in Ghana, where trust in mediating institutions follows a different distribution.' },
              { q: 'How should fact-checks be communicated online?',                              detail: 'Balancing attention and accuracy in WhatsApp-first, mobile-data-conscious distribution — adapting Full Fact\'s &ldquo;Communicating Fact Checks Online&rdquo; principles to the formats most Ghanaian citizens actually read.' },
              { q: 'What does the Ghanaian public think about fact-checking?',  detail: 'Following Full Fact\'s tradition of asking audiences directly, we collect structured qualitative responses from Ghanaian users on what they trust, what they distrust, and what they wish fact-checkers did differently.' },
            ].map((item, i) => (
              <div key={item.q} className="bg-slate-50 border border-slate-200 rounded-xl p-5 hover:border-blue-300 transition-colors">
                <div className="flex gap-4">
                  <div className="font-display font-extrabold text-xl text-blue-600 shrink-0">Q{i + 1}</div>
                  <div>
                    <h3 className="font-display font-bold text-base text-[#0f2240] mb-1">{item.q}</h3>
                    <p className="text-sm text-slate-600 leading-relaxed">{item.detail}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Themes */}
      <section className="px-[5%] py-16 bg-slate-50 border-y border-slate-200">
        <div className="max-w-5xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2 text-center">Research themes</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-3 text-center">Eight focus areas</h2>
          <p className="text-slate-500 text-center max-w-2xl mx-auto mb-12">
            We organise our work around the eight themes that account for the majority of high-impact misinformation claims observed in Ghana.
          </p>

          <div className="grid md:grid-cols-2 gap-5">
            {THEMES.map(t => (
              <div key={t.title} className="bg-white border border-slate-200 rounded-xl p-6 hover:shadow-md hover:border-blue-200 transition-all">
                <div className="text-3xl mb-3" aria-hidden>{t.icon}</div>
                <h3 className="font-display font-bold text-base text-[#0f2240] mb-2">{t.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed mb-3">{t.desc}</p>
                <div className="flex flex-wrap gap-1.5">
                  {t.tags.map(tag => (
                    <span key={tag} className="text-[0.65rem] font-mono-vg text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Publications */}
      <section className="px-[5%] py-16 bg-white">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Publications</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-3">Reports &amp; briefings</h2>
          <p className="text-slate-500 mb-10">
            Outputs from the VeriGhana research programme. All publications are open-access; preprints are released ahead of formal venue submission.
          </p>

          <div className="space-y-5">
            {PUBLICATIONS.map(pub => (
              <article key={pub.title} className="border border-slate-200 rounded-xl p-6 hover:border-blue-300 transition-colors">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="text-[0.65rem] font-mono-vg bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full uppercase tracking-wider">{pub.type}</span>
                  <span className="text-[0.65rem] font-mono-vg text-slate-400">{pub.year}</span>
                  <span className={`text-[0.65rem] font-mono-vg px-2 py-0.5 rounded-full uppercase tracking-wider ml-auto ${
                    pub.status === 'In review' ? 'bg-amber-100 text-amber-700' :
                    pub.status === 'Draft'     ? 'bg-slate-100 text-slate-500' :
                                                  'bg-green-100 text-green-700'
                  }`}>
                    {pub.status}
                  </span>
                </div>
                <h3 className="font-display font-bold text-lg text-[#0f2240] mb-1 leading-snug">{pub.title}</h3>
                <p className="text-sm text-slate-500 mb-3">{pub.author} · {pub.venue}</p>
                <p className="text-sm text-slate-600 leading-relaxed">{pub.summary}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="px-[5%] py-16 bg-slate-50 border-y border-slate-200">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Methodology</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-6">How we work</h2>

          <div className="space-y-5">
            {[
              { num: '01', title: 'Design Science Research', body: 'Built on Hevner et al. (2004): research outputs are working artifacts whose value is demonstrated through rigorous evaluation, not hypotheses tested against existing phenomena.' },
              { num: '02', title: 'Ghana-sampled corpora',    body: 'Every fact-check dataset we publish is drawn from Ghanaian news outlets, government agencies, and civic-tech sources — 64+ active publishers indexed every six hours.' },
              { num: '03', title: 'Mixed-methods evaluation', body: 'Quantitative accuracy testing on curated claim sets is complemented by qualitative thematic analysis (Braun & Clarke, 2006) of structured open-ended responses from Ghanaian users.' },
              { num: '04', title: 'Open replication',        body: 'Code, source lists, evaluation prompts, and dataset construction notes are public. Any researcher can reproduce a result from the repository alone.' },
            ].map(m => (
              <div key={m.num} className="flex gap-5 bg-white border border-slate-200 rounded-xl p-5">
                <div className="font-display font-extrabold text-2xl text-blue-600 shrink-0 leading-none">{m.num}</div>
                <div>
                  <h3 className="font-display font-bold text-base text-[#0f2240] mb-1">{m.title}</h3>
                  <p className="text-sm text-slate-600 leading-relaxed">{m.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Partners */}
      <section className="px-[5%] py-16 bg-white">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2 text-center">Partners &amp; collaborators</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-3 text-center">Working with Ghanaian institutions</h2>
          <p className="text-slate-500 text-center max-w-2xl mx-auto mb-10">
            Our work is read, supervised, and challenged by institutions whose remit overlaps with ours.
          </p>

          <div className="grid sm:grid-cols-2 gap-4">
            {PARTNERS.map(p => (
              <div key={p.name} className="border border-slate-200 rounded-xl p-5 hover:border-blue-300 transition-colors">
                <p className="font-display font-bold text-base text-[#0f2240] mb-1">{p.name}</p>
                <p className="text-sm text-slate-600 leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Influences & further reading — explicit attribution to Full Fact */}
      <section className="px-[5%] py-16 bg-slate-50 border-y border-slate-200">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Influences &amp; further reading</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-[#0f2240] mb-3">Standing on the work of others</h2>
          <p className="text-slate-600 leading-relaxed mb-6 max-w-3xl">
            Our research programme is shaped substantially by the published work of <a href="https://fullfact.org/policy/research/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-500 underline">Full Fact</a>, the UK&apos;s independent fact-checking charity (registered charity no. 1158683). Several of the reports below are sources we draw on directly when designing studies and interpreting Ghanaian findings. Where we adopt their framing or evidence, we cite them; where we depart, we explain why.
          </p>

          <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
            {[
              { title: 'A Checklist for Fact Checkers',                  note: 'Practical recommendations distilled from misinformation research; informs our editorial discipline.' },
              { title: 'Communicating Uncertainty',                       note: 'How to convey evidence limitations honestly without losing the audience — directly applicable to our verdict labelling.' },
              { title: 'Conspiracy Beliefs',                              note: 'Drivers of belief in conspiracy theories and intervention strategies — adapted to Ghanaian faith-adjacent and traditional-medicine claims.' },
              { title: 'The Impact of Health Misinformation',             note: 'Comparative work across Africa, Latin America, and the UK — we sharpen the Africa leg with Ghana-specific evidence.' },
              { title: 'Media and Information Literacy',                  note: 'Effectiveness review with regional comparative analysis we draw on when assessing reader-side interventions.' },
              { title: 'The Impact of Fact Checking',                     note: 'Evidence on the effects of fact-checking on public figures, institutions, and media. We test whether the same effects appear in Ghana.' },
              { title: 'Communicating Fact Checks Online',                note: 'Attention–accuracy trade-offs in online formats; informs how we design WhatsApp-shareable verdicts.' },
              { title: 'Who Believes and Shares Misinformation?',         note: 'Cognitive biases underlying acceptance of false claims — relevant cross-culturally though distributions vary.' },
              { title: 'Researching Misinformation',                      note: 'Overview of lessons, gaps, and emerging research directions — our research questions are partly structured around their gap analysis.' },
              { title: 'The Backfire Effect',                             note: 'Evidence that fact-checking informs rather than entrenches. We replicate the question in Ghana, where trust distributions differ.' },
              { title: 'What People Think About Fact Checking',           note: 'Audience research methodology we adapt for our qualitative evaluation strand.' },
            ].map(p => (
              <div key={p.title} className="px-6 py-4 hover:bg-slate-50 transition-colors">
                <p className="font-display font-semibold text-sm text-[#0f2240]">{p.title}</p>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{p.note}</p>
              </div>
            ))}
          </div>

          <p className="text-xs text-slate-500 mt-5 italic">
            All Full Fact reports cited above are available open-access at <a href="https://fullfact.org/policy/research/" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-700">fullfact.org/policy/research</a>. Their work is reproduced and referenced here under fair-use academic citation. VeriGhana is not affiliated with Full Fact.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="px-[5%] py-20" style={{ background: 'linear-gradient(135deg,#0f2240 0%,#1a3a6e 100%)' }}>
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-xs font-mono-vg text-blue-300 uppercase tracking-widest mb-3">Get involved</p>
          <h2 className="font-display font-extrabold text-2xl md:text-3xl text-white mb-4">
            Are you in Ghana? Help us evaluate the platform.
          </h2>
          <p className="text-blue-100 text-base mb-8 max-w-xl mx-auto leading-relaxed">
            Sign in, verify a claim, and complete the optional research questions at the end of the feedback form. Responses are anonymised and analysed thematically as part of the live evaluation reported in the dissertation.
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <Link
              href="/app/verify"
              className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-6 py-3 rounded-lg transition-colors"
            >
              Try VeriGhana
            </Link>
            <Link
              href="/app/feedback"
              className="bg-white/10 hover:bg-white/15 text-white text-sm font-medium px-6 py-3 rounded-lg border border-white/20 transition-colors"
            >
              Participate in Research →
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
