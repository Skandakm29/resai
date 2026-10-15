/** @type {import('next').NextConfig} */
const backendUrl = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    // Menu uploads are read by an LLM and can take a few minutes.
    proxyTimeout: 330_000,
  },
  // The browser only ever talks to this origin; requests are proxied to the
  // FastAPI backend, so no backend URL or API key is exposed to the client.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
