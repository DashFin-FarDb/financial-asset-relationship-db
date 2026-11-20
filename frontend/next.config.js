/** @type {import('next').NextConfig} */
const isVercelBuild = process.env.VERCEL === '1'
const apiBaseUrl = isVercelBuild
  ? ''
  : (process.env.NEXT_PUBLIC_API_URL || '').trim()

if (process.env.NETLIFY && !apiBaseUrl) {
  throw new Error(
    'NEXT_PUBLIC_API_URL must point to the matching FastAPI deployment when building the static UI on Netlify.'
  )
}

const nextConfig = {
  ...(isVercelBuild ? {} : { output: 'export' }),
  reactStrictMode: true,
  typescript: {
    tsconfigPath: 'tsconfig.typecheck.json'
  },
  env: {
    // Vercel hosts this UI and the FastAPI handler in one deployment, so use
    // same-origin /api requests there. Static Netlify builds need an explicit
    // FastAPI origin, enforced above.
    NEXT_PUBLIC_API_URL: apiBaseUrl
  }
}

module.exports = nextConfig
