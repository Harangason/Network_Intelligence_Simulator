import type { NextConfig } from "next";

const configuredDistDir = process.env.NETWORKIS_NEXT_DIST_DIR;

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  distDir: configuredDistDir ?? ".next-networkis",
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    // In production sind die "services"-Rewrites aus der Wurzel-vercel.json
    // zuständig (/api/* -> backend-Service) - Requests für /api/* erreichen
    // diesen Next.js-Dienst dort gar nicht erst. Im lokalen `next dev`
    // (ohne `vercel dev`-Orchestrierung) fehlt dieses Routing jedoch, daher
    // proxyen wir /api/* hier zusätzlich auf das lokal laufende Flask-Backend.
    const backendApiUrl = process.env.SIMULATOR_BACKEND_API_URL;
    if (!backendApiUrl) return [];
    return [
      {
        source: "/api/:path((?!agent).*)",
        destination: `${backendApiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
