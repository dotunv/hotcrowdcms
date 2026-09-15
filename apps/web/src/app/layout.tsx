import type { ReactNode } from "react";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata = {
  title: "HotCrowd",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){const t=localStorage.getItem('theme');const d=t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-background-light dark:bg-background-dark text-gray-900 dark:text-white">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
