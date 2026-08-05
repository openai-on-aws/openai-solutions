import type { Metadata } from "next";
import ThemeToggle from "@/components/ThemeToggle";
import { themeInitScript } from "@/app/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "Azure OpenAI to Amazon Bedrock OpenAI Migration Workshop",
  description:
    "A Codex Desktop workshop for migrating an Azure OpenAI Chat Completions app to Amazon Bedrock OpenAI Responses.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        {children}
        <ThemeToggle />
      </body>
    </html>
  );
}
