import type { Metadata, Viewport } from "next";
import ErrorReporter from "@/components/ErrorReporter";
import GlobalMusicPlayerWrapper from "@/components/game/GlobalMusicPlayerWrapper";
import { AppShell } from "@/components/story101";
import "./globals.css";

export const metadata: Metadata = {
  title: "story101 - 人生模拟器",
  description: "AI驱动的沉浸式人生模拟文字冒险游戏",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0D0C0B",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh" className="dark">
      <body className="font-sans antialiased">
        <ErrorReporter />
        <AppShell fixedRegions={<GlobalMusicPlayerWrapper />}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
