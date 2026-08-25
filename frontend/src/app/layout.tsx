import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { GlobalAgentWidget } from "@/components/global-agent-widget";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Communication Simulator — Build signals. Understand systems.",
  description:
    "Offene Simulationsumgebung für moderne Kommunikationssysteme, Netzwerk-Traces und Hardwarevalidierung.",
};

export const viewport: Viewport = {
  themeColor: "#0b0d0b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="de"
      className={`${geistSans.variable} ${geistMono.variable} bg-background`}
    >
      <body>
        {children}
        <GlobalAgentWidget />
      </body>
    </html>
  );
}
