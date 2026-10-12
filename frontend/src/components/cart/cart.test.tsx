import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CartPanel } from "@/components/cart/cart-panel";
import { buildLine, useCart } from "@/components/cart/cart-context";
import { cappuccino, flatWhite, jsonResponse, renderWithProviders } from "@/test/fixtures";

let cartApi: ReturnType<typeof useCart>;
function Grab() {
  cartApi = useCart();
  return null;
}

function setup() {
  renderWithProviders(
    <>
      <Grab />
      <CartPanel />
    </>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("Cart", () => {
  it("shows an empty state", () => {
    setup();
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });

  it("adds, merges identical lines, changes quantity and removes items", async () => {
    setup();
    act(() => cartApi.add(buildLine(flatWhite, null, [], 1)));
    act(() => cartApi.add(buildLine(flatWhite, null, [], 1)));
    act(() => cartApi.add(buildLine(cappuccino, cappuccino.variants[1], [cappuccino.addons[0]], 1)));

    const list = screen.getByRole("list", { name: "Cart items" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByLabelText("Flat White quantity")).toHaveTextContent("2");
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("₹770"); // 2×230 + 250+60

    await userEvent.click(screen.getByRole("button", { name: "Increase Flat White" }));
    expect(screen.getByLabelText("Flat White quantity")).toHaveTextContent("3");
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("₹1,000");

    await userEvent.click(screen.getByRole("button", { name: "Decrease Classic Cappuccino" }));
    expect(screen.queryByText("Classic Cappuccino")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Remove Flat White" }));
    expect(screen.getByText("Your cart is empty")).toBeInTheDocument();
  });

  it("persists the cart to localStorage for continued browsing", () => {
    setup();
    act(() => cartApi.add(buildLine(flatWhite, null, [], 2)));
    const stored = JSON.parse(window.localStorage.getItem("cart:fernwood")!);
    expect(stored[0]).toMatchObject({ itemId: "fw", quantity: 2, unitPrice: "230.00" });
  });

  it("validates with the backend and uses the canonical price", async () => {
    const fetchMock = vi.fn().mockReturnValue(
      jsonResponse({
        valid: false,
        currency: "INR",
        subtotal: "240.00",
        item_count: 1,
        ordering_enabled: false,
        message: "Some items need your attention before checkout.",
        lines: [
          { item_id: "fw", name: "Flat White", variant_id: null, variant_name: null, addons: [], quantity: 1, unit_price: "240.00", line_total: "240.00", status: "price_changed", issues: ["Price updated from ₹230 to ₹240."] },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setup();
    act(() => cartApi.add(buildLine(flatWhite, null, [], 1)));
    await userEvent.click(screen.getByRole("button", { name: "Review & checkout" }));

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({
      restaurant_slug: "fernwood",
      lines: [{ item_id: "fw", variant_id: null, addon_ids: [], quantity: 1, unit_price: "230.00" }],
    });
    expect(await screen.findByText("Price updated from ₹230 to ₹240.")).toBeInTheDocument();
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("₹240");
    expect(screen.getByRole("status")).toHaveTextContent("Some items need your attention");
  });
});
