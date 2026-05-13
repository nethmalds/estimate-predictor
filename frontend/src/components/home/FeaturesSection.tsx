import { Cpu, FileSpreadsheet, BarChart3, Building2 } from "lucide-react";

const FEATURES = [
  {
    icon: <Cpu className="h-6 w-6 text-blue-400" />,
    title: "AI-Powered BOQ Generation",
    desc: "GPT-class LLMs generate a complete Bill of Quantities with 120+ line items tailored to your project.",
  },
  {
    icon: <Building2 className="h-6 w-6 text-blue-400" />,
    title: "Floor Plan Analysis",
    desc: "Upload floor plan images and our computer-vision engine automatically extracts room counts and areas.",
  },
  {
    icon: <BarChart3 className="h-6 w-6 text-blue-400" />,
    title: "BSR Rate Matching",
    desc: "Every item is matched against the Sri Lanka Schedule of Rates database for accurate cost benchmarks.",
  },
  {
    icon: <FileSpreadsheet className="h-6 w-6 text-blue-400" />,
    title: "Instant Excel Reports",
    desc: "Download a professional multi-sheet Excel report — Summary, BOQ table, and cost breakdown — in seconds.",
  },
];

export default function FeaturesSection() {
  return (
    <section className="relative border-y border-zinc-800/60 bg-zinc-900/30 px-6 py-24">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/5 via-zinc-950/0 to-zinc-950/0" />

      <div className="relative z-10 mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold text-zinc-100">Enterprise-Grade Features</h2>
          <p className="mx-auto max-w-xl text-zinc-400">
            Everything you need to produce accurate, professional construction estimates without the
            manual effort.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group rounded-2xl border border-zinc-800/80 bg-zinc-900/60 p-8 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:border-zinc-700/80 hover:bg-zinc-800/80 hover:shadow-xl hover:shadow-black/20"
            >
              <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 transition-all duration-300 group-hover:scale-110 group-hover:bg-blue-500/20">
                {f.icon}
              </div>
              <h3 className="mb-3 text-xl font-semibold text-zinc-100">{f.title}</h3>
              <p className="text-sm leading-relaxed text-zinc-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
