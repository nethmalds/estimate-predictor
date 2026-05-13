import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Forgot Password | CostEstimate AI",
  description: "Reset your CostEstimate AI account password.",
};

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
