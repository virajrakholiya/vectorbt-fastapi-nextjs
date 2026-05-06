/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        border: "var(--border)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        success: "var(--success)",
        danger: "var(--danger)",
        warning: "var(--warning)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-in-out",
        "slide-up": "slideUp 0.4s ease-out",
        "pulse-slow": "pulse 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(12px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      boxShadow: {
        glow: "0 0 24px -4px rgba(59, 130, 246, 0.4)",
        "glow-success": "0 0 24px -4px rgba(34, 197, 94, 0.35)",
        "glow-danger": "0 0 24px -4px rgba(239, 68, 68, 0.35)",
      },
    },
  },
  plugins: [],
};
