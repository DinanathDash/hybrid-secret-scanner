import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js 16 uses Turbopack by default; empty config suppresses the
  // "webpack config with no turbopack config" build error.
  turbopack: {},
};

export default nextConfig;
