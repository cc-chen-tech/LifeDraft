import type { Metadata, Viewport } from "next";
import { Noto_Sans_SC, Noto_Serif_SC } from "next/font/google";
import ErrorReporter from "@/components/ErrorReporter";
import GlobalMusicPlayerWrapper from "@/components/game/GlobalMusicPlayerWrapper";
import "./globals.css";

const notoSansSC = Noto_Sans_SC({
  variable: "--font-sans-sc",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
});

const notoSerifSC = Noto_Serif_SC({
  variable: "--font-serif-sc",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Story Life - 人生模拟器",
  description: "AI驱动的沉浸式人生模拟文字冒险游戏",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#0a0f1a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh" className="dark">
      <body
        className={`${notoSansSC.variable} ${notoSerifSC.variable} font-sans antialiased`}
      >
        <ErrorReporter />
        {children}
        <GlobalMusicPlayerWrapper />
      </body>
    </html>
  );
}
