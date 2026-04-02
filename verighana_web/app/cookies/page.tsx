import { LegalLayout } from '@/components/landing/LegalLayout'

export const metadata = {
  title: 'Cookie Policy — VeriGhana',
  description: 'How VeriGhana uses cookies and similar technologies.',
}

export default function CookiePolicyPage() {
  return (
    <LegalLayout
      title="Cookie Policy"
      subtitle="How we use cookies and similar technologies on VeriGhana."
      lastUpdated="April 2026"
      sections={[
        {
          heading: '1. What Are Cookies?',
          body: (
            <p>
              Cookies are small text files stored on your device when you visit a website. They help the site
              remember your preferences, keep you logged in, and understand how you use the service. VeriGhana
              uses cookies and similar technologies (such as localStorage) to provide a secure, functional experience.
            </p>
          ),
        },
        {
          heading: '2. Cookies We Use',
          body: (
            <>
              <p>VeriGhana uses the following categories of cookies:</p>

              <h4 className="font-semibold mt-4 mb-2">Essential Cookies (Required)</h4>
              <p className="mb-2">These are strictly necessary for the platform to function. You cannot opt out of these.</p>
              <ul className="list-disc pl-5 space-y-1">
                <li><strong>Supabase Auth cookies</strong> — maintain your login session and authenticate API requests. Without these, you cannot sign in.</li>
                <li><strong>CSRF / security tokens</strong> — protect against cross-site request forgery and other attacks.</li>
              </ul>

              <h4 className="font-semibold mt-4 mb-2">Functional Cookies</h4>
              <p className="mb-2">These remember your preferences to improve your experience.</p>
              <ul className="list-disc pl-5 space-y-1">
                <li><strong>Theme / UI preferences</strong> — stored in localStorage to remember display settings across sessions.</li>
                <li><strong>Selected AI model</strong> — remembers your last-used verification model so you do not need to re-select it.</li>
                <li><strong>Sidebar state</strong> — remembers whether the admin sidebar is collapsed or expanded.</li>
              </ul>

              <h4 className="font-semibold mt-4 mb-2">Analytics Cookies</h4>
              <p className="mb-2">We currently do <strong>not</strong> use third-party analytics cookies (such as Google Analytics). All usage tracking is done server-side through our own database for:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Counting daily verifications per user (rate limiting)</li>
                <li>Aggregate platform statistics (total users, total verifications)</li>
                <li>Monitoring scraper pipeline health</li>
              </ul>
              <p className="mt-2">This data is never shared with third parties or used for advertising.</p>

              <h4 className="font-semibold mt-4 mb-2">Payment Cookies</h4>
              <p>When you use the checkout flow, Paystack may set its own cookies to process your payment securely. These are governed by <a href="https://paystack.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Paystack&apos;s Privacy Policy</a>.</p>
            </>
          ),
        },
        {
          heading: '3. Third-Party Cookies',
          body: (
            <>
              <p>VeriGhana minimises third-party cookie usage. The only third-party services that may set cookies are:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><strong>Supabase</strong> — authentication provider (essential cookies only)</li>
                <li><strong>Google OAuth</strong> — if you sign in with Google, Google may set cookies during the authentication flow</li>
                <li><strong>Paystack</strong> — payment processing cookies during checkout</li>
              </ul>
              <p className="mt-2">We do not use cookies for advertising, tracking across other websites, or selling data to third parties.</p>
            </>
          ),
        },
        {
          heading: '4. localStorage and sessionStorage',
          body: (
            <>
              <p>In addition to cookies, VeriGhana uses browser storage APIs:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><strong>localStorage</strong> — stores your auth session tokens (managed by Supabase), UI preferences, and email notification settings. Data persists until you clear your browser data or sign out.</li>
                <li><strong>sessionStorage</strong> — stores temporary data that is cleared when you close the browser tab.</li>
              </ul>
            </>
          ),
        },
        {
          heading: '5. Managing Cookies',
          body: (
            <>
              <p>You can control cookies through your browser settings:</p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li><strong>Block all cookies</strong> — this will prevent you from signing in to VeriGhana.</li>
                <li><strong>Block third-party cookies</strong> — VeriGhana will still function, but Google Sign-In and Paystack checkout may be affected.</li>
                <li><strong>Clear cookies</strong> — you will be signed out and preferences will be reset.</li>
              </ul>
              <p className="mt-2">Most browsers allow you to manage cookies in Settings → Privacy → Cookies. For detailed instructions, visit your browser&apos;s help page.</p>
            </>
          ),
        },
        {
          heading: '6. Data Retention',
          body: (
            <p>
              Essential cookies expire when your authentication session ends (typically 7 days of inactivity).
              Functional preferences stored in localStorage persist until you clear your browser data or delete
              your account. Server-side usage logs are retained as described in our <a href="/privacy" className="text-blue-600 hover:underline">Privacy Policy</a>.
            </p>
          ),
        },
        {
          heading: '7. Updates to This Policy',
          body: (
            <p>
              We may update this Cookie Policy from time to time to reflect changes in technology, legislation,
              or our practices. The &quot;Last updated&quot; date at the top of this page indicates when the policy was
              last revised. Continued use of VeriGhana after changes constitutes acceptance.
            </p>
          ),
        },
        {
          heading: '8. Contact Us',
          body: (
            <p>
              If you have questions about our use of cookies, contact us at{' '}
              <a href="mailto:support@verighana.com" className="text-blue-600 hover:underline">support@verighana.com</a>{' '}
              or use the <a href="/app/contact" className="text-blue-600 hover:underline">Support page</a>.
            </p>
          ),
        },
      ]}
    />
  )
}
