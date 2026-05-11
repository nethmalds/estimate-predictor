import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { apiClient } from "@/lib/api-client";
import type { LoginResponse } from "@/types/auth";

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
        } catch {
          return null;
        }
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 }, // 7 days
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
