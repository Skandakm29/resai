// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

describe("server-side API calls", () => {
  it("retry while the backend is waking up (gateway errors / no connection)", async () => {
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(json({ detail: "waking" }, 503))
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockReturnValueOnce(json({ slug: "meloghrano" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.restaurant("meloghrano")).resolves.toEqual({ slug: "meloghrano" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  }, 15000);

  it("do not retry real errors like 404", async () => {
    const fetchMock = vi.fn().mockReturnValue(json({ detail: "Restaurant 'x' not found" }, 404));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.restaurant("x")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
