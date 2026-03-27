'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'

interface Props {
  userEmail: string
  userTier: string
  priorSubmission: { id: string; created_at: string } | null
}

const ROLES = [
  { value: 'researcher',  label: 'Researcher / Academic' },
  { value: 'journalist',  label: 'Journalist / Media' },
  { value: 'student',     label: 'Student' },
  { value: 'developer',   label: 'Developer / Engineer' },
  { value: 'educator',    label: 'Educator' },
  { value: 'general',     label: 'General Public' },
]

const FREQUENCIES = [
  { value: 'daily',        label: 'Daily' },
  { value: 'weekly',       label: 'Weekly' },
  { value: 'monthly',      label: 'Monthly' },
  { value: 'occasionally', label: 'Occasionally' },
  { value: 'first_time',   label: 'This is my first time' },
]

const RATINGS = [
  { key: 'rating_accuracy',   label: 'Accuracy of results',        desc: 'How accurate are the fact-check verdicts?' },
  { key: 'rating_usability',  label: 'Ease of use',                desc: 'How easy is the platform to navigate and use?' },
  { key: 'rating_speed',      label: 'Speed',                      desc: 'How fast does the verification process feel?' },
  { key: 'rating_reliability', label: 'Reliability',               desc: 'Does the platform work consistently without errors?' },
  { key: 'rating_value',      label: 'Overall value',              desc: 'How valuable is VeriGhana for your work?' },
]

const LIKERTS = [
  { key: 'likert_easy_to_use',   label: 'VeriGhana is easy to use and understand.' },
  { key: 'likert_trust_results', label: 'I trust the fact-checking results provided.' },
  { key: 'likert_improves_work', label: 'VeriGhana improves my workflow / research process.' },
  { key: 'likert_recommend',     label: 'I would recommend VeriGhana to a colleague.' },
]

const LIKERT_LABELS = ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree']

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0)
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          aria-label={`${n} star`}
          className={`text-2xl transition-colors ${
            n <= (hover || value) ? 'text-amber-400' : 'text-slate-200'
          }`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

function LikertRow({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="py-3 border-b border-slate-100 last:border-0">
      <p className="text-sm text-[#0f2240] mb-2">{label}</p>
      <div className="flex gap-2 flex-wrap">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={`flex-1 min-w-[80px] text-xs py-2 px-1 rounded-lg border transition-colors ${
              value === n
                ? 'bg-blue-600 border-blue-600 text-white font-medium'
                : 'border-slate-200 text-slate-500 hover:border-blue-300'
            }`}
          >
            {LIKERT_LABELS[n - 1]}
          </button>
        ))}
      </div>
    </div>
  )
}

