import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VectorBT Backtesting Dashboard",
  description: "Indian Stock Market Backtesting Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground min-h-screen">
        <main className="container mx-auto p-4">{children}</main>
      </body>
    </html>
  );
}
