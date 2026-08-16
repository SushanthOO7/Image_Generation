import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FLUX.2 Platform",
  description: "Self-hosted FLUX.2 image generation console",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
