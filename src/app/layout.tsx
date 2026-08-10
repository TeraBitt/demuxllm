import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";
import { THEME_SCRIPT } from "@/components/theme-toggle";
import { MotionProvider } from "@/components/ui/motion";
import "./globals.css";

const sans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

const mono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

const DESCRIPTION =
  "One key for every AI model. We send each question to the cheapest model that can answer it properly, and show you what you saved. Change one line of code.";

export const metadata: Metadata = {
  metadataBase: new URL("https://demuxllm.com"),
  title: {
    default: "DemuxLLM — one key for every AI model",
    template: "%s · DemuxLLM",
  },
  description: DESCRIPTION,
  openGraph: {
    title: "DemuxLLM — one key for every AI model",
    description: DESCRIPTION,
    type: "website",
    url: "/",
    siteName: "DemuxLLM",
  },
  twitter: {
    card: "summary_large_image",
    title: "DemuxLLM — one key for every AI model",
    description: DESCRIPTION,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#08090b" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Stamps `.dark` before first paint so the theme never flashes. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-100 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-canvas"
        >
          Skip to content
        </a>
        <MotionProvider>
          <Nav />
          <main id="main">{children}</main>
          <Footer />
        </MotionProvider>
      </body>
    </html>
  );
}
