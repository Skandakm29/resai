import type { CartValidation, ChatResponse, Menu, MenuItem, Restaurant } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryable: boolean,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Server components call the backend directly; the browser goes through the Next.js /api proxy. */
function baseUrl(): string {
  if (typeof window === "undefined") return (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  return "";
}

const WAKE_STATUSES = new Set([0, 502, 503, 504]);

/**
 * Server-side GETs retry while the backend is unreachable or returns a
 * gateway error - on free hosting the API sleeps when idle and takes up to
 * about a minute to wake. Other requests fail fast (the chat has a Retry).
 */
async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const isServerGet = typeof window === "undefined" && (!init?.method || init.method === "GET");
  if (!isServerGet) return requestOnce<T>(path, init);
  const deadline = Date.now() + 75_000;
  let delay = 1000;
  for (;;) {
    try {
      return await requestOnce<T>(path, { ...init, timeoutMs: Math.max(5000, deadline - Date.now()) });
    } catch (e) {
      if (!(e instanceof ApiError) || !WAKE_STATUSES.has(e.status) || Date.now() + delay > deadline) throw e;
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(delay * 2, 5000);
    }
  }
}

async function requestOnce<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  // Server-side calls get longer: a sleeping free-tier backend can take ~a minute to wake.
  const timer = setTimeout(() => controller.abort(), init?.timeoutMs ?? (typeof window === "undefined" ? 70000 : 30000));
  let res: Response;
  try {
    res = await fetch(`${baseUrl()}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      signal: controller.signal,
    });
  } catch {
    throw new ApiError("We couldn't reach the café right now. Check your connection and try again.", 0, true);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 429) throw new ApiError(detail || "You're sending messages quickly - please wait a moment.", 429, true);
    if (res.status >= 500) throw new ApiError("Something went wrong on our side. Please try again.", res.status, true);
    throw new ApiError(detail || "That request couldn't be completed.", res.status, false);
  }
  return (await res.json()) as T;
}

export const api = {
  restaurant: (slug: string) => request<Restaurant>(`/api/restaurants/${encodeURIComponent(slug)}`, { cache: "no-store" }),
  menu: (slug: string) => request<Menu>(`/api/restaurants/${encodeURIComponent(slug)}/menu`, { cache: "no-store" }),
  item: (slug: string, id: string) =>
    request<MenuItem>(`/api/restaurants/${encodeURIComponent(slug)}/menu/items/${encodeURIComponent(id)}`),
  chat: (
    slug: string,
    body: {
      conversation_id: string | null;
      message: string;
      history: { role: "user" | "assistant"; content: string }[];
      cart: { item_id: string; quantity: number }[];
    },
  ) =>
    request<ChatResponse>(`/api/restaurants/${encodeURIComponent(slug)}/assistant/chat`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 45000,
    }),
  validateCart: (body: {
    restaurant_slug: string;
    lines: { item_id: string; variant_id: string | null; addon_ids: string[]; quantity: number; unit_price: string }[];
  }) => request<CartValidation>("/api/cart/validate", { method: "POST", body: JSON.stringify(body) }),
};