export function FeedbackClient({ userEmail, userTier, priorSubmission }: Props) {
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step 1 — About you
  const [role, setRole] = useState('')
  const [frequency, setFrequency] = useState('')
  const [useCase, setUseCase] = useState('')

  // Step 2 — NPS + Star ratings
  const [nps, setNps] = useState<number | null>(null)
  const [ratings, setRatings] = useState<Record<string, number>>({})

  // Step 3 — Likert
  const [likerts, setLikerts] = useState<Record<string, number>>({})

  // Step 4 — Open-ended
  const [mostUseful, setMostUseful] = useState('')
  const [biggestChallenge, setBiggestChallenge] = useState('')
  const [featureRequest, setFeatureRequest] = useState('')
  const [generalComments, setGeneralComments] = useState('')

  const totalSteps = 4

  async function handleSubmit() {
    setSubmitting(true)
    setError(null)

    const supabase = createClient()
    const { data: { user } } = await supabase.auth.getUser()

    const { error: err } = await supabase.from('app_feedback').insert({
      user_id:             user?.id ?? null,
      user_email:          userEmail,
      user_tier:           userTier,
      respondent_role:     role,
      use_frequency:       frequency,
      use_case:            useCase.trim() || null,
      nps_score:           nps,
      rating_accuracy:     ratings['rating_accuracy'] ?? null,
      rating_usability:    ratings['rating_usability'] ?? null,
      rating_speed:        ratings['rating_speed'] ?? null,
      rating_reliability:  ratings['rating_reliability'] ?? null,
      rating_value:        ratings['rating_value'] ?? null,
      likert_easy_to_use:  likerts['likert_easy_to_use'] ?? null,
      likert_trust_results: likerts['likert_trust_results'] ?? null,
      likert_improves_work: likerts['likert_improves_work'] ?? null,
      likert_recommend:    likerts['likert_recommend'] ?? null,
      most_useful:         mostUseful.trim() || null,
      biggest_challenge:   biggestChallenge.trim() || null,
      feature_request:     featureRequest.trim() || null,
      general_comments:    generalComments.trim() || null,
    })

    setSubmitting(false)
    if (err) { setError(err.message); return }
    setSubmitted(true)
  }

  if (submitted || priorSubmission) {
    const date = priorSubmission
      ? new Date(priorSubmission.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
      : 'just now'
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-white border border-slate-200 rounded-xl p-10 text-center space-y-4">
          <div className="text-4xl">🙏</div>
          <h2 className="font-display font-bold text-xl text-[#0f2240]">Thank you for your feedback!</h2>
          <p className="text-slate-500 text-sm">
            {priorSubmission && !submitted
              ? `You already submitted feedback on ${date}. Your response has been recorded and helps improve VeriGhana.`
              : 'Your response has been recorded. It helps us improve VeriGhana for researchers, journalists, and the public across Ghana.'}
          </p>
          <a
            href="/app/verify"
            className="inline-block mt-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
          >
            Back to Verify
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Platform Feedback</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Help us evaluate and improve VeriGhana. Takes about 5 minutes.
        </p>
      </div>

      {/* Progress bar */}
      <div className="bg-white border border-slate-200 rounded-xl px-6 py-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">
            Step {step} of {totalSteps}
          </p>
          <p className="text-xs text-slate-400 font-mono-vg">{Math.round((step / totalSteps) * 100)}% complete</p>
        </div>
        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
        <div className="flex justify-between mt-2">
          {['About You', 'Ratings', 'Agreement', 'Open-ended'].map((s, i) => (
            <span key={s} className={`text-[0.65rem] font-mono-vg ${step > i ? 'text-blue-500' : 'text-slate-300'}`}>{s}</span>
          ))}
        </div>
      </div>

      {/* ── Step 1: About You ─────────────────────────────────────────── */}
      {step === 1 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">About You</p>

          <div>
            <label className="block text-sm font-medium text-[#0f2240] mb-2">I primarily use VeriGhana as a…</label>
            <div className="grid grid-cols-2 gap-2">
              {ROLES.map(r => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRole(r.value)}
                  className={`text-sm py-2.5 px-3 rounded-lg border text-left transition-colors ${
                    role === r.value
                      ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0f2240] mb-2">How often do you use VeriGhana?</label>
            <div className="grid grid-cols-3 gap-2">
              {FREQUENCIES.map(f => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setFrequency(f.value)}
                  className={`text-sm py-2.5 px-3 rounded-lg border text-center transition-colors ${
                    frequency === f.value
                      ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0f2240] mb-1">
              Briefly describe your primary use case <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={useCase}
              onChange={e => setUseCase(e.target.value)}
              placeholder="e.g. Verifying political claims for news articles…"
              rows={3}
              className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors resize-none"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!role || !frequency}
              onClick={() => setStep(2)}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: NPS + Star Ratings ────────────────────────────────── */}
      {step === 2 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Ratings</p>

          {/* NPS */}
          <div>
            <label className="block text-sm font-medium text-[#0f2240] mb-1">
              How likely are you to recommend VeriGhana to a colleague or peer?
            </label>
            <p className="text-xs text-slate-400 mb-3">0 = Not at all likely · 10 = Extremely likely</p>
            <div className="flex gap-1.5 flex-wrap">
              {Array.from({ length: 11 }, (_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setNps(i)}
                  className={`w-10 h-10 rounded-lg text-sm font-medium border transition-colors ${
                    nps === i
                      ? i <= 6 ? 'bg-red-500 border-red-500 text-white'
                        : i <= 8 ? 'bg-amber-400 border-amber-400 text-white'
                        : 'bg-green-500 border-green-500 text-white'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {i}
                </button>
              ))}
            </div>
            {nps !== null && (
              <p className="text-xs mt-2 font-mono-vg text-slate-400">
                {nps <= 6 ? 'Detractor — we want to hear why' : nps <= 8 ? 'Passive — room to improve' : 'Promoter — thank you!'}
              </p>
            )}
          </div>

          {/* Star ratings */}
          <div className="space-y-4">
            <p className="text-sm font-medium text-[#0f2240]">Rate each dimension (1–5 stars)</p>
            {RATINGS.map(r => (
              <div key={r.key} className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-sm text-[#0f2240]">{r.label}</p>
                  <p className="text-xs text-slate-400">{r.desc}</p>
                </div>
                <StarRating
                  value={ratings[r.key] ?? 0}
                  onChange={v => setRatings(prev => ({ ...prev, [r.key]: v }))}
                />
              </div>
            ))}
          </div>

          <div className="flex justify-between">
            <button type="button" onClick={() => setStep(1)} className="text-sm text-slate-500 hover:text-slate-700 px-4 py-2.5 rounded-lg border border-slate-200 transition-colors">← Back</button>
            <button
              type="button"
              disabled={nps === null}
              onClick={() => setStep(3)}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Likert Scales ─────────────────────────────────────── */}
      {step === 3 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Level of Agreement</p>
          <p className="text-sm text-slate-500">Select how much you agree with each statement.</p>

          <div>
            {LIKERTS.map(l => (
              <LikertRow
                key={l.key}
                label={l.label}
                value={likerts[l.key] ?? 0}
                onChange={v => setLikerts(prev => ({ ...prev, [l.key]: v }))}
              />
            ))}
          </div>

          <div className="flex justify-between pt-2">
            <button type="button" onClick={() => setStep(2)} className="text-sm text-slate-500 hover:text-slate-700 px-4 py-2.5 rounded-lg border border-slate-200 transition-colors">← Back</button>
            <button
              type="button"
              onClick={() => setStep(4)}
              className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 4: Open-ended ────────────────────────────────────────── */}
      {step === 4 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Your Experience</p>
          <p className="text-sm text-slate-500">All fields are optional but very helpful.</p>

          {[
            { label: 'What do you find most useful about VeriGhana?', value: mostUseful, set: setMostUseful, placeholder: 'e.g. The speed of results, the source citations…' },
            { label: "What's your biggest challenge or frustration?", value: biggestChallenge, set: setBiggestChallenge, placeholder: 'e.g. Accuracy on local dialect claims…' },
            { label: 'What feature would make VeriGhana more useful to you?', value: featureRequest, set: setFeatureRequest, placeholder: 'e.g. Batch claim verification, WhatsApp integration…' },
            { label: 'Any other comments or suggestions?', value: generalComments, set: setGeneralComments, placeholder: 'Anything else on your mind…' },
          ].map(({ label, value, set, placeholder }) => (
            <div key={label}>
              <label className="block text-sm font-medium text-[#0f2240] mb-1">{label}</label>
              <textarea
                value={value}
                onChange={e => set(e.target.value)}
                placeholder={placeholder}
                rows={3}
                maxLength={1000}
                className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors resize-none"
              />
              <p className="text-right text-[0.65rem] text-slate-400 font-mono-vg mt-0.5">{value.length}/1000</p>
            </div>
          ))}

          {error && (
            <div className="text-sm px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-600">{error}</div>
          )}

          <div className="flex justify-between">
            <button type="button" onClick={() => setStep(3)} className="text-sm text-slate-500 hover:text-slate-700 px-4 py-2.5 rounded-lg border border-slate-200 transition-colors">← Back</button>
            <button
              type="button"
              disabled={submitting}
              onClick={handleSubmit}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors flex items-center gap-2"
            >
              {submitting
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Submitting…</>
                : 'Submit Feedback'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
