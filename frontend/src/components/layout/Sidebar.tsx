"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, LayoutDashboard, FileText, Plus, LogOut } from "lucide-react";
import { signOut } from "next-auth/react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

interface AppSidebarProps {
  user: {
    name?: string | null;
    email?: string | null;
    role?: string | null;
  };
}

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/estimates", label: "All Estimates", icon: FileText },
];

export function AppSidebar({ user }: AppSidebarProps) {
  const pathname = usePathname();

  const initials = (user.name ?? "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Sidebar collapsible="none" className="sticky top-0 px-1 h-svh">
      {/* Brand */}
      <SidebarHeader className="border-b border-border px-4 py-8">
        <Link href="/" className="flex items-center gap-3">
          <Building2 className="w-6 h-6 text-blue-400 shrink-0" />
          <span className="font-bold text-base tracking-tight">CostEstimate AI</span>
        </Link>
      </SidebarHeader>

      <SidebarContent className="pt-4">
        {/* New Estimate CTA */}
        <div className="px-3 mb-4">
          <Button asChild className="w-full">
            <Link href="/dashboard/estimate/new">
              <Plus className="w-4 h-4" /> New Estimate
            </Link>
          </Button>
        </div>

        <SidebarGroup>
          <SidebarMenu>
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive =
                pathname === href ||
                (href !== "/dashboard" && pathname.startsWith(href));
              return (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton asChild isActive={isActive} className="my-1">
                    <Link href={href}>
                      <Icon className="w-4 h-4" />
                      {label}
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      {/* User footer */}
      <SidebarFooter className="border-t border-border p-3">
        <div className="flex items-center gap-3">
          <Avatar size="sm">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user.name}</p>
            <p className="text-xs text-muted-foreground capitalize truncate">
              {user.role?.replace("_", " ")}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label="Log out"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
