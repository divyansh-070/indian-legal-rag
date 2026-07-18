/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'https://indian-legal-rag-api-1hv3.onrender.com/api/v1/:path*',
      },
    ];
  },
};

module.exports = nextConfig;