/** Admin-only client for /api/onboarding (menu upload -> draft -> live page). */

export type DraftVariant = { name: string; price: string };

export type DraftItem = {
  category: string;
  name: string;
  price: string;
  description: string | null;
  item_type: "beverage" | "food" | "dessert";
  temperature: "hot" | "cold" | null;
  contains_coffee: boolean | null;
  is_vegetarian: boolean | null;
  tags: string[];
  variants: DraftVariant[];
};

export type DraftProfile = {
  name: string | null;
  tagline: string | null;
  address_line: string | null;
  city: string | null;
  phone: string | null;
};

export type DraftMenu = {
  items: DraftItem[];
  profile: DraftProfile;
  unparsed_lines: string[];
  warnings: string[];
  method: "vision" | "text-llm" | "text-rules";
};

export type CafeProfile = {
  name: string;
  slug: string;
  tagline: string;
  address_line: string;
  city: string;
  phone: string;
  brand_color: string;
  assistant_icon: "coffee" | "utensils" | "pizza" | "drink" | "dessert" | "tea";
};

export type PublishedCafe = {
  slug: string;
  name: string;
  path: string;
  item_count: number;
  category_count: number;
  city: string | null;
  published_at: string | null;
};

export type OnboardingStatus = { reads_photos_and_scans: boolean; max_upload_mb: number };

export class AdminError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function slugify(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/, "");
}

export const PRICE_RE = /^\d{1,7}(\.\d{1,2})?$/;

async function call<T>(key: string, path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? 60_000);
  let res: Response;
  try {
    res = await fetch(`/api/onboarding${path}`, {
      ...init,
      headers: { "X-Admin-Key": key, ...(init.headers || {}) },
      signal: controller.signal,
    });
  } catch {
    throw new AdminError("Couldn't reach the server (it may be waking up or the request timed out). Try again.", 0);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail =
        typeof body?.detail === "string"
          ? body.detail
          : Array.isArray(body?.errors)
            ? body.errors.map((e: { field: string; message: string }) => `${e.field}: ${e.message}`).join("; ")
            : "";
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401) detail = "That admin key isn't right.";
    if (res.status === 404 && !detail) detail = "Onboarding is off on this server (set ADMIN_API_KEY).";
    throw new AdminError(detail || `Request failed (${res.status})`, res.status);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" },
});

export const onboarding = {
  status: (key: string) => call<OnboardingStatus>(key, "/status", { timeoutMs: 90_000 }),
  extract: (key: string, files: File[], text: string) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("text", text);
    // Reading a long menu with Claude can take a few minutes.
    return call<DraftMenu>(key, "/menu/extract", { method: "POST", body: form, timeoutMs: 330_000 });
  },
  publish: (key: string, profile: CafeProfile, items: DraftItem[], replace: boolean) =>
    call<PublishedCafe>(key, "/restaurants", {
      ...json({
        profile: {
          ...profile,
          slug: profile.slug || null,
          tagline: profile.tagline || null,
          address_line: profile.address_line || null,
          city: profile.city || null,
          phone: profile.phone || null,
          brand_color: profile.brand_color || null,
        },
        items,
        replace,
      }),
    }),
  list: (key: string) => call<PublishedCafe[]>(key, "/restaurants"),
  remove: (key: string, slug: string) =>
    call<void>(key, `/restaurants/${encodeURIComponent(slug)}`, { method: "DELETE" }),
};

/** A short cold email pitching the café's live page. */
export function pitchEmail(cafe: { name: string; itemCount: number; url: string }, sender: string) {
  const subject = `${cafe.name}'s menu as an AI ordering assistant (free demo)`;
  const body = [
    `Hi ${cafe.name} team,`,
    "",
    `I turned your menu into a live AI menu assistant. Your customers can ask things like "a cold coffee under ₹200" or "starters for 4 under ₹2000" and get answers straight from your menu:`,
    "",
    cafe.url,
    "",
    `It already has all ${cafe.itemCount} items from your menu. There's nothing to install: put it on a QR code on your tables, or link it from your Instagram or Google profile.`,
    "",
    "I'd be happy to set it up properly for you (your photos, colours and any corrections). Would a 10-minute call this week work?",
    "",
    "Thanks,",
    sender || "[Your name]",
  ].join("\n");
  return { subject, body };
}
