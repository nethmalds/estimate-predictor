import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

export const metadata: Metadata = {
  title: "Sign In",
  description: "Sign in or create a CostEstimate AI account.",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dark flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* Ambient background glows */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div
          className="absolute -top-40 -left-40 h-125 w-125 rounded-full bg-blue-600/10 blur-[120px]"
          aria-hidden="true"
        />
        <div
          className="absolute -right-40 -bottom-40 h-125 w-125 rounded-full bg-blue-500/8 blur-[120px]"
          aria-hidden="true"
        />
      </div>

      <Navbar />

      <main className="relative flex flex-1 items-center justify-center px-4 py-12 pt-28">
        {children}
      </main>

      <Footer />
    </div>
  );
}
