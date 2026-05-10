"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, LayoutDashboard, FileText, Plus, LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

interface SidebarProps {
  user: {
    name?: string | null;
    email?: string | null;
    role?: string | null;
  };
}

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname();

  const links = [
    { href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-5 h-5" /> },
    { href: "/dashboard/estimates", label: "All Estimates", icon: <FileText className="w-5 h-5" /> },
  ];

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col h-screen fixed left-0 top-0">
      {/* Brand */}
      <div className="h-16 flex items-center px-6 border-b border-zinc-800">
        <Link href="/dashboard" className="flex items-center gap-3">
          <Building2 className="w-6 h-6 text-blue-400" />
          <span className="font-bold text-lg text-zinc-100 tracking-tight">CostEstimate AI</span>
        </Link>
      </div>

      {/* Main Nav */}
      <nav className="flex-1 px-4 py-6 space-y-2">
        <Link
          href="/dashboard/estimate/new"
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors mb-6"
        >
          <Plus className="w-4 h-4" /> New Estimate
        </Link>

        {links.map((link) => {
          // Exact match or starting with path for active state
          const isActive = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-500/10 text-blue-400"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
              }`}
            >
              {link.icon}
              {link.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer / User Profile */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center justify-between">
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-medium text-zinc-100 truncate">{user.name}</span>
            <span className="text-xs text-zinc-500 capitalize">{user.role?.replace("_", " ")}</span>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="p-2 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
