"use client";

import * as React from "react";
import { fromPaise, toPaise } from "@/lib/money";
import type { Addon, MenuItem, Variant } from "@/lib/types";

export interface CartLine {
  key: string;
  itemId: string;
  name: string;
  itemType: MenuItem["item_type"];
  imageUrl: string | null;
  variantId: string | null;
  variantName: string | null;
  addons: { id: string; name: string; price: string }[];
  /** Base/variant price + add-ons, as last seen from the API. Display only. */
  unitPrice: string;
  quantity: number;
}

type Action =
  | { type: "add"; line: CartLine }
  | { type: "setQuantity"; key: string; quantity: number }
  | { type: "remove"; key: string }
  | { type: "updatePrice"; key: string; unitPrice: string }
  | { type: "clear" }
  | { type: "hydrate"; lines: CartLine[] };

export const MAX_QUANTITY = 20;

function reducer(state: CartLine[], action: Action): CartLine[] {
  switch (action.type) {
    case "add": {
      const existing = state.find((l) => l.key === action.line.key);
      if (existing) {
        return state.map((l) =>
          l.key === action.line.key
            ? { ...l, quantity: Math.min(MAX_QUANTITY, l.quantity + action.line.quantity), unitPrice: action.line.unitPrice }
            : l,
        );
      }
      return [...state, { ...action.line, quantity: Math.min(MAX_QUANTITY, action.line.quantity) }];
    }
    case "setQuantity":
      if (action.quantity <= 0) return state.filter((l) => l.key !== action.key);
      return state.map((l) => (l.key === action.key ? { ...l, quantity: Math.min(MAX_QUANTITY, action.quantity) } : l));
    case "remove":
      return state.filter((l) => l.key !== action.key);
    case "updatePrice":
      return state.map((l) => (l.key === action.key ? { ...l, unitPrice: action.unitPrice } : l));
    case "clear":
      return [];
    case "hydrate":
      return action.lines;
  }
}

export function lineKey(itemId: string, variantId: string | null, addonIds: string[]) {
  return [itemId, variantId ?? "-", ...[...addonIds].sort()].join("|");
}

export function buildLine(item: MenuItem, variant: Variant | null, addons: Addon[], quantity: number): CartLine {
  const base = toPaise(variant ? variant.price : item.price);
  const extras = addons.reduce((sum, a) => sum + toPaise(a.price), 0);
  return {
    key: lineKey(item.id, variant?.id ?? null, addons.map((a) => a.id)),
    itemId: item.id,
    name: item.name,
    itemType: item.item_type,
    imageUrl: item.image_url,
    variantId: variant?.id ?? null,
    variantName: variant?.name ?? null,
    addons: addons.map((a) => ({ id: a.id, name: a.name, price: a.price })),
    unitPrice: fromPaise(base + extras),
    quantity,
  };
}

export function lineTotalPaise(line: CartLine) {
  return toPaise(line.unitPrice) * line.quantity;
}

interface CartContextValue {
  slug: string;
  lines: CartLine[];
  itemCount: number;
  subtotalPaise: number;
  add: (line: CartLine) => void;
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  updatePrice: (key: string, unitPrice: string) => void;
  clear: () => void;
}

const CartContext = React.createContext<CartContextValue | null>(null);

const storageKey = (slug: string) => `cart:${slug}`;

export function CartProvider({ slug, children }: { slug: string; children: React.ReactNode }) {
  const [lines, dispatch] = React.useReducer(reducer, []);
  const hydrated = React.useRef(false);

  // Restore after mount (storage can be unavailable - private mode, blocked cookies).
  React.useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey(slug));
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) dispatch({ type: "hydrate", lines: parsed });
      }
    } catch {
      /* ignore */
    }
    hydrated.current = true;
  }, [slug]);

  React.useEffect(() => {
    if (!hydrated.current) return;
    try {
      window.localStorage.setItem(storageKey(slug), JSON.stringify(lines));
    } catch {
      /* ignore */
    }
  }, [lines, slug]);

  const value = React.useMemo<CartContextValue>(
    () => ({
      slug,
      lines,
      itemCount: lines.reduce((n, l) => n + l.quantity, 0),
      subtotalPaise: lines.reduce((n, l) => n + lineTotalPaise(l), 0),
      add: (line) => dispatch({ type: "add", line }),
      setQuantity: (key, quantity) => dispatch({ type: "setQuantity", key, quantity }),
      remove: (key) => dispatch({ type: "remove", key }),
      updatePrice: (key, unitPrice) => dispatch({ type: "updatePrice", key, unitPrice }),
      clear: () => dispatch({ type: "clear" }),
    }),
    [lines, slug],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = React.useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
