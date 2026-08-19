import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["localhost", "10.218.64.88"],
  distDir: process.env.NEXT_DIST_DIR ?? ".next-codex-build",
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
