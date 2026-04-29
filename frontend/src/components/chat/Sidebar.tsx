"use client";

import { ReactNode } from "react";
import { SquarePen, Search, Calculator, Clock } from "lucide-react";

import {
  Sidebar as UiSidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";

interface SidebarProps {
  onNewChat?: () => void;
}

function NavItem({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 w-full px-3 py-3 rounded-lg text-sm text-zinc-400 font-normal transition-colors text-left hover:bg-white/5 hover:text-zinc-100"
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="text-[11px] font-medium text-zinc-600 uppercase tracking-wider px-3 pt-7 pb-3">
      {label}
    </p>
  );
}

function HistoryItem({ icon, label }: { icon?: ReactNode; label: string }) {
  return (
    <button className="flex items-center gap-3 w-full px-3 py-3 rounded-lg text-sm text-zinc-500 transition-colors text-left hover:bg-white/5 hover:text-zinc-300">
      {icon}
      <span className="truncate">{label}</span>
    </button>
  );
}

export function Sidebar({ onNewChat }: SidebarProps) {
  const handleNewChatClick = () => {
    if (onNewChat) {
      onNewChat();
      return;
    }

    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("chat:new"));
    }
  };

  return (
    <UiSidebar collapsible="none" variant="sidebar" className=" bg-foreground text-zinc-100">
      <SidebarHeader className="px-4 pt-6 pb-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-zinc-200 tracking-tight">BOQ Assistant</span>
          <button
            onClick={handleNewChatClick}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-100 hover:bg-white/5 transition-colors"
            aria-label="New chat"
          >
            <SquarePen className="w-4 h-4" />
          </button>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <div className="space-y-2">
          <NavItem icon={<Search className="w-4 h-4" />} label="Search" />
          <NavItem icon={<Calculator className="w-4 h-4" />} label="BOQ Tool" />
        </div>

        <SectionLabel label="Recent" />
        <HistoryItem icon={<Clock className="w-3.5 h-3.5 shrink-0 text-zinc-600" />} label="Project estimation session" />
        <HistoryItem icon={<Clock className="w-3.5 h-3.5 shrink-0 text-zinc-600" />} label="BOQ generation" />
        <HistoryItem icon={<Clock className="w-3.5 h-3.5 shrink-0 text-zinc-600" />} label="Floor plan analysis" />
        <HistoryItem icon={<Clock className="w-3.5 h-3.5 shrink-0 text-zinc-600" />} label="Material cost breakdown" />
        <HistoryItem icon={<Clock className="w-3.5 h-3.5 shrink-0 text-zinc-600" />} label="Site survey estimate" />
      </SidebarContent>

      <SidebarFooter className="px-3 py-3 border-t border-white/[0.06]">
        <button className="flex items-center gap-3 w-full px-2 py-2 rounded-lg hover:bg-white/5 transition-colors">
          <div className="w-7 h-7 rounded-full bg-[#e8a130] flex items-center justify-center text-xs font-bold text-white shrink-0">
            N
          </div>
          <div className="text-left min-w-0">
            <div className="text-sm text-zinc-300 font-medium leading-tight">User</div>
            <div className="text-[11px] text-zinc-600 leading-tight">Free plan</div>
          </div>
        </button>
      </SidebarFooter>
    </UiSidebar>
  );
}
