import { NextResponse, type NextRequest } from "next/server";

const sessionCookie = `${process.env.SESSION_COOKIE_NAME ?? "nodo_session"}_access`;
const refreshCookie = `${process.env.SESSION_COOKIE_NAME ?? "nodo_session"}_refresh`;

export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has(sessionCookie) || request.cookies.has(refreshCookie);
  if (!hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/coach/:path*", "/athlete/:path*", "/settings/:path*"],
};
