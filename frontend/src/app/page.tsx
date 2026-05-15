import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import HeroSection from "@/components/home/HeroSection";
import BuildingTypesSection from "@/components/home/BuildingTypesSection";
import HowItWorksSection from "@/components/home/HowItWorksSection";
import FeaturesSection from "@/components/home/FeaturesSection";
import CtaSection from "@/components/home/CtaSection";

export const metadata: Metadata = {
  title: "AI-powered Construction Cost Estimation",
  description:
    "Upload your floorplan, answer a few questions, and get a full Bill of Quantities with BSR-matched rates in minutes.",
  openGraph: {
    title: "CostEstimate AI — AI-powered Construction Cost Estimation",
    description:
      "Upload your floorplan, answer a few questions, and get a full Bill of Quantities with BSR-matched rates in minutes.",
  },
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background pt-16 font-sans text-foreground">
      <Navbar />
      <HeroSection />
      <BuildingTypesSection />
      <HowItWorksSection />
      <FeaturesSection />
      <CtaSection />
      <Footer />
    </main>
  );
}
