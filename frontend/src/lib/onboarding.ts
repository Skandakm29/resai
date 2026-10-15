/** Clients for menu upload -> draft -> live page: admin (/api/onboarding) and self-serve (/api/start). */

import { readMenuFiles, type PageText } from "./ocr";

/** The product name on the public landing page. */
export const PRODUCT = "Resai";

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
  method: "text-llm" | "text-rules";
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
  owner_name?: string | null;
  owner_email?: string | null;
};

export type Owner = { name: string; email: string };

export type OnboardingStatus = { reads_photos_and_scans: boolean; max_upload_mb: number; max_items?: number };

export const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;

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

/** `key` = admin key for /api/onboarding; null = the public /api/start endpoints. */
async function call<T>(key: string | null, path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? 60_000);
  let res: Response;
  try {
    res = await fetch(`${key === null ? "/api/start" : "/api/onboarding"}${path}`, {
      ...init,
      headers: { ...(key === null ? {} : { "X-Admin-Key": key }), ...(init.headers || {}) },
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
    if (res.status === 404 && !detail) detail = "Onboarding is off on this server.";
    if (res.status >= 500) detail = "Something went wrong on our side. Please try again.";
    throw new AdminError(detail || `Request failed (${res.status})`, res.status);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" },
});

function profileBody(profile: CafeProfile) {
  return {
    ...profile,
    slug: profile.slug || null,
    tagline: profile.tagline || null,
    address_line: profile.address_line || null,
    city: profile.city || null,
    phone: profile.phone || null,
    brand_color: profile.brand_color || null,
  };
}

export type ExtractProgress = { phase: "ocr"; done: number; total: number } | { phase: "structuring" };

async function extract(
  key: string | null,
  files: File[],
  text: string,
  onProgress?: (p: ExtractProgress) => void,
) {
  // OCR runs on this device; the server only organises the text into items.
  let pages: PageText[] | null = null;
  if (files.length) {
    try {
      pages = await readMenuFiles(files, (p) => onProgress?.({ phase: "ocr", ...p }));
    } catch (e) {
      console.warn("Reading the menu in the browser failed; uploading the files instead.", e);
    }
  }
  const form = new FormData();
  if (pages) form.append("pages", JSON.stringify(pages));
  else files.forEach((f) => form.append("files", f));
  form.append("text", text);
  onProgress?.({ phase: "structuring" });
  return call<DraftMenu>(key, key === null ? "/extract" : "/menu/extract", {
    method: "POST",
    body: form,
    timeoutMs: 330_000,
  });
}

/** What the upload and review steps need, for either the admin or the public page. */
export type OnboardClient = {
  status: () => Promise<OnboardingStatus>;
  extract: (files: File[], text: string, onProgress?: (p: ExtractProgress) => void) => Promise<DraftMenu>;
  publish: (profile: CafeProfile, items: DraftItem[], opts: { replace?: boolean; owner?: Owner }) => Promise<PublishedCafe>;
};

export function adminClient(key: string): OnboardClient {
  return {
    status: () => call<OnboardingStatus>(key, "/status", { timeoutMs: 90_000 }),
    extract: (files, text, onProgress) => extract(key, files, text, onProgress),
    publish: (profile, items, { replace = false }) =>
      call<PublishedCafe>(key, "/restaurants", json({ profile: profileBody(profile), items, replace })),
  };
}

export const publicClient: OnboardClient = {
  status: () => call<OnboardingStatus>(null, "/status", { timeoutMs: 90_000 }),
  extract: (files, text, onProgress) => extract(null, files, text, onProgress),
  publish: (profile, items, { owner }) =>
    call<PublishedCafe>(null, "/publish", json({ profile: profileBody(profile), items, owner })),
};

export const onboarding = {
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
