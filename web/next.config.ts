import type { NextConfig } from "next";

// Flask API (hatch-studio/app.py). Next.js chuyen tiep /api va /fonts sang day nen khong can CORS.
const API = process.env.HATCH_API ?? "http://127.0.0.1:5050";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/fonts/:path*", destination: `${API}/fonts/:path*` },
    ];
  },
  experimental: {
    proxyTimeout: 300_000, // xuat sach nhieu trang co the mat vai chuc giay
  },
};

export default nextConfig;
