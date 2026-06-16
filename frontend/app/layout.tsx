import type { Metadata } from "next";
import { Archivo, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "VECTORBT // Backtesting Terminal",
  description: "Indian Stock Market Quantitative Backtesting Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${archivo.variable} ${jetbrains.variable}`}>
      <body className="bg-background text-foreground min-h-screen antialiased">
        {/* Ambient terminal backdrop: grid + amber phosphor bloom + scanlines */}
        <div className="terminal-grid" aria-hidden />
        <div className="terminal-bloom" aria-hidden />
        <div className="terminal-scanlines" aria-hidden />
        <main className="relative z-10 mx-auto max-w-[1500px] px-4 py-6 md:px-8">
          {children}
        </main>
      </body>
    </html>
  );
}
