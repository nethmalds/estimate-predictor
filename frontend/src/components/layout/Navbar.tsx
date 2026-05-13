import Link from "next/link";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Navbar() {
  return (
    <header className="fixed inset-x-0 top-0 z-50">
      {/* Glass backdrop */}
      <div className="absolute inset-0 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-md" />

      {/* Content */}
      <nav className="relative mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="group flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10 transition-all duration-200 group-hover:border-blue-500/30 group-hover:bg-blue-500/15">
            <Building2 className="h-4 w-4 text-blue-400" />
          </div>
          <span className="text-base font-bold tracking-tight text-zinc-100">
            CostEstimate<span className="text-blue-400">AI</span>
          </span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="text-zinc-400 transition-all duration-200 hover:bg-zinc-800/60 hover:text-zinc-100"
          >
            <Link href="/login">Sign in</Link>
          </Button>
          <Button
            size="sm"
            asChild
            className="rounded-lg bg-blue-600 text-white shadow-md shadow-blue-600/25 transition-all duration-200 hover:-translate-y-0.5 hover:bg-blue-500 hover:shadow-blue-500/30"
          >
            <Link href="/register">Get started</Link>
          </Button>
        </div>
      </nav>
    </header>
  );
}
