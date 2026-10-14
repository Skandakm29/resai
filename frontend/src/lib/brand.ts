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

/**
 * A restaurant's full look. `vars` override the CSS variables in globals.css;
 * `wordmark` replaces the initials badge in the header with the name set in
 * the display font (as on the restaurant's own printed menu).
 */
export type Theme = {
  vars: Record<string, string>;
  /** Dark "printed menu" header and welcome hero. */
  darkHeader?: boolean;
  wordmark?: string;
};

const THEMES: Record<string, Theme> = {
  // Moai: espresso-brown pages, caramel panels, cream paper - from the printed menu.
  moai: {
    darkHeader: true,
    wordmark: "moai",
    vars: {
      "--background": "38 33% 94%",
      "--foreground": "24 22% 13%",
      "--card": "40 45% 98%",
      "--card-foreground": "24 22% 13%",
      "--popover": "40 45% 98%",
      "--popover-foreground": "24 22% 13%",
      "--primary": "28 60% 40%",
      "--primary-foreground": "40 45% 97%",
      "--secondary": "32 40% 88%",
      "--secondary-foreground": "24 30% 20%",
      "--accent": "32 45% 90%",
      "--accent-foreground": "24 30% 20%",
      "--muted": "35 25% 90%",
      "--muted-foreground": "25 10% 36%",
      "--border": "32 20% 83%",
      "--input": "32 20% 78%",
      "--ring": "28 60% 40%",
      "--coffee": "24 30% 22%",
      "--coffee-light": "30 40% 80%",
      "--ink": "20 18% 11%",
      "--ink-foreground": "38 40% 93%",
    },
  },
};

export function themeFor(slug: string): Theme | null {
  return THEMES[slug] ?? null;
}

/** CSS for one restaurant: its full theme if it has one, else just its brand colour ("" = default theme). */
export function brandCss(color: string | null | undefined, slug?: string): string {
  const theme = slug ? themeFor(slug) : null;
  if (theme) return `:root{${Object.entries(theme.vars).map(([k, v]) => `${k}:${v};`).join("")}}`;
  const hsl = color ? hexToHslTriplet(color) : null;
  return hsl ? `:root{--primary:${hsl};--ring:${hsl};}` : "";
}
