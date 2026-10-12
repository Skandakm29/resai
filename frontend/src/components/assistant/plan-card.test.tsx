import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PlanCard } from "@/components/assistant/plan-card";
import { CartPanel } from "@/components/cart/cart-panel";
import { cappuccino, flatWhite, makeItem, renderWithProviders } from "@/test/fixtures";
import type { MealPlan } from "@/lib/types";

const fries = makeItem({ id: "fries", name: "French Fries", item_type: "food", price: "200.00", price_from: "200.00" });
const plan: MealPlan = {
  party_size: 2,
  budget: "1000.00",
  lines: [
    { course: "starter", item: fries, variant_id: null, variant_name: null, quantity: 1, unit_price: "200.00", line_total: "200.00" },
    { course: "main", item: cappuccino, variant_id: "cap-l", variant_name: "Large", quantity: 1, unit_price: "250.00", line_total: "250.00" },
    { course: "main", item: flatWhite, variant_id: null, variant_name: null, quantity: 2, unit_price: "230.00", line_total: "460.00" },
  ],
  course_subtotals: [
    { course: "starter", items: 1, subtotal: "200.00" },
    { course: "main", items: 3, subtotal: "710.00" },
  ],
  total: "910.00",
  per_person: "455.00",
  remaining: "90.00",
  within_budget: true,
  assumptions: ["One main course each"],
};

describe("PlanCard", () => {
  it("shows the breakdown and adds the whole plan to the cart", async () => {
    renderWithProviders(
      <>
        <PlanCard plan={plan} />
        <CartPanel />
      </>,
    );
    const card = screen.getByRole("region", { name: "Meal plan" });
    expect(within(card).getByText("Within budget")).toBeInTheDocument();
    expect(within(card).getByTestId("subtotal-main")).toHaveTextContent("₹710");
    expect(within(card).getByTestId("plan-total")).toHaveTextContent("₹910");
    expect(within(card).getByText("₹455")).toBeInTheDocument();
    expect(within(card).getByText("₹90")).toBeInTheDocument();
    expect(within(card).getByText("(Large)")).toBeInTheDocument();

    await userEvent.click(within(card).getByRole("button", { name: /Add whole plan to cart/ }));
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("₹910");
    expect(screen.getByText("Large")).toBeInTheDocument(); // cart line keeps the chosen option
  });

  it("flags an over-budget plan", () => {
    renderWithProviders(<PlanCard plan={{ ...plan, within_budget: false, remaining: "-90.00" }} />);
    expect(screen.getByText("Over budget")).toBeInTheDocument();
    expect(screen.getByText("Over by")).toBeInTheDocument();
  });
});
