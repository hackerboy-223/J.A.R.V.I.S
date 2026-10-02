import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/theme-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "J.A.R.V.I.S. — Agent IA vocal propulsé par Hugging Face",
  description:
    "Just A Rather Very Intelligent System : un agent IA vocal façon Iron Man — reconnaissance vocale, voix de synthèse, recherche web, contrôle de la machine et interface holographique animée, propulsé par les modèles de Hugging Face.",
  keywords: [
    "JARVIS",
    "Iron Man",
    "Hugging Face",
    "Agent IA",
    "Assistant vocal",
    "LLM",
    "Next.js",
    "Outils",
  ],
  authors: [{ name: "J.A.R.V.I.S." }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#060d1a" },
    { media: "(prefers-color-scheme: light)", color: "#e8f6fa" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
