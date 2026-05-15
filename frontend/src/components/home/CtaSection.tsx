import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function CtaSection() {
  return (
    <section className="relative overflow-hidden px-6 py-24">
      {/* Background elements */}
      <div className="absolute inset-0 bg-blue-900/10" aria-hidden="true" />
      <div
        className="pointer-events-none absolute top-1/2 left-1/2 h-[300px] w-full max-w-3xl -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600/20 blur-[100px]"
        aria-hidden="true"
      />

      <div className="relative z-10 mx-auto max-w-3xl rounded-3xl border border-zinc-200 bg-white/80 p-10 text-center shadow-2xl shadow-zinc-200/40 backdrop-blur-md sm:p-14">
        <h2 className="mb-4 text-3xl font-bold text-zinc-900 sm:text-4xl">
          Ready to estimate your project?
        </h2>
        <p className="mx-auto mb-8 max-w-xl text-lg text-zinc-600">
          Join homeowners and contractors using AI to generate accurate, instant construction
          estimates.
        </p>
        <Button
          asChild
          size="lg"
          className="h-12 rounded-xl bg-blue-600 px-8 text-base font-semibold text-white shadow-lg shadow-blue-600/25 transition-all duration-200 hover:-translate-y-0.5 hover:bg-blue-500 hover:shadow-blue-500/30"
        >
          <Link href="/register">
            Create your free account <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
        <p className="mt-6 text-sm text-zinc-500">
          No credit card required. Results in under 2 minutes.
        </p>
      </div>
    </section>
  );
}
