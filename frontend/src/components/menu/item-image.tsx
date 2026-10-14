import { CakeSlice, Coffee, CupSoda, Pizza, Salad, Sandwich, Soup, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MenuItem } from "@/lib/types";

/**
 * Real photo when the restaurant provides one; otherwise a neutral,
 * clearly-illustrative placeholder (never a fake "photo" of the dish).
 */
function foodIcon(name: string, category: string) {
  const text = `${name} ${category}`.toLowerCase();
  if (/pizza/.test(text)) return Pizza;
  if (/soup|zuppa/.test(text)) return Soup;
  if (/salad/.test(text)) return Salad;
  if (/pasta|risotto|lasagna|gnocchi|main|platter|steak/.test(text)) return UtensilsCrossed;
  return Sandwich;
}

type ImageItem = Pick<MenuItem, "name" | "image_url" | "item_type" | "temperature"> & { category_name?: string };

export function ItemImage({ item, className }: { item: ImageItem; className?: string }) {
  if (item.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={item.image_url} alt={item.name} className={cn("h-full w-full object-cover", className)} loading="lazy" />;
  }
  const Icon =
    item.item_type === "dessert"
      ? CakeSlice
      : item.item_type === "food"
        ? foodIcon(item.name, item.category_name ?? "")
        : item.temperature === "cold"
          ? CupSoda
          : Coffee;
  // Warm, theme-coloured tile (follows each restaurant's palette).
  const tone =
    item.item_type === "beverage" && item.temperature === "cold"
      ? "from-accent via-secondary to-muted"
      : "from-secondary via-accent to-muted";
  return (
    <div
      role="img"
      aria-label={`${item.name} (no photo available)`}
      className={cn("flex h-full w-full items-center justify-center bg-gradient-to-br", tone, className)}
    >
      <Icon className="h-1/3 max-h-12 w-1/3 max-w-12 text-primary/45" strokeWidth={1.25} />
    </div>
  );
}
