import { act, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantPage } from "@/components/assistant/assistant-page";
import { buildLine, useCart } from "@/components/cart/cart-context";
import { MobileCartBar } from "@/components/shell";
import { flatWhite, renderWithProviders, restaurant } from "@/test/fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/r/fernwood" }));

let cartApi: ReturnType<typeof useCart>;
function Grab() {
  cartApi = useCart();
  return null;
}

/*
 * jsdom has no layout engine, so these tests assert the responsive contract
 * (which elements exist and which breakpoint classes hide/show them). Real
 * rendering at 390px and 1366px was verified in a browser - see docs/TESTING.md.
 */
describe("Responsive layout", () => {
  it("hides the cart sidebar on mobile and shows it from the lg breakpoint", () => {
    renderWithProviders(<AssistantPage restaurant={restaurant} />);
    const aside = screen.getByTestId("desktop-cart");
    expect(aside).toHaveClass("hidden", "lg:flex");
    // Chat column must be able to shrink below its content width on phones.
    expect(aside.parentElement).toHaveClass("grid-cols-[minmax(0,1fr)]");
  });

  it("shows a mobile-only cart bar once the cart has items", () => {
    const onOpen = vi.fn();
    renderWithProviders(
      <>
        <Grab />
        <MobileCartBar onOpen={onOpen} />
      </>,
    );
    expect(screen.queryByTestId("mobile-cart-bar")).not.toBeInTheDocument();
    act(() => cartApi.add(buildLine(flatWhite, null, [], 2)));
    const bar = screen.getByTestId("mobile-cart-bar");
    expect(bar).toHaveClass("lg:hidden");
    expect(bar).toHaveTextContent("2 items · ₹460");
    act(() => bar.querySelector("button")!.click());
    expect(onOpen).toHaveBeenCalled();
  });
});

