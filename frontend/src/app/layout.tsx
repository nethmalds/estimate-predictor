import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Project Estimation Assistant",
  description: "AI-powered construction project estimation and bill of quantities generator.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.className} h-full`} style={{ background: "#212121" }}>
      <body className="h-full" style={{ background: "#212121" }}>
        {children}
      </body>
    </html>
  );
}
