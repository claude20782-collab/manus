import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OpenManus-Web - Autonomous AI Agent",
  description: "AI agent with browser automation capabilities",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
