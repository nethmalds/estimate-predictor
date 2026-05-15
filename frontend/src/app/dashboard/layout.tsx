import type { Metadata } from "next";
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { AppSidebar } from "@/components/layout/Sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: {
    template: "%s | CostEstimate AI",
    default: "Dashboard | CostEstimate AI",
  },
  robots: { index: false, follow: false },
};

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  return (
    <div>
      <SidebarProvider>
        <AppSidebar user={session.user} />
        <SidebarInset className="bg-background text-foreground">
          <main className="bg-background min-h-screen pt-15">{children}</main>
        </SidebarInset>
        <Toaster richColors position="top-right" />
      </SidebarProvider>
    </div>
  );
}
