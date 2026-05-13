import type { Metadata } from "next";
import { Inter, Geist } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import Providers from "@/components/Providers";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://localhost:3000";

export const metadata: Metadata = {
  title: {
    template: "%s | CostEstimate AI",
    default: "CostEstimate AI",
  },
  description:
    "AI-powered construction cost estimation platform. Generate Bills of Quantities, match BSR rates, and produce detailed project cost reports.",
  metadataBase: new URL(APP_URL),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: APP_URL,
    siteName: "CostEstimate AI",
    title: "CostEstimate AI — AI-powered Construction Cost Estimation",
    description:
      "Generate accurate Bills of Quantities and cost estimates for construction projects using AI and BSR rate matching.",
  },
  twitter: {
    card: "summary_large_image",
    title: "CostEstimate AI",
    description: "AI-powered construction cost estimation.",
  },
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("h-full", inter.className, "font-sans", geist.variable)}>
      <body className="bg-foreground h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
