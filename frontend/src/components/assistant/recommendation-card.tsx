"use client";

import { Check, Info, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ItemBadges } from "@/components/menu/item-badges";
import { ItemImage } from "@/components/menu/item-image";
import { needsChoice, useItemDialog, variantLabel } from "@/components/menu/item-dialog";
import { formatINR } from "@/lib/money";
import type { Recommendation } from "@/lib/types";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const { item } = rec;
  const dialog = useItemDialog();
  const hasVariants = item.variants.length > 0;
  const availableAddons = item.addons.filter((a) => a.is_available).length;

  return (
    <article
      className="flex w-[78vw] max-w-[300px] shrink-0 snap-start flex-col overflow-hidden rounded-3xl border bg-card shadow-sm sm:w-auto sm:max-w-none"
      aria-label={item.name}
    >
      <div className="relative aspect-[16/10] overflow-hidden sm:aspect-auto sm:h-32">
        <ItemImage item={item} />
        {rec.over_budget && (
          <Badge variant="warning" className="absolute left-3 top-3">
            Above budget
          </Badge>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-display text-[17px] leading-snug">{item.name}</h3>
          <p className="shrink-0 font-semibold text-primary" data-testid="rec-price">
            {hasVariants && <span className="text-xs font-normal text-muted-foreground">from </span>}
            {formatINR(item.price_from)}
          </p>
        </div>
        {item.description && <p className="line-clamp-2 text-sm text-muted-foreground">{item.description}</p>}
        <ItemBadges item={item} compact />
        {rec.note && <p className="text-sm italic text-coffee">{rec.note}</p>}
        {rec.reasons.length > 0 && (
          <ul className="space-y-1">
            {rec.reasons.map((r) => (
              <li key={r} className="flex items-start gap-1.5 text-xs text-foreground/80">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                {r}
              </li>
            ))}
          </ul>
        )}
        {(hasVariants || availableAddons > 0) && (
          <p className="text-xs text-muted-foreground">
            {hasVariants && `${variantLabel(item) === "Size" ? "Sizes" : "Options"}: ${item.variants.map((v) => v.name).join(", ")}`}
            {hasVariants && availableAddons > 0 && " · "}
            {availableAddons > 0 && `${availableAddons} add-on${availableAddons === 1 ? "" : "s"} available`}
          </p>
        )}
        <div className="mt-auto flex gap-2 pt-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={() => dialog.open(item)}>
            <Info /> View details
          </Button>
          <Button
            size="sm"
            className="flex-1"
            disabled={!item.is_available}
            onClick={() => dialog.quickAdd(item)}
            aria-label={item.is_available ? `Add ${item.name} to cart` : `${item.name} is unavailable`}
          >
            {item.is_available ? (
              <>
                <Plus /> {needsChoice(item) ? "Choose & add" : "Add to cart"}
              </>
            ) : (
              "Unavailable"
            )}
          </Button>
        </div>
      </div>
    </article>
  );
}
