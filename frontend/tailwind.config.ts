import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#EFF6FF",
          500: "#3B82F6",
          600: "#1A56DB",
        },
        neutral: {
          50: "#F9FAFB",
          100: "#F3F4F6",
          400: "#9CA3AF",
          600: "#4B5563",
          900: "#111827",
        },
        danger: "#DC2626",
        warning: "#F59E0B",
        success: "#10B981",
        info: "#6366F1",
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        full: "9999px",
      },
      spacing: {
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
      },
      fontSize: {
        display: ["34px", { lineHeight: "41px", fontWeight: "700" }],
        h1: ["28px", { lineHeight: "34px", fontWeight: "600" }],
        h2: ["22px", { lineHeight: "28px", fontWeight: "600" }],
        h3: ["17px", { lineHeight: "22px", fontWeight: "600" }],
        body: ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        caption: ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      fontFamily: {
        sans: [
          '"Inter"',
          '"SF Pro Display"',
          "-apple-system",
          "BlinkMacSystemFont",
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
        modal:
          "0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04)",
        fab: "0 4px 12px rgba(26,86,219,0.35)",
      },
      animation: {
        "skeleton-pulse": "skeleton-pulse 1.5s ease-in-out infinite",
        "spin-slow": "spin 2s linear infinite",
        "fade-in": "fade-in 200ms ease-out",
        "slide-up": "slide-up 300ms ease-out",
      },
      keyframes: {
        "skeleton-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
