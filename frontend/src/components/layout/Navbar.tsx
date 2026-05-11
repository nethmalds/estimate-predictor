import Link from "next/link";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Navbar() {
  return (
    <header className="fixed top-0 inset-x-0 z-50">
      {/* Glass backdrop */}
      <div className="absolute inset-0 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/60" />

      {/* Content */}
      <nav className="relative max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2 group"
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 group-hover:bg-blue-500/15 group-hover:border-blue-500/30 transition-all duration-200">
            <Building2 className="w-4 h-4 text-blue-400" />
          </div>
          <span className="font-bold text-base tracking-tight text-zinc-100">
            CostEstimate<span className="text-blue-400">AI</span>
          </span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 transition-all duration-200"
          >
            <Link href="/login">Sign in</Link>
          </Button>
          <Button
            size="sm"
            asChild
            className="bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/25 hover:shadow-blue-500/30 hover:-translate-y-0.5 transition-all duration-200 rounded-lg"
          >
            <Link href="/register">Get started</Link>
          </Button>
        </div>
      </nav>
    </header>
  );
}
