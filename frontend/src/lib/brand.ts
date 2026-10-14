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
  /** Dark brand-coloured header and welcome hero. */
  darkHeader?: boolean;
  wordmark?: string;
  /** Logo image for the dark header (replaces the wordmark). */
  logo?: string;
  /** Small uppercase line above the welcome title, and a motto under it. */
  eyebrow?: string;
  motto?: string;
};

const THEMES: Record<string, Theme> = {
  // Moai: matches moaiveg.com - #004F00 green, white and beige, peach accent,
  // Playfair Display headings over Inter.
  moai: {
    darkHeader: true,
    wordmark: "moai",
    logo: "/r/moai/logo.png",
    eyebrow: "Pure veg fine dining in Bangalore",
    motto: "Mingle Over Artisanal Infusions",
    vars: {
      "--background": "40 15% 97%",
      "--foreground": "140 20% 15%",
      "--card": "0 0% 100%",
      "--card-foreground": "140 20% 15%",
      "--popover": "0 0% 100%",
      "--popover-foreground": "140 20% 15%",
      "--primary": "140 60% 20%",
      "--primary-foreground": "0 0% 98%",
      "--secondary": "31 98% 92%",
      "--secondary-foreground": "25 30% 28%",
      "--accent": "31 98% 92%",
      "--accent-foreground": "25 30% 28%",
      "--muted": "40 15% 94%",
      "--muted-foreground": "140 15% 38%",
      "--border": "140 15% 88%",
      "--input": "140 15% 84%",
      "--ring": "140 60% 20%",
      "--coffee": "25 30% 40%",
      "--coffee-light": "30 25% 65%",
      "--ink": "120 100% 15.5%",
      "--ink-foreground": "0 0% 98%",
      "--glow": "140 50% 40%",
      "--highlight": "31 98% 83%",
      "--highlight-foreground": "120 100% 12%",
      "--brand-display": "var(--font-playfair)",
      "--brand-sans": "var(--font-inter)",
      "--display-weight": "700",
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
