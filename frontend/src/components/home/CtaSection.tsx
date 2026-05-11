import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function CtaSection() {
  return (
    <section className="py-24 px-6 relative overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 bg-blue-900/10" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-3xl h-[300px] bg-blue-600/20 blur-[100px] rounded-full pointer-events-none" />

      <div className="relative z-10 max-w-3xl mx-auto bg-zinc-900/80 border border-zinc-800 rounded-3xl p-10 sm:p-14 text-center backdrop-blur-md shadow-2xl shadow-black/40">
        <h2 className="text-3xl sm:text-4xl font-bold mb-4 text-zinc-100">
          Ready to estimate your project?
        </h2>
        <p className="text-zinc-400 text-lg mb-8 max-w-xl mx-auto">
          Join homeowners and contractors using AI to generate accurate, instant construction estimates.
        </p>
        <Button
          asChild
          size="lg"
          className="h-12 px-8 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-600/25 transition-all duration-200 hover:shadow-blue-500/30 hover:-translate-y-0.5 text-base"
        >
          <Link href="/register">
            Create your free account <ArrowRight className="w-4 h-4 ml-2" />
          </Link>
        </Button>
        <p className="mt-6 text-sm text-zinc-500">
          No credit card required. Results in under 2 minutes.
        </p>
      </div>
    </section>
  );
}
