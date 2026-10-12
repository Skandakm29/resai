"use client";

import { Info, ShoppingBag, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { buildLine, useCart } from "@/components/cart/cart-context";
import { useItemDialog } from "@/components/menu/item-dialog";
import { formatINR } from "@/lib/money";
import type { Course, MealPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const COURSE_TITLE: Record<Course, string> = { starter: "Starters", main: "Mains", dessert: "Desserts", drink: "Drinks" };

/** A complete order built by the backend: every figure here is server-computed. */
export function PlanCard({ plan }: { plan: MealPlan }) {
  const cart = useCart();
  const dialog = useItemDialog();
  const count = plan.lines.reduce((n, l) => n + l.quantity, 0);

  function addAll() {
    for (const line of plan.lines) {
      const variant = line.item.variants.find((v) => v.id === line.variant_id) ?? null;
      cart.add(buildLine(line.item, variant, [], line.quantity));
    }
    toast.success(`Added ${count} dishes to your cart`);
  }

  return (
    <section className="overflow-hidden rounded-3xl border bg-card shadow-sm" aria-label="Meal plan">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/40 px-4 py-3">
        <p className="flex items-center gap-2 font-semibold">
          <Users className="h-4 w-4 text-primary" />
          Plan for {plan.party_size}
          {plan.budget && <span className="font-normal text-muted-foreground">· budget {formatINR(plan.budget)}</span>}
        </p>
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-xs font-medium",
            plan.within_budget ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive",
          )}
        >
          {plan.within_budget ? "Within budget" : "Over budget"}
        </span>
      </header>

      <div className="divide-y">
        {plan.course_subtotals.map((group) => (
          <div key={group.course} className="px-4 py-3">
            <div className="mb-1.5 flex items-baseline justify-between text-xs uppercase tracking-wide text-muted-foreground">
              <span>{COURSE_TITLE[group.course]}</span>
              <span data-testid={`subtotal-${group.course}`}>{formatINR(group.subtotal)}</span>
            </div>
            <ul className="space-y-1.5">
              {plan.lines
                .filter((l) => l.course === group.course)
                .map((l) => (
                  <li key={`${l.course}-${l.item.id}`} className="flex items-center justify-between gap-3 text-sm">
                    <button
                      type="button"
                      onClick={() => dialog.open(l.item)}
                      className="flex min-w-0 items-center gap-1.5 text-left hover:underline"
                    >
                      <span className="truncate">
                        {l.quantity > 1 && `${l.quantity} × `}
                        {l.item.name}
                      </span>
                      {l.variant_name && <span className="shrink-0 text-xs text-muted-foreground">({l.variant_name})</span>}
                    </button>
                    <span className="shrink-0 tabular-nums">{formatINR(l.line_total)}</span>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </div>

      <dl className="grid grid-cols-3 gap-2 border-t bg-muted/40 px-4 py-3 text-center">
        <div>
          <dt className="text-xs text-muted-foreground">Total</dt>
          <dd className="font-semibold" data-testid="plan-total">{formatINR(plan.total)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Per person</dt>
          <dd className="font-semibold">{formatINR(plan.per_person)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{plan.remaining && plan.remaining.startsWith("-") ? "Over by" : "Left"}</dt>
          <dd className={cn("font-semibold", plan.remaining?.startsWith("-") && "text-destructive")}>
            {plan.remaining === null ? "—" : formatINR(plan.remaining.replace("-", ""))}
          </dd>
        </div>
      </dl>

      <div className="space-y-3 px-4 py-3">
        <ul className="space-y-0.5 text-xs text-muted-foreground">
          {plan.assumptions.map((a) => (
            <li key={a} className="flex gap-1.5">
              <Info className="mt-0.5 h-3 w-3 shrink-0" />
              {a}
            </li>
          ))}
        </ul>
        <Button className="w-full" onClick={addAll}>
          <ShoppingBag /> Add whole plan to cart · {formatINR(plan.total)}
        </Button>
      </div>
    </section>
  );
}
