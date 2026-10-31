import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { navy: { DEFAULT: "#0B1B33", 800: "#12294a", 700: "#1b3560" }, canvas: "#F7F8FA" },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-jbmono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { md: "4px", lg: "4px" },
      boxShadow: { card: "0 1px 2px rgba(15,23,42,0.05), 0 1px 1px rgba(15,23,42,0.03)" },
    },
  },
  plugins: [],
};
export default config;
