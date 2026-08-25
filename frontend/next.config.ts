import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    // In production sind die "services"-Rewrites aus der Wurzel-vercel.json
    // zuständig (/api/* -> backend-Service) - Requests für /api/* erreichen
    // diesen Next.js-Dienst dort gar nicht erst. Im lokalen `next dev`
    // (ohne `vercel dev`-Orchestrierung) fehlt dieses Routing jedoch, daher
    // proxyen wir /api/* hier zusätzlich auf das lokal laufende Flask-Backend.
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:5050/api/:path*",
      },
    ];
  },
};

export default nextConfig;
