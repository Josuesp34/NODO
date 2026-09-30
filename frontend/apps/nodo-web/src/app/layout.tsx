import type { Metadata, Viewport } from "next";
import { PwaRegister } from "@/components/pwa-register";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "NODO", template: "%s · NODO" },
  description: "Planificación, ejecución y contexto para entrenadores y atletas.",
  applicationName: "NODO",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/nodo.svg", apple: "/icons/nodo.svg" },
};

export const viewport: Viewport = {
  themeColor: "#101110",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es-MX">
      <body>
        <a className="skip-link" href="#contenido">Saltar al contenido</a>
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
