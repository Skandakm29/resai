"use client";

import * as React from "react";
import { AlertCircle, CheckCircle2, Loader2, Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ItemImage } from "@/components/menu/item-image";
import { lineTotalPaise, MAX_QUANTITY, useCart } from "@/components/cart/cart-context";
import { api, ApiError } from "@/lib/api";
import { formatINR, fromPaise } from "@/lib/money";
import type { CartValidation } from "@/lib/types";
import { cn } from "@/lib/utils";

type CheckoutState =
  | { status: "idle" }
  | { status: "validating" }
  | { status: "done"; result: CartValidation; lineKeys: string[] }
  | { status: "error"; message: string };

export function CartPanel({ className }: { className?: string }) {
  const cart = useCart();
  const [checkout, setCheckout] = React.useState<CheckoutState>({ status: "idle" });

  // Any cart change invalidates a previous verification.
  const signature = cart.lines.map((l) => `${l.key}:${l.quantity}`).join(",");
  React.useEffect(() => setCheckout({ status: "idle" }), [signature]);

  async function verify() {
    setCheckout({ status: "validating" });
    const lineKeys = cart.lines.map((l) => l.key);
    try {
      const result = await api.validateCart({
        restaurant_slug: cart.slug,
        lines: cart.lines.map((l) => ({
          item_id: l.itemId,
          variant_id: l.variantId,
          addon_ids: l.addons.map((a) => a.id),
          quantity: l.quantity,
          unit_price: l.unitPrice,
        })),
      });
      result.lines.forEach((line, i) => {
        if (line.status === "price_changed" && line.unit_price) cart.updatePrice(lineKeys[i], line.unit_price);
      });
      setCheckout({ status: "done", result, lineKeys });
    } catch (e) {
      setCheckout({ status: "error", message: e instanceof ApiError ? e.message : "Couldn't verify your cart." });
    }
  }

  const issuesByKey = new Map<string, string[]>();
  if (checkout.status === "done") {
    checkout.result.lines.forEach((l, i) => l.issues.length && issuesByKey.set(checkout.lineKeys[i], l.issues));
  }

  if (cart.lines.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-12 text-center", className)}>
        <div className="rounded-full bg-secondary p-4">
          <ShoppingBag className="h-6 w-6 text-coffee" />
        </div>
        <p className="font-medium">Your cart is empty</p>
        <p className="text-sm text-muted-foreground">Ask the assistant for a recommendation or browse the menu to add something.</p>
      </div>
    );
  }

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <ul className="min-h-0 flex-1 divide-y overflow-y-auto px-4" aria-label="Cart items">
        {cart.lines.map((line) => (
          <li key={line.key} className="flex gap-3 py-4">
            <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl">
              <ItemImage item={{ name: line.name, image_url: line.imageUrl, item_type: line.itemType, temperature: null }} />
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium leading-snug">{line.name}</p>
                <p className="shrink-0 text-sm font-semibold" data-testid="line-total">
                  {formatINR(fromPaise(lineTotalPaise(line)))}
                </p>
              </div>
              {(line.variantName || line.addons.length > 0) && (
                <p className="text-xs text-muted-foreground">
                  {[line.variantName, ...line.addons.map((a) => `+ ${a.name}`)].filter(Boolean).join(" · ")}
                </p>
              )}
              {issuesByKey.get(line.key)?.map((issue) => (
                <p key={issue} className="text-xs text-destructive">
                  {issue}
                </p>
              ))}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center rounded-full border">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Decrease ${line.name}`}
                    onClick={() => cart.setQuantity(line.key, line.quantity - 1)}
                  >
                    <Minus />
                  </Button>
                  <span className="w-6 text-center text-sm" aria-label={`${line.name} quantity`}>
                    {line.quantity}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Increase ${line.name}`}
                    disabled={line.quantity >= MAX_QUANTITY}
                    onClick={() => cart.setQuantity(line.key, line.quantity + 1)}
                  >
                    <Plus />
                  </Button>
                </div>
                <Button variant="ghost" size="sm" aria-label={`Remove ${line.name}`} onClick={() => cart.remove(line.key)}>
                  <Trash2 /> Remove
                </Button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="space-y-3 border-t bg-card px-4 py-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Subtotal · {cart.itemCount} item{cart.itemCount === 1 ? "" : "s"}</span>
          <span className="text-lg font-semibold" data-testid="cart-subtotal">
            {formatINR(fromPaise(cart.subtotalPaise))}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">Taxes, if any, are shown at the counter. Prices are re-checked before ordering.</p>

        {checkout.status === "done" && (
          <div
            role="status"
            className={cn(
              "flex gap-2 rounded-2xl p-3 text-sm",
              checkout.result.valid ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive",
            )}
          >
            {checkout.result.valid ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />}
            <div>
              <p>{checkout.result.message}</p>
              {checkout.result.valid && <p className="mt-1 font-semibold">Verified total: {formatINR(checkout.result.subtotal)}</p>}
            </div>
          </div>
        )}
        {checkout.status === "error" && (
          <p role="alert" className="rounded-2xl bg-destructive/10 p-3 text-sm text-destructive">
            {checkout.message}
          </p>
        )}

        <Button className="w-full" size="lg" onClick={verify} disabled={checkout.status === "validating"}>
          {checkout.status === "validating" ? (
            <>
              <Loader2 className="animate-spin" /> Checking prices…
            </>
          ) : checkout.status === "done" && checkout.result.valid ? (
            "Verified - order at the counter"
          ) : (
            "Review & checkout"
          )}
        </Button>
      </div>
    </div>
  );
}
