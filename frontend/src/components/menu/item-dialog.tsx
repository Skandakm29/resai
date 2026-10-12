"use client";

import * as React from "react";
import { AlertTriangle, Check, Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { buildLine, MAX_QUANTITY, useCart } from "@/components/cart/cart-context";
import { ItemBadges } from "@/components/menu/item-badges";
import { ItemImage } from "@/components/menu/item-image";
import { formatINR, fromPaise, toPaise } from "@/lib/money";
import type { Addon, MenuItem, Variant } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ItemDialogContextValue {
  open: (item: MenuItem) => void;
  /** Adds directly when no choice is needed; otherwise opens the dialog. */
  quickAdd: (item: MenuItem) => void;
}

const ItemDialogContext = React.createContext<ItemDialogContextValue | null>(null);

export function useItemDialog() {
  const ctx = React.useContext(ItemDialogContext);
  if (!ctx) throw new Error("useItemDialog must be used inside ItemDialogProvider");
  return ctx;
}

const SIZE_WORDS = /^(regular|small|medium|large|single|double|half|full|\d+\s*(inch|in|"|ml|oz))$/i;

/** "Size" when every variant is a size (Regular/Large, 8 inch...), else a neutral "Option". */
export function variantLabel(item: Pick<MenuItem, "variants">) {
  return item.variants.length > 0 && item.variants.every((v) => SIZE_WORDS.test(v.name.trim())) ? "Size" : "Option";
}

export function needsChoice(item: MenuItem) {
  return item.variant_required || item.variants.filter((v) => v.is_available).length > 1;
}

function defaultVariant(item: MenuItem): Variant | null {
  if (item.variant_required) return null;
  return item.variants.find((v) => v.is_default && v.is_available) ?? null;
}

export function ItemDialogProvider({ children }: { children: React.ReactNode }) {
  const [item, setItem] = React.useState<MenuItem | null>(null);
  const cart = useCart();

  const quickAdd = React.useCallback(
    (it: MenuItem) => {
      if (!it.is_available) return;
      if (needsChoice(it)) {
        setItem(it);
        return;
      }
      cart.add(buildLine(it, defaultVariant(it), [], 1));
      toast.success(`Added ${it.name}`);
    },
    [cart],
  );

  const value = React.useMemo(() => ({ open: setItem, quickAdd }), [quickAdd]);
  return (
    <ItemDialogContext.Provider value={value}>
      {children}
      <Dialog open={item !== null} onOpenChange={(o) => !o && setItem(null)}>
        {item && <ItemDetails key={item.id} item={item} onDone={() => setItem(null)} />}
      </Dialog>
    </ItemDialogContext.Provider>
  );
}

function KnownListText({ label, list, unknownText }: { label: string; list: MenuItem["allergens"]; unknownText: string }) {
  let body: string;
  if (list.status === "unknown") body = unknownText;
  else if (list.items.length === 0) body = list.status === "verified" ? "None listed" : "Not fully specified";
  else body = list.items.join(", ") + (list.status === "partial" ? " (not a complete list)" : "");
  return (
    <div className="flex gap-2 text-sm">
      <dt className="w-24 shrink-0 text-muted-foreground">{label}</dt>
      <dd className={cn(list.status === "unknown" && "text-muted-foreground")}>{body}</dd>
    </div>
  );
}

function ItemDetails({ item, onDone }: { item: MenuItem; onDone: () => void }) {
  const cart = useCart();
  const [variant, setVariant] = React.useState<Variant | null>(defaultVariant(item));
  const [addons, setAddons] = React.useState<Addon[]>([]);
  const [quantity, setQuantity] = React.useState(1);

  const hasVariants = item.variants.length > 0;
  const missingVariant = hasVariants && !variant;
  const unitPaise =
    toPaise(variant ? variant.price : item.price_from) + addons.reduce((s, a) => s + toPaise(a.price), 0);
  const totalPaise = unitPaise * quantity;

  const groups = React.useMemo(() => {
    const g = new Map<string, Addon[]>();
    for (const a of item.addons) g.set(a.group_name, [...(g.get(a.group_name) ?? []), a]);
    return Array.from(g.entries());
  }, [item.addons]);

  function toggleAddon(a: Addon) {
    setAddons((prev) => (prev.some((p) => p.id === a.id) ? prev.filter((p) => p.id !== a.id) : [...prev, a]));
  }

  function add() {
    if (!item.is_available || missingVariant) return;
    cart.add(buildLine(item, variant, addons, quantity));
    toast.success(`Added ${quantity} × ${item.name}${variant ? ` (${variant.name})` : ""}`);
    onDone();
  }

  return (
    <DialogContent>
      <div className="overflow-y-auto">
        <div className="aspect-[16/9] w-full overflow-hidden rounded-t-3xl">
          <ItemImage item={item} />
        </div>
        <div className="space-y-5 p-5 sm:p-6">
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-3">
              <DialogTitle>{item.name}</DialogTitle>
              <span className="shrink-0 pt-1 font-semibold text-primary">
                {hasVariants ? `from ${formatINR(item.price_from)}` : formatINR(item.price)}
              </span>
            </div>
            <ItemBadges item={item} />
            <DialogDescription>{item.description ?? "No description provided."}</DialogDescription>
          </div>

          {hasVariants && (
            <fieldset className="space-y-2">
              <legend className="mb-2 text-sm font-semibold">
                {variantLabel(item)} {item.variant_required && <span className="font-normal text-muted-foreground">· required</span>}
              </legend>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={variantLabel(item)}>
                {item.variants.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    role="radio"
                    aria-checked={variant?.id === v.id}
                    disabled={!v.is_available}
                    onClick={() => setVariant(v)}
                    className={cn(
                      "flex items-center justify-between rounded-2xl border px-4 py-3 text-left text-sm transition-colors disabled:opacity-50",
                      variant?.id === v.id ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted",
                    )}
                  >
                    <span className="font-medium">{v.name}</span>
                    <span className="text-muted-foreground">{v.is_available ? formatINR(v.price) : "Unavailable"}</span>
                  </button>
                ))}
              </div>
            </fieldset>
          )}

          {groups.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-semibold">
                Add-ons <span className="font-normal text-muted-foreground">· optional</span>
              </p>
              {groups.map(([group, list]) => (
                <div key={group} className="space-y-1.5">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{group}</p>
                  <div className="flex flex-wrap gap-2">
                    {list.map((a) => {
                      const on = addons.some((p) => p.id === a.id);
                      return (
                        <button
                          key={a.id}
                          type="button"
                          aria-pressed={on}
                          disabled={!a.is_available}
                          onClick={() => toggleAddon(a)}
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors disabled:opacity-50",
                            on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
                          )}
                        >
                          {on && <Check className="h-3 w-3" />}
                          {a.name} · {a.is_available ? `+${formatINR(a.price)}` : "unavailable"}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          <dl className="space-y-1.5 rounded-2xl bg-muted/60 p-4">
            <KnownListText label="Ingredients" list={item.ingredients} unknownText="Not published by the restaurant" />
            <KnownListText label="Allergens" list={item.allergens} unknownText="Not verified - please ask staff" />
            <div className="flex gap-2 text-sm">
              <dt className="w-24 shrink-0 text-muted-foreground">Vegan</dt>
              <dd className={cn(item.dietary.vegan === "unknown" && "text-muted-foreground")}>
                {item.dietary.vegan === "yes" ? "Yes (verified)" : item.dietary.vegan === "no" ? "No" : "Not verified"}
              </dd>
            </div>
            {item.allergens.status === "unknown" && (
              <p className="flex items-start gap-1.5 pt-1 text-xs text-amber-900">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Allergen information isn&apos;t verified for this item. If you have an allergy, please check with staff.
              </p>
            )}
          </dl>
        </div>
      </div>

      <div className="flex items-center gap-3 border-t bg-card p-4 sm:rounded-b-3xl">
        <div className="flex items-center rounded-full border">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Decrease quantity"
            onClick={() => setQuantity((q) => Math.max(1, q - 1))}
            disabled={quantity <= 1}
          >
            <Minus />
          </Button>
          <span className="w-7 text-center text-sm font-medium" aria-live="polite" aria-label="Quantity">
            {quantity}
          </span>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Increase quantity"
            onClick={() => setQuantity((q) => Math.min(MAX_QUANTITY, q + 1))}
            disabled={quantity >= MAX_QUANTITY}
          >
            <Plus />
          </Button>
        </div>
        <Button className="flex-1" size="lg" onClick={add} disabled={!item.is_available || missingVariant}>
          {!item.is_available
            ? "Currently unavailable"
            : missingVariant
              ? `Choose ${variantLabel(item) === "Size" ? "a size" : "an option"}`
              : `Add to cart · ${formatINR(fromPaise(totalPaise))}`}
        </Button>
      </div>
    </DialogContent>
  );
}
