import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verify Email | CostEstimate AI",
  description: "Verify your CostEstimate AI email address.",
};

export default function VerifyEmailLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
