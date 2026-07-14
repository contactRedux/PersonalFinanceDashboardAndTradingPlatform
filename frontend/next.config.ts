import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Strict mode for React 19
  reactStrictMode: true,

  // Standalone output for Docker
  output: "standalone",

  // Environment variables exposed to the browser
  env: {
    NEXT_PUBLIC_APP_NAME: "QuantNexus",
  },

  // Allow images from data: URIs (used by chart components)
  images: {
    formats: ["image/avif", "image/webp"],
  },

  // Rewrites: proxy /api/* → FastAPI backend (dev only)
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
