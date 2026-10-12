"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MapPin, ShoppingBag } from "lucide-react";
import { Toaster } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { AssistantProvider } from "@/components/assistant/assistant-context";
import { CartPanel } from "@/components/cart/cart-panel";
import { CartProvider, useCart } from "@/components/cart/cart-context";
import { ItemDialogProvider } from "@/components/menu/item-dialog";
import { brandCss } from "@/lib/brand";
import { formatINR, fromPaise } from "@/lib/money";
import type { Restaurant } from "@/lib/types";
import { cn } from "@/lib/utils";

const CartDrawerContext = React.createContext<() => void>(() => {});
export const useOpenCart = () => React.useContext(CartDrawerContext);

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w))
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

function Header({ restaurant, onOpenCart }: { restaurant: Restaurant; onOpenCart: () => void }) {
  const cart = useCart();
  const pathname = usePathname();
  const base = `/r/${restaurant.slug}`;
  const tabs = [
    { href: base, label: "Assistant" },
    { href: `${base}/menu`, label: "Menu" },
  ];
  return (
    <header className="border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4">
        <div
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary font-display text-sm font-semibold text-primary-foreground"
        >
          {initials(restaurant.name)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-base font-semibold leading-tight sm:text-lg">{restaurant.name}</p>
          <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{[restaurant.address_line, restaurant.city].filter(Boolean).join(", ")}</span>
            {restaurant.settings.pickup_enabled && <span className="hidden sm:inline"> · Pickup</span>}
          </p>
        </div>
        <nav className="hidden items-center rounded-full bg-muted p-1 sm:flex" aria-label="Sections">
          {tabs.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              aria-current={pathname === t.href ? "page" : undefined}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                pathname === t.href ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
        <Button variant="outline" className="relative px-3 sm:px-4" onClick={onOpenCart} aria-label={`Open cart, ${cart.itemCount} items`}>
          <ShoppingBag />
          <span className="hidden sm:inline">Cart</span>
          {cart.itemCount > 0 && (
            <span
              className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-coffee px-1 text-[11px] font-semibold text-white"
              data-testid="cart-count"
            >
              {cart.itemCount}
            </span>
          )}
        </Button>
      </div>
      <nav className="flex border-t sm:hidden" aria-label="Sections">
        {tabs.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            aria-current={pathname === t.href ? "page" : undefined}
            className={cn(
              "flex-1 border-b-2 py-2 text-center text-sm font-medium",
              pathname === t.href ? "border-primary text-primary" : "border-transparent text-muted-foreground",
            )}
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

/** Slim "view cart" bar on small screens, where the cart sidebar is hidden. */
export function MobileCartBar({ onOpen }: { onOpen: () => void }) {
  const cart = useCart();
  if (cart.itemCount === 0) return null;
  return (
    <div className="border-b bg-secondary/60 px-4 py-2 lg:hidden" data-testid="mobile-cart-bar">
      <button type="button" onClick={onOpen} className="mx-auto flex w-full max-w-3xl items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium text-secondary-foreground">
          <ShoppingBag className="h-4 w-4" />
          {cart.itemCount} item{cart.itemCount === 1 ? "" : "s"} · {formatINR(fromPaise(cart.subtotalPaise))}
        </span>
        <span className="font-semibold text-primary">View cart →</span>
      </button>
    </div>
  );
}

function ShellInner({ restaurant, children }: { restaurant: Restaurant; children: React.ReactNode }) {
  const [cartOpen, setCartOpen] = React.useState(false);
  const openCart = React.useCallback(() => setCartOpen(true), []);
  return (
    <CartDrawerContext.Provider value={openCart}>
      <div className="flex h-dvh flex-col overflow-hidden">
        <Header restaurant={restaurant} onOpenCart={openCart} />
        <MobileCartBar onOpen={openCart} />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      <Dialog open={cartOpen} onOpenChange={setCartOpen}>
        <DialogContent side="right">
          <div className="border-b px-4 py-4 pr-14">
            <DialogTitle>Your cart</DialogTitle>
            <DialogDescription>Pickup from {restaurant.name}</DialogDescription>
          </div>
          <CartPanel className="min-h-0 flex-1" />
        </DialogContent>
      </Dialog>
    </CartDrawerContext.Provider>
  );
}

export function RestaurantShell({ restaurant, children }: { restaurant: Restaurant; children: React.ReactNode }) {
  return (
    <CartProvider slug={restaurant.slug}>
      {/* Per-restaurant brand colour; applies to dialogs rendered in portals too. */}
      {restaurant.settings.brand_color && <style>{brandCss(restaurant.settings.brand_color)}</style>}
      <AssistantProvider slug={restaurant.slug}>
        <ItemDialogProvider>
          <ShellInner restaurant={restaurant}>{children}</ShellInner>
          <Toaster position="top-center" richColors closeButton />
        </ItemDialogProvider>
      </AssistantProvider>
    </CartProvider>
  );
}
