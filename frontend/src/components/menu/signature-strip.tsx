"use client";

import { ItemImage } from "@/components/menu/item-image";
import { formatINR } from "@/lib/money";
import type { MenuItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Horizontally scrolling photo cards for a restaurant's signature items. */
export function SignatureStrip({
  items,
  onPick,
  className,
  tone = "light",
}: {
  items: MenuItem[];
  onPick: (item: MenuItem) => void;
  className?: string;
  tone?: "light" | "dark";
}) {
  if (items.length === 0) return null;
  return (
    <ul className={cn("-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 scrollbar-none", className)} aria-label="Signatures">
      {items.map((item, i) => (
        <li key={item.id} className="rise-in shrink-0 snap-start" style={{ animationDelay: `${i * 60}ms` }}>
          <button
            type="button"
            onClick={() => onPick(item)}
            className={cn(
              "group block w-40 overflow-hidden rounded-3xl text-left shadow-sm ring-1 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:w-44",
              tone === "dark" ? "bg-white/5 ring-white/10" : "bg-card ring-border",
            )}
          >
            <div className="aspect-square overflow-hidden">
              <ItemImage item={item} className="transition-transform duration-500 group-hover:scale-105" />
            </div>
            <div className="space-y-0.5 p-3">
              <p className="truncate text-sm font-semibold leading-snug">{item.name}</p>
              <p className={cn("text-xs", tone === "dark" ? "text-ink-foreground/70" : "text-muted-foreground")}>
                {item.variants.length > 0 && "from "}
                {formatINR(item.price_from)}
              </p>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
