import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "LangGraph Chatbot",
  description: "Threaded LangGraph chatbot with calculator, Exa search, and Twitter/X MCP tools.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
