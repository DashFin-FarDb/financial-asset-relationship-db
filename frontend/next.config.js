/** @type {import('next').NextConfig} */
const isVercelBuild = process.env.VERCEL === '1'
const rawApiBaseUrl = isVercelBuild
  ? ''
  : (process.env.NEXT_PUBLIC_API_URL || '').trim()

let apiBaseUrl = rawApiBaseUrl
if (process.env.NETLIFY) {
  if (!rawApiBaseUrl) {
    throw new Error(
      'NEXT_PUBLIC_API_URL must point to the matching FastAPI deployment when building the static UI on Netlify.'
    )
  }
  let parsed
  try {
    parsed = new URL(rawApiBaseUrl)
  } catch {
    throw new Error(
      'NEXT_PUBLIC_API_URL must be a valid http(s) origin (scheme and host only) when building the static UI on Netlify.'
    )
  }
  if (
    (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') ||
    (parsed.pathname && parsed.pathname !== '/') ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      'NEXT_PUBLIC_API_URL must be an http(s) origin with no path, query, or fragment (for example, https://api.example.com).'
    )
  }
  apiBaseUrl = parsed.origin
}

const nextConfig = {
  ...(isVercelBuild ? {} : { output: 'export' }),
  reactStrictMode: true,
  typescript: {
    tsconfigPath: 'tsconfig.typecheck.json'
  },
  ...(isVercelBuild || apiBaseUrl
    ? {
        env: {
          // Vercel hosts this UI and the FastAPI handler in one deployment, so use
          // same-origin /api requests there. Static Netlify builds need an explicit
          // FastAPI origin, enforced above.
          NEXT_PUBLIC_API_URL: isVercelBuild ? '' : apiBaseUrl
        }
      }
    : {})
}

module.exports = nextConfig
