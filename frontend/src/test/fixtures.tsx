import * as React from "react";
import { render } from "@testing-library/react";
import { AssistantProvider } from "@/components/assistant/assistant-context";
import { CartProvider } from "@/components/cart/cart-context";
import { ItemDialogProvider } from "@/components/menu/item-dialog";
import type { ChatResponse, MenuItem, Restaurant } from "@/lib/types";

export function makeItem(overrides: Partial<MenuItem> = {}): MenuItem {
  return {
    id: "item-" + Math.random().toString(36).slice(2, 8),
    category_id: "cat-1",
    category_name: "Hot Coffee",
    name: "Flat White",
    description: "A double ristretto with silky microfoam.",
    price: "230.00",
    price_from: "230.00",
    currency: "INR",
    is_available: true,
    image_url: null,
    item_type: "beverage",
    temperature: "hot",
    contains_coffee: true,
    caffeine_level: "high",
    strength: 4,
    sweetness: 1,
    serves: 1,
    dietary: { vegetarian: "yes", vegan: "no" },
    dietary_labels: ["Vegetarian"],
    ingredients: { status: "verified", items: ["ristretto", "whole milk"] },
    allergens: { status: "verified", items: ["milk"] },
    flavor_tags: ["toffee"],
    variant_required: false,
    variants: [],
    addons: [],
    is_featured: false,
    ...overrides,
  };
}

export const cappuccino = makeItem({
  id: "cap",
  name: "Classic Cappuccino",
  price: "210.00",
  price_from: "210.00",
  variant_required: true,
  variants: [
    { id: "cap-r", name: "Regular", price: "210.00", is_default: true, is_available: true },
    { id: "cap-l", name: "Large", price: "250.00", is_default: false, is_available: true },
  ],
  addons: [
    { id: "oat", name: "Oat milk", group_name: "Milk", price: "60.00", is_available: true },
    { id: "sfs", name: "Sugar-free syrup", group_name: "Syrups", price: "40.00", is_available: false },
  ],
});

export const flatWhite = makeItem({ id: "fw", name: "Flat White" });
export const spanishLatte = makeItem({ id: "sl", name: "Spanish Latte", price: "280.00", price_from: "280.00", is_available: false });

export const restaurant: Restaurant = {
  id: "r1",
  slug: "fernwood",
  name: "Fernwood Coffee Roasters",
  tagline: null,
  address_line: "12, 100 Feet Road",
  city: "Bengaluru",
  phone: null,
  logo_url: null,
  currency: "INR",
  settings: {
    assistant_name: "Your Coffee Guide",
    welcome_message: "Hi! What are you in the mood for today?",
    suggested_prompts: ["Recommend a coffee under ₹250", "Something cold and not too sweet"],
    ai_enabled: true,
    pickup_enabled: true,
    ordering_enabled: false,
    allergen_disclaimer: "",
    brand_color: null,
    assistant_icon: "coffee",
  },
};

export function chatResponse(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    conversation_id: "conv-1",
    message: "Here are 2 coffees at or under ₹250. My top pick is the Classic Cappuccino.",
    intent: "recommend",
    recommendations: [
      { item: cappuccino, reasons: ["From ₹210 - within your ₹250 budget"], note: null, suggested_quantity: 1, estimated_total: "210.00", over_budget: false },
      { item: flatWhite, reasons: ["₹230 - within your ₹250 budget"], note: null, suggested_quantity: 1, estimated_total: "230.00", over_budget: false },
    ],
    comparison: null,
    clarification: null,
    follow_ups: ["Something cold instead?"],
    filter_summary: ["Coffee", "Up to ₹250"],
    source: "rules",
    ...overrides,
  };
}

export function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

export function renderWithProviders(ui: React.ReactElement) {
  return render(
    <CartProvider slug="fernwood">
      <AssistantProvider slug="fernwood">
        <ItemDialogProvider>{ui}</ItemDialogProvider>
      </AssistantProvider>
    </CartProvider>,
  );
}
