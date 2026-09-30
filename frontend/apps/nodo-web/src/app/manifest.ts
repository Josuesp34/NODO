import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "NODO Training Systems",
    short_name: "NODO",
    description: "Planificación y seguimiento para entrenadores y atletas.",
    start_url: "/app",
    display: "standalone",
    background_color: "#101110",
    theme_color: "#101110",
    lang: "es-MX",
    icons: [
      { src: "/icons/nodo.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icons/nodo.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}
