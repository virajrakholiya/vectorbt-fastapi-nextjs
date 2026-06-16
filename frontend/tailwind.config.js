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
        "border-strong": "var(--border-strong)",
        card: "var(--card)",
        "card-elevated": "var(--card-elevated)",
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
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out both",
        "slide-up": "slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(14px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,176,0,0.25), 0 0 28px -6px rgba(255, 176, 0, 0.55)",
        "glow-success": "0 0 24px -6px rgba(58, 208, 122, 0.45)",
        "glow-danger": "0 0 24px -6px rgba(255, 77, 77, 0.45)",
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 20px 50px -30px rgba(0,0,0,0.9)",
      },
    },
  },
  plugins: [],
};
