"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ItemBadges } from "@/components/menu/item-badges";
import { ItemImage } from "@/components/menu/item-image";
import { needsChoice, useItemDialog } from "@/components/menu/item-dialog";
import { formatINR } from "@/lib/money";
import type { Menu, MenuItem } from "@/lib/types";
import { cn } from "@/lib/utils";

function MenuRow({ item }: { item: MenuItem }) {
  const dialog = useItemDialog();
  return (
    <li className={cn("flex gap-4 rounded-3xl border bg-card p-3 transition-shadow hover:shadow-sm", !item.is_available && "opacity-60")}>
      <button
        type="button"
        onClick={() => dialog.open(item)}
        className="h-24 w-24 shrink-0 overflow-hidden rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`View details for ${item.name}`}
      >
        <ItemImage item={item} />
      </button>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-start justify-between gap-2">
          <button type="button" onClick={() => dialog.open(item)} className="text-left font-semibold leading-snug hover:underline">
            {item.name}
          </button>
          <span className="shrink-0 text-sm font-semibold text-primary">
            {item.variants.length > 0 && <span className="text-xs font-normal text-muted-foreground">from </span>}
            {formatINR(item.price_from)}
          </span>
        </div>
        {item.description && <p className="line-clamp-2 text-sm text-muted-foreground">{item.description}</p>}
        <div className="mt-auto flex items-end justify-between gap-2">
          <ItemBadges item={item} compact />
          <Button
            size="sm"
            variant={item.is_available ? "default" : "outline"}
            disabled={!item.is_available}
            onClick={() => dialog.quickAdd(item)}
            aria-label={item.is_available ? `Add ${item.name} to cart` : `${item.name} is unavailable`}
          >
            {item.is_available ? (
              <>
                <Plus /> {needsChoice(item) ? "Options" : "Add"}
              </>
            ) : (
              "Sold out"
            )}
          </Button>
        </div>
      </div>
    </li>
  );
}

export function MenuBrowser({ menu, slug }: { menu: Menu; slug: string }) {
  const [active, setActive] = React.useState(menu.categories[0]?.slug);

  function jump(catSlug: string) {
    setActive(catSlug);
    document.getElementById(`cat-${catSlug}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="mx-auto max-w-4xl px-4 pb-16">
      <div className="sticky top-0 z-10 -mx-4 bg-background/95 px-4 py-3 backdrop-blur">
        <div className="flex gap-2 overflow-x-auto scrollbar-none" role="tablist" aria-label="Menu categories">
          {menu.categories.map((c) => (
            <button
              key={c.id}
              type="button"
              role="tab"
              aria-selected={active === c.slug}
              onClick={() => jump(c.slug)}
              className={cn(
                "shrink-0 rounded-full border px-4 py-1.5 text-sm transition-colors",
                active === c.slug ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-muted",
              )}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>

      <Link
        href={`/r/${slug}`}
        className="mb-6 mt-2 flex items-center gap-3 rounded-3xl bg-primary px-5 py-4 text-primary-foreground transition-opacity hover:opacity-95"
      >
        <Sparkles className="h-5 w-5 shrink-0" />
        <span className="text-sm">
          <span className="font-semibold">Not sure what to get?</span> Ask the Coffee Guide for a recommendation within your budget.
        </span>
      </Link>

      <div className="space-y-10">
        {menu.categories.map((c) => (
          <section key={c.id} id={`cat-${c.slug}`} className="scroll-mt-16" aria-labelledby={`h-${c.slug}`}>
            <h2 id={`h-${c.slug}`} className="font-display text-2xl font-semibold">
              {c.name}
            </h2>
            {c.description && <p className="mb-4 mt-1 text-sm text-muted-foreground">{c.description}</p>}
            <ul className="grid gap-3 md:grid-cols-2">
              {c.items.map((item) => (
                <MenuRow key={item.id} item={item} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
