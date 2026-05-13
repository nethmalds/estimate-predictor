import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "New Estimate | CostEstimate AI",
  description: "Create a new construction cost estimate.",
};

export default function NewEstimateLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
