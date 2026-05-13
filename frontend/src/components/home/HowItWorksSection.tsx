const STEPS = [
  {
    num: "01",
    title: "Describe Your Project",
    body: "Enter building type, floor count, floor areas, and construction details.",
  },
  {
    num: "02",
    title: "AI Analysis",
    body: "Our pipeline runs quantity take-off, LLM generation, and BSR matching automatically.",
  },
  {
    num: "03",
    title: "Review & Download",
    body: "Inspect the full BOQ, confidence score, and category breakdown; download the Excel report.",
  },
];

export default function HowItWorksSection() {
  return (
    <section className="relative mx-auto max-w-6xl px-6 py-24">
      <div className="mb-16 text-center">
        <h2 className="mb-4 text-3xl font-bold text-zinc-100">How It Works</h2>
        <p className="mx-auto max-w-xl text-zinc-400">
          A seamless pipeline from project description to a professional, BSR-matched Bill of
          Quantities.
        </p>
      </div>

      <div className="relative grid gap-8 md:grid-cols-3">
        {/* Connecting Line (desktop only) */}
        <div className="absolute top-12 right-[16%] left-[16%] hidden h-px bg-gradient-to-r from-blue-500/0 via-blue-500/30 to-blue-500/0 md:block" />

        {STEPS.map((s, i) => (
          <div key={s.num} className="group relative text-center">
            {/* Step Number Circle */}
            <div className="relative z-10 mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/80 bg-gradient-to-br from-zinc-100 to-zinc-600 bg-clip-text text-4xl font-black text-transparent shadow-xl shadow-black/20 backdrop-blur-sm transition-all duration-300 group-hover:border-blue-500/40 group-hover:shadow-blue-500/10">
              {s.num}
            </div>

            <h3 className="mb-3 text-lg font-semibold text-zinc-100 transition-colors group-hover:text-blue-400">
              {s.title}
            </h3>
            <p className="mx-auto max-w-xs text-sm leading-relaxed text-zinc-400">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
