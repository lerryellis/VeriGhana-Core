import { LegalLayout } from '@/components/landing/LegalLayout'

export const metadata = {
  title: 'Privacy Policy — VeriGhana',
  description: 'How VeriGhana collects, uses, and protects your personal data.',
}

export default function PrivacyPage() {
  return (
    <LegalLayout
      title="Privacy Policy"
      subtitle="How we collect, use, and protect your information."
      lastUpdated="March 2026"
      sections={[
        {
          heading: '1. Who We Are',
          body: (
            <p>
              VeriGhana is an AI-powered fact-checking platform developed as part of a Computer Science research
              project at GIMPA (Ghana Institute of Management and Public Administration). We are committed to
              protecting your privacy and handling your data responsibly.
            </p>
          ),
        },
        {
          heading: '2. Information We Collect',
          body: (
            <>
              <p>We collect the following types of information:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><strong>Account data:</strong> your email address, name, and password (stored as a secure hash) when you register.</li>
                <li><strong>Usage data:</strong> claims you submit for verification, verdicts returned, and timestamps — used to improve accuracy and enforce fair-use limits.</li>
                <li><strong>Technical data:</strong> IP address, browser type, and device information collected automatically for security and abuse prevention.</li>
                <li><strong>Payment data:</strong> billing information processed securely by Paystack. We do not store card numbers.</li>
              </ul>
            </>
          ),
        },
        {
          heading: '3. How We Use Your Information',
          body: (
            <>
              <p>Your data is used to:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li>Operate and improve the VeriGhana platform</li>
                <li>Enforce your subscription tier and daily usage limits</li>
                <li>Send account-related emails (confirmation, password reset)</li>
                <li>Detect and prevent abuse, spam, or fraudulent activity</li>
                <li>Generate anonymous aggregate statistics about misinformation trends in Ghana</li>
              </ul>
              <p className="mt-3">We do <strong>not</strong> sell your personal data to third parties.</p>
            </>
          ),
        },
        {
          heading: '4. Data Storage & Security',
          body: (
            <p>
              Your data is stored on Supabase infrastructure hosted in the EU (London region). We use
              industry-standard encryption in transit (TLS) and at rest. Passwords are hashed using bcrypt
              and are never stored in plain text. Access to production data is restricted to authorised
              team members only.
            </p>
          ),
        },
        {
          heading: '5. Third-Party Services',
          body: (
            <>
              <p>VeriGhana uses the following third-party services:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><strong>Supabase</strong> — authentication and database</li>
                <li><strong>Google Gemini / Groq / Cohere</strong> — AI claim verification (claims are sent to these APIs for analysis)</li>
                <li><strong>Paystack</strong> — payment processing</li>
                <li><strong>Railway / Vercel</strong> — hosting infrastructure</li>
              </ul>
              <p className="mt-3">
                Claims you submit may be sent to AI providers for processing. Do not submit claims
                containing sensitive personal information.
              </p>
            </>
          ),
        },
        {
          heading: '6. Cookies',
          body: (
            <p>
              We use essential session cookies to keep you signed in. We do not use tracking cookies or
              third-party advertising cookies. You can clear cookies at any time through your browser settings,
              though this will sign you out.
            </p>
          ),
        },
        {
          heading: '7. Your Rights',
          body: (
            <>
              <p>You have the right to:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li>Access the personal data we hold about you</li>
                <li>Request correction of inaccurate data</li>
                <li>Request deletion of your account and associated data</li>
                <li>Export your verification history</li>
              </ul>
              <p className="mt-3">
                To exercise these rights, contact us at <strong>privacy@verighana.com</strong>.
              </p>
            </>
          ),
        },
        {
          heading: '8. Children\'s Privacy',
          body: (
            <p>
              VeriGhana is not directed at children under 13. We do not knowingly collect personal
              information from children. If you believe a child has provided us with personal information,
              please contact us and we will delete it promptly.
            </p>
          ),
        },
        {
          heading: '9. Changes to This Policy',
          body: (
            <p>
              We may update this Privacy Policy from time to time. We will notify registered users of
              significant changes via email. Continued use of VeriGhana after changes constitutes
              acceptance of the updated policy.
            </p>
          ),
        },
        {
          heading: '10. Contact',
          body: (
            <p>
              For privacy-related questions or requests, email us at <strong>privacy@verighana.com</strong>{' '}
              or use the <a href="/app/contact" className="text-blue-600 hover:underline">contact form</a> in your dashboard.
            </p>
          ),
        },
      ]}
    />
  )
}
