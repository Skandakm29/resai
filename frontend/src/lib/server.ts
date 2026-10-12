import "server-only";
import { cache } from "react";
import { api, ApiError } from "./api";

/** Deduplicated per request across layout + page. Returns null for unknown restaurants. */
export const getRestaurant = cache(async (slug: string) => {
  try {
    return await api.restaurant(slug);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
});
