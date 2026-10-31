import "@/components/landing/landing.css";
import type { ReactNode } from "react";

// Marketing routes: no app sidebar, just the landing page.
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
