import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  // If no valid session exists (including stale/corrupt JWT cookies), redirect to login
  // and clear the bad cookie so the user gets a fresh start.
  if (!req.auth) {
    const loginUrl = new URL("/login", req.url);
    const res = NextResponse.redirect(loginUrl);
    // Clear both the development and production (Secure-prefixed) session cookies
    res.cookies.delete("authjs.session-token");
    res.cookies.delete("__Secure-authjs.session-token");
    return res;
  }
});

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/profile/:path*",
  ],
};
