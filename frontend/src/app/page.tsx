import Link from "next/link";
import { Building2, Cpu, FileSpreadsheet, BarChart3, CheckCircle2, ChevronRight } from "lucide-react";

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

const STEPS = [
  { num: "01", title: "Describe Your Project", body: "Enter building type, floor count, floor areas, and construction details." },
  { num: "02", title: "AI Analysis", body: "Our pipeline runs quantity take-off, LLM generation, and BSR matching automatically." },
  { num: "03", title: "Review & Download", body: "Inspect the full BOQ, confidence score, and category breakdown; download the Excel report." },
];

const BUILDING_TYPES = ["Residential", "Commercial", "Industrial"];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <nav className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <span className="font-bold text-lg tracking-tight text-zinc-100">
          <Building2 className="inline w-5 h-5 mr-2 text-blue-400" />
          CostEstimate <span className="text-blue-400">AI</span>
        </span>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors">
            Sign in
          </Link>
          <Link
            href="/register"
            className="text-sm px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Register
          </Link>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 text-center max-w-3xl mx-auto">
        <span className="inline-block text-xs font-semibold tracking-widest text-blue-400 uppercase mb-4 border border-blue-400/30 rounded-full px-3 py-1">
          Sri Lanka Construction Cost Intelligence
        </span>
        <h1 className="text-4xl sm:text-5xl font-bold leading-tight mb-6">
          Generate Accurate BOQ Estimates{" "}
          <span className="text-blue-400">in Minutes</span>
        </h1>
        <p className="text-zinc-400 text-lg mb-10 max-w-xl mx-auto">
          Describe your project and our AI generates a full Bill of Quantities matched against official BSR rates — no quantity surveyor required.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/login"
            className="flex items-center justify-center gap-2 px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-base transition-colors"
          >
            Start Free Estimate <ChevronRight className="w-4 h-4" />
          </Link>
          <Link
            href="/login"
            className="flex items-center justify-center gap-2 px-8 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg font-semibold text-base transition-colors"
          >
            View Dashboard
          </Link>
        </div>
      </section>

      {/* ── Building types ───────────────────────────────────────────── */}
      <section className="py-8 border-t border-zinc-800">
        <div className="max-w-4xl mx-auto px-6 flex flex-wrap gap-3 justify-center">
          {BUILDING_TYPES.map((t) => (
            <span
              key={t}
              className="flex items-center gap-2 text-sm text-zinc-300 bg-zinc-800 border border-zinc-700 rounded-full px-4 py-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-green-400" /> {t}
            </span>
          ))}
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section className="py-20 px-6 max-w-5xl mx-auto">
        <h2 className="text-2xl font-bold text-center mb-12">How It Works</h2>
        <div className="grid sm:grid-cols-3 gap-8">
          {STEPS.map((s) => (
            <div key={s.num} className="text-center">
              <div className="text-5xl font-black text-zinc-800 mb-3">{s.num}</div>
              <h3 className="font-semibold text-zinc-100 mb-2">{s.title}</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────────────── */}
      <section className="py-20 px-6 bg-zinc-900 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-12">Features</h2>
          <div className="grid sm:grid-cols-2 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-zinc-950 border border-zinc-800 rounded-xl p-6">
                <div className="mb-3">{f.icon}</div>
                <h3 className="font-semibold text-zinc-100 mb-1">{f.title}</h3>
                <p className="text-zinc-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 text-center max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold mb-4">Ready to estimate your project?</h2>
        <p className="text-zinc-400 mb-8">No account required to start. Results in under 2 minutes.</p>
        <Link
          href="/login"
          className="inline-flex items-center gap-2 px-10 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-base transition-colors"
        >
          Start Free Estimate <ChevronRight className="w-4 h-4" />
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="border-t border-zinc-800 py-8 px-6 text-center text-zinc-500 text-sm">
        <p>© {new Date().getFullYear()} CostEstimate AI — AI-Assisted Construction Cost Estimation for Sri Lanka</p>
      </footer>
    </main>
  );
}
