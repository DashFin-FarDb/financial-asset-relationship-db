import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Financial Asset Relationship Network",
  description:
    "Interactive 3D visualization of interconnected financial assets",
};

/**
 * Application root layout that renders a complete HTML document with language set to English.
 * Places the app content inside the document body.
 *
 * @param children - The React nodes to render inside the `<body>` of the document
 * @returns The root `<html>` element containing the rendered children
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
