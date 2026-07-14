/**
 * Next.js Edge Middleware — auth guard.
 *
 * Protects /dashboard/* routes: if no access token is present in the
 * quantnexus-auth localStorage entry, redirect to /login.
 *
 * NOTE: Middleware runs in the Edge runtime — it cannot access localStorage
 * directly. Instead, we use a cookie-based auth signal (`qn-authed`) that
 * the client sets on login and clears on logout.
 *
 * The cookie is NOT the JWT itself (tokens stay in localStorage for security),
 * it is only a presence signal for the middleware redirect gate.
 */
import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PATHS = ["/dashboard", "/charts", "/screener", "/settings"];
const AUTH_SIGNAL_COOKIE = "qn-authed";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));

  if (!isProtected) return NextResponse.next();

  const authed = request.cookies.get(AUTH_SIGNAL_COOKIE)?.value === "1";

  if (!authed) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except Next.js internals and static assets.
     */
    "/((?!_next/static|_next/image|favicon.ico|public/).*)",
  ],
};
