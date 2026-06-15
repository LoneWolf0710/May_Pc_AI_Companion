/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#1A1A1A",
          dark: "#0D0D0D",
          elevated: "#252525",
          hover: "#2E2E2E",
        },
        border: {
          DEFAULT: "#2E2E2E",
          subtle: "#222222",
          hover: "#3A3A3A",
        },
        accent: {
          DEFAULT: "#06B6D4",
          subtle: "#06B6D415",
          soft: "#06B6D430",
          glow: "#06B6D440",
        },
        purple: {
          DEFAULT: "#8B5CF6",
          subtle: "#8B5CF615",
          soft: "#8B5CF630",
          glow: "#8B5CF640",
        },
        text: {
          DEFAULT: "#E5E5E5",
          secondary: "#A0A0A0",
          muted: "#666666",
        },
        danger: {
          DEFAULT: "#EF4444",
          subtle: "#EF444415",
        },
        success: {
          DEFAULT: "#4ADE80",
          subtle: "#4ADE8015",
        },
        warning: {
          DEFAULT: "#F59E0B",
          subtle: "#F59E0B15",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      borderRadius: {
        DEFAULT: "4px",
        sm: "2px",
        md: "6px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0,0,0,0.3)",
        panel: "0 4px 24px 0 rgba(0,0,0,0.5)",
        elevated: "0 8px 32px 0 rgba(0,0,0,0.6)",
        glow: "0 0 30px #06B6D415, 0 0 60px #06B6D408",
        "glow-strong": "0 0 20px #06B6D430, 0 0 40px #06B6D420",
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      backgroundImage: {
        "mesh-gradient": "radial-gradient(circle at 30% 30%, #06B6D420 0%, #8B5CF610 50%, transparent 80%)",
      },
    },
  },
  plugins: [],
};
