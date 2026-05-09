export { auth as middleware } from "@/auth";

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/estimates/:path*",
    "/estimate/:path*",
    "/profile/:path*",
  ],
};
