const STEPS = [
  { num: "01", title: "Describe Your Project", body: "Enter building type, floor count, floor areas, and construction details." },
  { num: "02", title: "AI Analysis", body: "Our pipeline runs quantity take-off, LLM generation, and BSR matching automatically." },
  { num: "03", title: "Review & Download", body: "Inspect the full BOQ, confidence score, and category breakdown; download the Excel report." },
];

export default function HowItWorksSection() {
  return (
    <section className="py-24 px-6 max-w-6xl mx-auto relative">
      <div className="text-center mb-16">
        <h2 className="text-3xl font-bold text-zinc-100 mb-4">How It Works</h2>
        <p className="text-zinc-400 max-w-xl mx-auto">
          A seamless pipeline from project description to a professional, BSR-matched Bill of Quantities.
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-8 relative">
        {/* Connecting Line (desktop only) */}
        <div className="hidden md:block absolute top-12 left-[16%] right-[16%] h-px bg-gradient-to-r from-blue-500/0 via-blue-500/30 to-blue-500/0" />

        {STEPS.map((s, i) => (
          <div key={s.num} className="relative group text-center">
            {/* Step Number Circle */}
            <div className="mx-auto w-24 h-24 mb-6 rounded-full bg-zinc-900/80 border border-zinc-800 flex items-center justify-center text-4xl font-black text-transparent bg-clip-text bg-gradient-to-br from-zinc-100 to-zinc-600 shadow-xl shadow-black/20 group-hover:border-blue-500/40 group-hover:shadow-blue-500/10 transition-all duration-300 backdrop-blur-sm relative z-10">
              {s.num}
            </div>
            
            <h3 className="text-lg font-semibold text-zinc-100 mb-3 group-hover:text-blue-400 transition-colors">
              {s.title}
            </h3>
            <p className="text-zinc-400 text-sm leading-relaxed max-w-xs mx-auto">
              {s.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
