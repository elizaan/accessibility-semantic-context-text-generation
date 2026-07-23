"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, GitCompare, Home, Bookmark } from "lucide-react";
import { IS_STATIC_BUILD } from "@/lib/config";

const NAV = [
  { href: "/",            label: "Home",        icon: Home },
  { href: "/datasets",    label: "Datasets",    icon: Database },
  { href: "/collections", label: "Collections", icon: Bookmark },
  { href: "/compare",  label: "Compare",        icon: GitCompare },
].filter((item) => !IS_STATIC_BUILD || item.href !== "/collections");

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 border-r bg-muted/20 flex flex-col py-4 px-3 gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
              active
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </aside>
  );
}
