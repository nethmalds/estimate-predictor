import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Reset Password | CostEstimate AI",
  description: "Set a new password for your CostEstimate AI account.",
};

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
