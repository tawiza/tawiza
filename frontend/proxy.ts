import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Proxy (Next.js 16): auth gate.
 *
 * Protects /dashboard/* routes. Redirects to /login if no session.
 * Auth tokens stored in localStorage (client-side) + refresh_token cookie.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth entirely if SKIP_AUTH is set (e.g. behind Cloudflare Access)
  if (process.env.SKIP_AUTH === 'true') {
    return NextResponse.next();
  }

  const hasRefreshToken = request.cookies.has('refresh_token');
  const hasTawizaSession = request.cookies.has('tawiza-auth');

  // Redirect / to dashboard or login
  if (pathname === '/') {
    if (hasRefreshToken || hasTawizaSession) {
      return NextResponse.redirect(new URL('/dashboard/main', request.url));
    }
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // If user has session and tries to go to /login, redirect to dashboard
  if (pathname === '/login' && (hasRefreshToken || hasTawizaSession)) {
    return NextResponse.redirect(new URL('/dashboard/main', request.url));
  }

  // Protect /dashboard/* routes — redirect to login if no session
  if (pathname.startsWith('/dashboard')) {
    // Server-side: check for refresh_token cookie or tawiza-auth cookie
    // Client-side: AuthContext checks localStorage (more reliable)
    // We allow through if either cookie exists; client AuthContext handles full validation
    if (!hasRefreshToken && !hasTawizaSession) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|img|.*\\..*).*)' ,
  ],
};
