import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { Resend } from 'resend'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code  = searchParams.get('code')
  const next  = searchParams.get('next') ?? '/app/verify'
  const error = searchParams.get('error')

  if (error) {
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(error)}`)
  }

  if (code) {
    const supabase = await createClient()
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

    if (!exchangeError) {
      // Send welcome email on first login (check if we've already sent one via user metadata)
      const { data: { user } } = await supabase.auth.getUser()
      if (user?.email && !user.user_metadata?.welcome_email_sent) {
        await sendWelcomeEmail(user.email, user.user_metadata?.full_name ?? user.email.split('@')[0])
        // Mark as sent so we don't resend on every login
        await supabase.auth.updateUser({ data: { welcome_email_sent: true } })
      }

      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`)
}

async function sendWelcomeEmail(email: string, name: string) {
  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) return

  try {
    const resend = new Resend(apiKey)
    await resend.emails.send({
      from: 'VeriGhana <hello@verighana.com>',
      to: email,
      subject: 'Welcome to VeriGhana',
      html: `
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#1e293b">
          <div style="background:#0f2240;padding:32px 40px;border-radius:12px 12px 0 0">
            <h1 style="margin:0;font-size:22px;color:#ffffff;font-weight:800;letter-spacing:-0.5px">
              Veri<span style="color:#60a5fa">Ghana</span>
            </h1>
          </div>
          <div style="background:#ffffff;padding:32px 40px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px">
            <h2 style="margin:0 0 12px;font-size:18px;color:#0f2240">Welcome, ${name}!</h2>
            <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.6">
              Thank you for joining VeriGhana — Ghana&rsquo;s fact-checking platform.
              You can now verify claims, check news articles, and access trusted sources powered by AI.
            </p>
            <p style="margin:0 0 24px;font-size:15px;color:#475569;line-height:1.6">
              You&rsquo;re on the <strong>Free plan</strong>, which includes 5 verifications per day.
              Upgrade to Pro or Institutional for unlimited access.
            </p>
            <a href="https://verighana.com/app/verify"
               style="display:inline-block;background:#2563eb;color:#ffffff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none">
              Start Verifying →
            </a>
            <hr style="margin:28px 0;border:none;border-top:1px solid #e2e8f0" />
            <p style="margin:0;font-size:12px;color:#94a3b8">
              You&rsquo;re receiving this because you signed up at verighana.com.
              To manage email preferences, visit your
              <a href="https://verighana.com/app/account" style="color:#2563eb">account settings</a>.
            </p>
          </div>
        </div>
      `,
    })
  } catch {
    // Non-blocking — don't fail the auth flow if email fails
  }
}
