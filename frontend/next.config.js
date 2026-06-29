/** @type {import('next').NextConfig} */
const isVercel = process.env.VERCEL === '1';
const defaultApiUrl = isVercel ? '' : 'http://localhost:8000';

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL !== undefined
        ? process.env.NEXT_PUBLIC_API_URL
        : defaultApiUrl
  }
}

module.exports = nextConfig
