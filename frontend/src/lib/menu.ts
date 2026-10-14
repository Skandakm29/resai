import type { MenuItem } from "./types";

/** The restaurant's featured items, photographed ones first. Safe on server and client. */
export function signatures(items: MenuItem[], max = 8): MenuItem[] {
  return items
    .filter((i) => i.is_featured && i.is_available)
    .sort((a, b) => Number(Boolean(b.image_url)) - Number(Boolean(a.image_url)))
    .slice(0, max);
}
