import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function HeroSection() {
  return (
    <section className="relative pt-32 pb-24 px-6 text-center max-w-4xl mx-auto overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl h-[400px] bg-blue-600/15 blur-[120px] rounded-full pointer-events-none -z-10" />

      {/* Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-8 rounded-full bg-blue-500/10 border border-blue-500/20 backdrop-blur-sm shadow-sm shadow-blue-500/10">
        <span className="flex w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
        <span className="text-xs font-semibold tracking-wide text-blue-300 uppercase">
          Sri Lanka Construction Cost Intelligence
        </span>
      </div>

      {/* Headline */}
      <h1 className="text-5xl sm:text-6xl font-extrabold leading-[1.1] mb-6 tracking-tight text-zinc-100">
        Generate Accurate BOQ Estimates{" "}
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
          in Minutes
        </span>
      </h1>

      {/* Subheadline */}
      <p className="text-zinc-400 text-lg sm:text-xl mb-10 max-w-2xl mx-auto leading-relaxed">
        Describe your project and our AI generates a full Bill of Quantities matched against official BSR rates — no quantity surveyor required.
      </p>

      {/* CTA Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
        <Button
          asChild
          size="lg"
          className="w-full sm:w-auto h-12 px-8 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-600/25 transition-all duration-200 hover:shadow-blue-500/30 hover:-translate-y-0.5 text-base"
        >
          <Link href="/login">
            Start Free Estimate <ChevronRight className="w-4 h-4 ml-1" />
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
