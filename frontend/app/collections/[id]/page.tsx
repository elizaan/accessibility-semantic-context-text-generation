import fs from "node:fs";
import path from "node:path";
import CollectionClient from "./CollectionClient";

// Route segment config + generateStaticParams must live in a Server
// Component — the actual page body (CollectionClient) is a client component.
export const dynamicParams = process.env.NEXT_PUBLIC_STATIC_MODE !== "true";

// `output: "export"` requires at least one generateStaticParams() result per
// dynamic route (an unconditionally-empty array fails the build), so these
// pages still get pre-rendered — but CollectionClient itself shows a "not
// available" notice in static mode instead of real content (collections are
// an internal research-curation tool, hidden from external viewers; nothing
// links to these URLs anymore).
export async function generateStaticParams() {
  if (process.env.NEXT_PUBLIC_STATIC_MODE !== "true") return [];
  const filePath = path.join(process.cwd(), "public", "static-data", "collections.json");
  if (!fs.existsSync(filePath)) return [];
  const collections: { collection_id: string }[] = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  return collections.map((c) => ({ id: c.collection_id }));
}

export default function CollectionDetailPage() {
  return <CollectionClient />;
}
