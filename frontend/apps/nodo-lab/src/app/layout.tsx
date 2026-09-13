import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NODO Lab",
  description: "Planeación y seguimiento para entrenadores.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es-MX"><body>{children}</body></html>;
}
