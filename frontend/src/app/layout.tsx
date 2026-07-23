import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI File Converter",
  description: "Convert architecture PDFs to DWG/DXF CAD models",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="min-h-screen bg-gray-50">{children}</main>
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
