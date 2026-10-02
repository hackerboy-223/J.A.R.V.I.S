import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "J.A.R.V.I.S. — Agent IA vocal propulsé par Hugging Face",
    short_name: "J.A.R.V.I.S.",
    description:
      "Assistant IA vocal façon Iron Man : reconnaissance vocale, voix de synthèse, recherche web, outils et interface holographique.",
    start_url: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#060d1a",
    theme_color: "#22d3ee",
    lang: "fr",
    categories: ["productivity", "utilities"],
    icons: [
      {
        src: "/jarvis-icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
