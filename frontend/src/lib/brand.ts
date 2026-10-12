import { CakeSlice, Coffee, CupSoda, Leaf, Pizza, Sparkles, UtensilsCrossed, type LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  coffee: Coffee,
  utensils: UtensilsCrossed,
  pizza: Pizza,
  drink: CupSoda,
  dessert: CakeSlice,
  tea: Leaf,
};

/** The restaurant's assistant icon (falls back to a neutral sparkle). */
export function assistantIcon(name: string | null | undefined): LucideIcon {
  return (name && ICONS[name]) || Sparkles;
}

/** "#8E2433" -> "352 59% 35%" (the HSL triplet format our CSS variables use). */
export function hexToHslTriplet(hex: string): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

/** CSS overriding the theme's primary colour for one restaurant, or "" for the default theme. */
export function brandCss(color: string | null | undefined): string {
  const hsl = color ? hexToHslTriplet(color) : null;
  return hsl ? `:root{--primary:${hsl};--ring:${hsl};}` : "";
}
