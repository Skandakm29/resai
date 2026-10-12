import { CakeSlice, Coffee, CupSoda, Sandwich } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MenuItem } from "@/lib/types";

/**
 * Real photo when the restaurant provides one; otherwise a neutral,
 * clearly-illustrative placeholder (never a fake "photo" of the dish).
 */
export function ItemImage({ item, className }: { item: Pick<MenuItem, "name" | "image_url" | "item_type" | "temperature">; className?: string }) {
  if (item.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={item.image_url} alt={item.name} className={cn("h-full w-full object-cover", className)} loading="lazy" />;
  }
  const Icon =
    item.item_type === "dessert" ? CakeSlice : item.item_type === "food" ? Sandwich : item.temperature === "cold" ? CupSoda : Coffee;
  const tone =
    item.item_type === "beverage"
      ? item.temperature === "cold"
        ? "from-[hsl(195_30%_90%)] to-[hsl(36_40%_88%)]"
        : "from-[hsl(30_40%_86%)] to-[hsl(36_45%_92%)]"
      : item.item_type === "dessert"
        ? "from-[hsl(15_45%_90%)] to-[hsl(36_45%_92%)]"
        : "from-[hsl(95_22%_88%)] to-[hsl(36_45%_92%)]";
  return (
    <div
      role="img"
      aria-label={`${item.name} (no photo available)`}
      className={cn("flex h-full w-full items-center justify-center bg-gradient-to-br", tone, className)}
    >
      <Icon className="h-1/3 max-h-12 w-1/3 max-w-12 text-coffee/45" strokeWidth={1.5} />
    </div>
  );
}
