/** @type {import('next').NextConfig} */
const nextConfig = { reactStrictMode: true };
// GC_STATIC_EXPORT=1: static export for the desktop shell (desktop/scripts/build-renderer.mjs). Default unchanged.
if (process.env.GC_STATIC_EXPORT === "1") Object.assign(nextConfig, { output: "export", trailingSlash: true, images: { unoptimized: true } });
export default nextConfig;
