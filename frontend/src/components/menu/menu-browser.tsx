"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ItemBadges } from "@/components/menu/item-badges";
import { ItemImage } from "@/components/menu/item-image";
import { needsChoice, useItemDialog } from "@/components/menu/item-dialog";
import { SignatureStrip } from "@/components/menu/signature-strip";
import { signatures } from "@/lib/menu";
import { themeFor } from "@/lib/brand";
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
          <button type="button" onClick={() => dialog.open(item)} className="text-left font-display text-[17px] leading-snug hover:underline">
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
  // Big menus split into Food and Drinks so the section bar stays short.
  const isDrinks = (c: Menu["categories"][number]) =>
    c.items.length > 0 && c.items.filter((i) => i.item_type === "beverage").length * 2 > c.items.length;
  const hasBoth = menu.categories.some(isDrinks) && menu.categories.some((c) => !isDrinks(c));
  const [half, setHalf] = React.useState<"food" | "drinks">("food");
  const categories = hasBoth ? menu.categories.filter((c) => isDrinks(c) === (half === "drinks")) : menu.categories;
  const [active, setActive] = React.useState<string | undefined>(categories[0]?.slug);
  const dialog = useItemDialog();
  const featured = signatures(categories.flatMap((c) => c.items));
  const dark = Boolean(themeFor(slug)?.darkHeader);

  function jump(catSlug: string) {
    setActive(catSlug);
    document.getElementById(`cat-${catSlug}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="mx-auto max-w-4xl px-4 pb-16">
      <div className="sticky top-0 z-10 -mx-4 space-y-2.5 bg-background/95 px-4 py-3 backdrop-blur">
        {hasBoth && (
          <div className="flex w-full rounded-full bg-muted p-1 sm:w-72" role="group" aria-label="Food or drinks">
            {(["food", "drinks"] as const).map((h) => (
              <button
                key={h}
                type="button"
                aria-pressed={half === h}
                onClick={() => {
                  setHalf(h);
                  const first = menu.categories.find((c) => isDrinks(c) === (h === "drinks"));
                  setActive(first?.slug);
                  document.getElementById("menu-top")?.scrollIntoView({ block: "start" });
                }}
                className={cn(
                  "flex-1 rounded-full py-1.5 text-sm font-medium capitalize transition-colors",
                  half === h ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {h}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2 overflow-x-auto scrollbar-none" role="tablist" aria-label="Menu categories">
          {categories.map((c) => (
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

      <div id="menu-top" className="scroll-mt-32" />
      <Link
        href={`/r/${slug}`}
        className={cn(
          "mb-6 mt-2 flex items-center gap-3 rounded-3xl px-5 py-4 transition-opacity hover:opacity-95",
          dark ? "bg-ink text-ink-foreground" : "bg-primary text-primary-foreground",
        )}
      >
        <Sparkles className={cn("h-5 w-5 shrink-0", dark && "text-[hsl(var(--glow))]")} />
        <span className="text-sm">
          <span className="font-semibold">Not sure what to get?</span> Ask the assistant for a recommendation within your budget.
        </span>
      </Link>

      {featured.length > 0 && (
        <section className="mb-10" aria-labelledby="h-signatures">
          <h2 id="h-signatures" className="font-display text-3xl">
            Signatures
          </h2>
          <p className="mb-4 mt-1 text-sm text-muted-foreground">House favourites - tap one for details.</p>
          <SignatureStrip items={featured} onPick={(item) => dialog.open(item)} />
        </section>
      )}

      <div className="space-y-10">
        {categories.map((c) => (
          <section key={c.id} id={`cat-${c.slug}`} className={hasBoth ? "scroll-mt-28" : "scroll-mt-16"} aria-labelledby={`h-${c.slug}`}>
            <h2 id={`h-${c.slug}`} className="font-display text-3xl">
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
