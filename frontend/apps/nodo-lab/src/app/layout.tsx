import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NODO",
  description: "Entrenamiento y planeación para atletas y entrenadores.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es-MX"><body>{children}</body></html>;
}
