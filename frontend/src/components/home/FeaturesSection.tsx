import { Cpu, FileSpreadsheet, BarChart3, Building2 } from "lucide-react";

const FEATURES = [
  {
    icon: <Cpu className="w-6 h-6 text-blue-400" />,
    title: "AI-Powered BOQ Generation",
    desc: "GPT-class LLMs generate a complete Bill of Quantities with 120+ line items tailored to your project.",
  },
  {
    icon: <Building2 className="w-6 h-6 text-blue-400" />,
    title: "Floor Plan Analysis",
    desc: "Upload floor plan images and our computer-vision engine automatically extracts room counts and areas.",
  },
  {
    icon: <BarChart3 className="w-6 h-6 text-blue-400" />,
    title: "BSR Rate Matching",
    desc: "Every item is matched against the Sri Lanka Schedule of Rates database for accurate cost benchmarks.",
  },
  {
    icon: <FileSpreadsheet className="w-6 h-6 text-blue-400" />,
    title: "Instant Excel Reports",
    desc: "Download a professional multi-sheet Excel report — Summary, BOQ table, and cost breakdown — in seconds.",
  },
];

export default function FeaturesSection() {
  return (
    <section className="py-24 px-6 bg-zinc-900/30 border-y border-zinc-800/60 relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/5 via-zinc-950/0 to-zinc-950/0 pointer-events-none" />
      
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-zinc-100 mb-4">Enterprise-Grade Features</h2>
          <p className="text-zinc-400 max-w-xl mx-auto">
            Everything you need to produce accurate, professional construction estimates without the manual effort.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-8 backdrop-blur-sm transition-all duration-300 hover:bg-zinc-800/80 hover:border-zinc-700/80 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/20"
            >
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-blue-500/20 transition-all duration-300">
                {f.icon}
              </div>
              <h3 className="text-xl font-semibold text-zinc-100 mb-3">{f.title}</h3>
              <p className="text-zinc-400 leading-relaxed text-sm">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
