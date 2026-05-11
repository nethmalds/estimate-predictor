import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import HeroSection from "@/components/home/HeroSection";
import BuildingTypesSection from "@/components/home/BuildingTypesSection";
import HowItWorksSection from "@/components/home/HowItWorksSection";
import FeaturesSection from "@/components/home/FeaturesSection";
import CtaSection from "@/components/home/CtaSection";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pt-16">
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
