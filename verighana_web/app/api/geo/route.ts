import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'edge'

export function GET(request: NextRequest) {
  const country =
    request.headers.get('x-vercel-ip-country') ??
    'US'
  return NextResponse.json({ country_code: country })
}
