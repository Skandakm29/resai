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
  // Moai: deep forest green (#223929) on warm cream (#FFF6EB), from its printed menu.
  moai: {
    darkHeader: true,
    wordmark: "moai",
    vars: {
      "--background": "34 100% 96%",
      "--foreground": "140 25% 12%",
      "--card": "36 100% 99%",
      "--card-foreground": "140 25% 12%",
      "--popover": "36 100% 99%",
      "--popover-foreground": "140 25% 12%",
      "--primary": "138 25% 22%",
      "--primary-foreground": "36 100% 97%",
      "--secondary": "100 18% 88%",
      "--secondary-foreground": "140 25% 16%",
      "--accent": "34 70% 91%",
      "--accent-foreground": "140 25% 16%",
      "--muted": "60 20% 91%",
      "--muted-foreground": "140 8% 34%",
      "--border": "60 14% 83%",
      "--input": "60 14% 78%",
      "--ring": "138 25% 30%",
      "--coffee": "140 25% 18%",
      "--coffee-light": "100 18% 80%",
      "--ink": "138 25% 18%",
      "--ink-foreground": "34 100% 95%",
      "--glow": "100 35% 55%",
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
