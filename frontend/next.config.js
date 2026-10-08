/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typescript: {
    tsconfigPath: "tsconfig.typecheck.json",
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL !== undefined
        ? process.env.NEXT_PUBLIC_API_URL
        : "",
  },
};

module.exports = nextConfig;
