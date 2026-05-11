import { CheckCircle2 } from "lucide-react";

const BUILDING_TYPES = ["Residential", "Commercial", "Industrial", "Renovation"];

export default function BuildingTypesSection() {
  return (
    <section className="relative py-12">
      {/* Divider */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />

      <div className="max-w-4xl mx-auto px-6">
        <p className="text-center text-sm font-medium text-zinc-500 mb-6 uppercase tracking-widest">
          Supported Project Types
        </p>
        <div className="flex flex-wrap gap-4 justify-center">
          {BUILDING_TYPES.map((t) => (
            <div
              key={t}
              className="group flex items-center gap-2.5 bg-zinc-900/40 hover:bg-zinc-800/80 border border-zinc-800/60 hover:border-blue-500/30 rounded-full px-5 py-2.5 transition-all duration-300 cursor-default backdrop-blur-sm shadow-sm hover:shadow-blue-500/10 hover:-translate-y-0.5"
            >
              <CheckCircle2 className="w-4 h-4 text-emerald-500/80 group-hover:text-emerald-400 transition-colors" />
              <span className="text-sm font-medium text-zinc-400 group-hover:text-zinc-200 transition-colors">
                {t}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
