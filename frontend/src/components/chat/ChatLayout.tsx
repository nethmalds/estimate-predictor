"use client";

import { ReactNode } from "react";

import { Sidebar } from "@/components/chat/Sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";

interface ChatLayoutProps {
  children: ReactNode;
}

export function ChatLayout({ children }: ChatLayoutProps) {
  return (
    <SidebarProvider defaultOpen className="h-screen overflow-hidden">
      <Sidebar />
      {children}
    </SidebarProvider>
  );
}
