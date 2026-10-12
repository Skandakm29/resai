"use client";

import { Chat } from "@/components/assistant/chat";
import { CartPanel } from "@/components/cart/cart-panel";
import type { Restaurant } from "@/lib/types";

/** Mobile: full-height chat. Desktop: chat + persistent cart sidebar. */
export function AssistantPage({ restaurant }: { restaurant: Restaurant }) {
  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-6 lg:px-4 lg:py-4">
      <div className="h-full min-h-0 bg-background lg:overflow-hidden lg:rounded-3xl lg:border lg:bg-card/40">
        <Chat restaurant={restaurant} />
      </div>
      <aside className="hidden min-h-0 flex-col overflow-hidden rounded-3xl border bg-card lg:flex" aria-label="Cart" data-testid="desktop-cart">
        <div className="border-b px-4 py-4">
          <h2 className="font-display text-lg font-semibold">Your cart</h2>
          <p className="text-xs text-muted-foreground">Pickup from {restaurant.name}</p>
        </div>
        <CartPanel className="min-h-0 flex-1" />
      </aside>
    </div>
  );
}
