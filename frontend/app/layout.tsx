import "./globals.css";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jbmono", display: "swap" });

export const metadata = {
  title: "AD Trace - aerospace regulatory intelligence, verified",
  description: "Search FAA Airworthiness Directive proposals and trace every answer to the original Federal Register source.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body>
        {children}
      </body>
    </html>
  );
}
