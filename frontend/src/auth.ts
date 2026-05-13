import NextAuth, { CredentialsSignin } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { apiClient } from "@/lib/api-client";
import { ApiError } from "@/types/api";
import type { LoginResponse } from "@/types/auth";

// NEW: H11 — typed error so the login page can detect unverified-email rejections
class EmailNotVerifiedError extends CredentialsSignin {
  code = "email_not_verified" as const;
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  trustHost: true,
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      authorize: async (credentials) => {
        try {
          const user = await apiClient.post<LoginResponse>("/api/auth/login", {
            email: credentials?.email,
            password: credentials?.password,
          });

          if (!user?.id) return null;

          return {
            id: user.id,
            name: user.name,
            email: user.email,
            role: user.role,
            accessToken: user.access_token,
          };
        } catch (err) {
          // NEW: H11 — surface email-not-verified as a typed error so the login
          // page can show a targeted message with a "Resend verification" link
          if (
            err instanceof ApiError &&
            err.status === 403 &&
            err.message === "email_not_verified"
          ) {
            throw new EmailNotVerifiedError();
          }
          return null;
        }
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 24 * 60 * 60 }, // 1 day — matches backend JWT TTL
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = (user as { role?: string }).role;
        token.accessToken = (user as { accessToken?: string }).accessToken;
      }
      return token;
    },
    session({ session, token }) {
      if (token) {
        session.user.id = token.id as string;
        (session.user as { role?: string }).role = token.role as string;
        (session.user as { accessToken?: string }).accessToken = token.accessToken as string;
      }
      return session;
    },
  },
  pages: { signIn: "/login", error: "/login" },
});
