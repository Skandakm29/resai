import { describe, expect, it } from "vitest";
import { formatINR, fromPaise, toPaise } from "./money";

describe("money", () => {
  it("converts decimal strings to integer paise without float drift", () => {
    expect(toPaise("210.00")).toBe(21000);
    expect(toPaise("0.1")).toBe(10);
    expect(toPaise("249.99")).toBe(24999);
    expect(fromPaise(toPaise("0.10") + toPaise("0.20"))).toBe("0.30");
  });

  it("formats INR", () => {
    expect(formatINR("250.00")).toBe("₹250");
    expect(formatINR("1160.00")).toBe("₹1,160");
    expect(formatINR("249.50")).toBe("₹249.50");
  });

  it("rejects malformed amounts", () => {
    expect(() => toPaise("abc")).toThrow();
  });
});
