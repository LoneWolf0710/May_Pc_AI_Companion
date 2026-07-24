/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#1a1720",
          dark: "#0c0a0f",
          elevated: "#242030",
          hover: "#2e2a3a",
        },
        border: {
          DEFAULT: "#2e2a3a",
          subtle: "#242030",
          hover: "#3e3a4a",
        },
        accent: {
          DEFAULT: "#818cf8",
          subtle: "#818cf815",
          soft: "#818cf830",
          glow: "#818cf840",
        },
        lavender: {
          DEFAULT: "#c084fc",
          subtle: "#c084fc15",
          soft: "#c084fc30",
        },
        emerald: {
          DEFAULT: "#34d399",
          subtle: "#34d39915",
        },
        amber: {
          DEFAULT: "#fbbf24",
          subtle: "#fbbf2415",
        },
        text: {
          DEFAULT: "#f0f0f5",
          secondary: "#9090a8",
          muted: "#55556a",
        },
        danger: {
          DEFAULT: "#f87171",
          subtle: "#f8717115",
        },
        success: {
          DEFAULT: "#34d399",
          subtle: "#34d39915",
        },
        warning: {
          DEFAULT: "#fbbf24",
          subtle: "#fbbf2415",
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
        glow: "0 0 30px #818cf815, 0 0 60px #818cf808",
        "glow-strong": "0 0 20px #818cf830, 0 0 40px #818cf820",
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      backgroundImage: {
        "mesh-gradient":
          "radial-gradient(circle at 30% 30%, #818cf820 0%, #c084fc10 50%, transparent 80%)",
      },
    },
  },
  plugins: [],
};
