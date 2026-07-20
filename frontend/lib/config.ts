// Set at build time (see .github/workflows/deploy.yml). Unset in local dev,
// so `npm run dev`/`npm run build` against the live backend are unaffected.
export const IS_STATIC_BUILD = process.env.NEXT_PUBLIC_STATIC_MODE === "true";
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
