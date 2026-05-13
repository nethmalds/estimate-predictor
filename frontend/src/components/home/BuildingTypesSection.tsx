import { CheckCircle2 } from "lucide-react";

const BUILDING_TYPES = ["Residential", "Commercial", "Industrial", "Renovation"];

export default function BuildingTypesSection() {
  return (
    <section className="relative py-12">
      {/* Divider */}
      <div className="absolute top-0 left-1/2 h-px w-full max-w-4xl -translate-x-1/2 bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />

      <div className="mx-auto max-w-4xl px-6">
        <p className="mb-6 text-center text-sm font-medium tracking-widest text-zinc-500 uppercase">
          Supported Project Types
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          {BUILDING_TYPES.map((t) => (
            <div
              key={t}
              className="group flex cursor-default items-center gap-2.5 rounded-full border border-zinc-800/60 bg-zinc-900/40 px-5 py-2.5 shadow-sm backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-blue-500/30 hover:bg-zinc-800/80 hover:shadow-blue-500/10"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-500/80 transition-colors group-hover:text-emerald-400" />
              <span className="text-sm font-medium text-zinc-400 transition-colors group-hover:text-zinc-200">
                {t}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
