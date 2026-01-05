import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  // Handle OAuth errors
  if (error) {
    return NextResponse.redirect(
      new URL(`/settings?slack_error=${encodeURIComponent(error)}`, request.url)
    );
  }

  // OAuth was cancelled or no code
  if (!code) {
    return NextResponse.redirect(
      new URL('/settings?slack_error=no_code', request.url)
    );
  }

  // Redirect to settings with success
  return NextResponse.redirect(
    new URL('/settings?slack_connected=true', request.url)
  );
}
