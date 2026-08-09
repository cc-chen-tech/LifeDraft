import type { Metadata, Viewport } from "next";
import ErrorReporter from "@/components/ErrorReporter";
import GlobalMusicPlayerWrapper from "@/components/game/GlobalMusicPlayerWrapper";
import { AppShell } from "@/components/story101";
import "./globals.css";

export const metadata: Metadata = {
  title: "story101 - 人生模拟器",
  description: "人生草稿本，把一次人生写成一页页可继续的故事",
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
