/** @type {import('next').NextConfig} */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const isStaticBuild = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

const nextConfig = {
  output: isStaticBuild ? "export" : undefined,
  basePath,
  assetPrefix: basePath || undefined,
  trailingSlash: isStaticBuild,
  images: { unoptimized: true },
};

export default nextConfig;
