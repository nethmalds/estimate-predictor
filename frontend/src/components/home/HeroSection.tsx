import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function HeroSection() {
  return (
    <section className="relative mx-auto max-w-4xl overflow-hidden px-6 pt-32 pb-24 text-center">
      {/* Ambient background glows */}
      <div
        className="pointer-events-none absolute top-1/2 left-1/2 -z-10 h-[400px] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600/15 blur-[120px]"
        aria-hidden="true"
      />

      {/* Badge */}
      <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1.5 shadow-sm shadow-blue-500/10 backdrop-blur-sm">
        <span className="flex h-2 w-2 animate-pulse rounded-full bg-blue-400" />
        <span className="text-xs font-semibold tracking-wide text-blue-300 uppercase">
          Sri Lanka Construction Cost Intelligence
        </span>
      </div>

      {/* Headline */}
      <h1 className="mb-6 text-5xl leading-[1.1] font-extrabold tracking-tight text-zinc-100 sm:text-6xl">
        Generate Accurate BOQ Estimates{" "}
        <span className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          in Minutes
        </span>
      </h1>

      {/* Subheadline */}
      <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-zinc-400 sm:text-xl">
        Describe your project and our AI generates a full Bill of Quantities matched against
        official BSR rates — no quantity surveyor required.
      </p>

      {/* CTA Buttons */}
      <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
        <Button
          asChild
          size="lg"
          className="h-12 w-full rounded-xl bg-blue-600 px-8 text-base font-semibold text-white shadow-lg shadow-blue-600/25 transition-all duration-200 hover:-translate-y-0.5 hover:bg-blue-500 hover:shadow-blue-500/30 sm:w-auto"
        >
          <Link href="/login">
            Start Free Estimate <ChevronRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
        {/*   <Button
          asChild
          variant="outline"
          size="lg"
          className="w-full sm:w-auto h-12 px-8 bg-zinc-900/50 hover:bg-zinc-800 border-zinc-700/80 text-zinc-200 font-semibold rounded-xl backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 text-base"
        >
          <Link href="/login">View Dashboard</Link>
        </Button> */}
      </div>
    </section>
  );
}
