import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isAuthPage = pathname === "/login" || pathname === "/register";
  const isProtectedPage = pathname.startsWith("/dashboard") || pathname.startsWith("/profile");

  // If an authenticated user tries to access auth pages, send them to dashboard.
  if (req.auth && isAuthPage) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  // If no valid session exists (including stale/corrupt JWT cookies), redirect to login
  // and clear the bad cookie so the user gets a fresh start.
  if (!req.auth && isProtectedPage) {
    const loginUrl = new URL("/login", req.url);
    const res = NextResponse.redirect(loginUrl);
    // Clear both the development and production (Secure-prefixed) session cookies
    res.cookies.delete("authjs.session-token");
    res.cookies.delete("__Secure-authjs.session-token");
    return res;
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/dashboard/:path*", "/profile/:path*", "/login", "/register"],
};
