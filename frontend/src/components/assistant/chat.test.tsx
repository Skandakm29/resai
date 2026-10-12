import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Chat } from "@/components/assistant/chat";
import { CartPanel } from "@/components/cart/cart-panel";
import { chatResponse, jsonResponse, renderWithProviders, restaurant, spanishLatte } from "@/test/fixtures";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function lastRequestBody() {
  const [, init] = fetchMock.mock.calls.at(-1)!;
  return JSON.parse(init.body);
}

describe("Chat", () => {
  it("shows the welcome screen with clickable suggested prompts", async () => {
    fetchMock.mockReturnValue(jsonResponse(chatResponse()));
    renderWithProviders(<Chat restaurant={restaurant} />);
    expect(screen.getByRole("heading", { name: "Your Coffee Guide" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));

    expect(fetchMock).toHaveBeenCalledWith("/api/restaurants/fernwood/assistant/chat", expect.objectContaining({ method: "POST" }));
    expect(lastRequestBody().message).toBe("Recommend a coffee under ₹250");
    expect(await screen.findByText(/My top pick is the Classic Cappuccino/)).toBeInTheDocument();
  });

  it("sends with Enter, shows a loading state and disables sending while pending", async () => {
    let resolve!: (r: Response) => void;
    fetchMock.mockReturnValue(new Promise<Response>((r) => (resolve = r)));
    renderWithProviders(<Chat restaurant={restaurant} />);

    const input = screen.getByLabelText("Message Your Coffee Guide");
    await userEvent.type(input, "coffee under 250{Enter}");

    expect(screen.getByText("coffee under 250")).toBeInTheDocument(); // user bubble
    expect(screen.getByRole("status", { name: "Assistant is typing" })).toBeInTheDocument();
    await userEvent.type(input, "another");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolve(new Response(JSON.stringify(chatResponse()), { status: 200 }));
    expect(await screen.findByText(/My top pick/)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Assistant is typing" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  it("does not send blank messages", async () => {
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.type(screen.getByLabelText("Message Your Coffee Guide"), "   {Enter}");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders recommendation cards with real prices, reasons, filters and follow-ups", async () => {
    fetchMock.mockReturnValue(jsonResponse(chatResponse()));
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));

    const card = await screen.findByRole("article", { name: "Classic Cappuccino" });
    expect(within(card).getByTestId("rec-price")).toHaveTextContent("from ₹210");
    expect(within(card).getByText("From ₹210 - within your ₹250 budget")).toBeInTheDocument();
    expect(within(card).getByText("Vegetarian")).toBeInTheDocument();
    expect(within(card).getByText(/Sizes: Regular, Large · 1 add-on available/)).toBeInTheDocument();
    expect(screen.getByText("Up to ₹250")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Something cold instead?" }));
    expect(lastRequestBody().message).toBe("Something cold instead?");
    expect(lastRequestBody().conversation_id).toBe("conv-1");
  });

  it("disables adding unavailable items", async () => {
    fetchMock.mockReturnValue(
      jsonResponse(chatResponse({ recommendations: [{ item: spanishLatte, reasons: [], note: null, suggested_quantity: 1, estimated_total: "280.00", over_budget: false }] })),
    );
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));
    const card = await screen.findByRole("article", { name: "Spanish Latte" });
    expect(within(card).getByRole("button", { name: "Spanish Latte is unavailable" })).toBeDisabled();
    expect(within(card).getByText("Unavailable", { selector: "span" })).toBeInTheDocument();
  });

  it("shows a recoverable error and retries the same message", async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ detail: "boom" }, 503)).mockReturnValueOnce(jsonResponse(chatResponse()));
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong on our side");
    await userEvent.click(within(alert).getByRole("button", { name: /Retry/ }));

    expect(await screen.findByText(/My top pick/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(lastRequestBody().message).toBe("Recommend a coffee under ₹250");
    expect(screen.getAllByText("Recommend a coffee under ₹250")).toHaveLength(1); // no duplicate user bubble
  });

  it("starts a new chat", async () => {
    fetchMock.mockReturnValue(jsonResponse(chatResponse()));
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));
    await screen.findByText(/My top pick/);
    await userEvent.click(screen.getByRole("button", { name: /New chat/ }));
    expect(screen.getByRole("heading", { name: "Your Coffee Guide" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));
    expect(lastRequestBody().conversation_id).toBeNull();
  });

  it("requires a size before adding a variant item, then adds it to the cart", async () => {
    fetchMock.mockReturnValue(jsonResponse(chatResponse()));
    renderWithProviders(
      <>
        <Chat restaurant={restaurant} />
        <CartPanel />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add Classic Cappuccino to cart" }));

    const dialog = await screen.findByRole("dialog");
    const addButton = within(dialog).getByRole("button", { name: "Choose a size" });
    expect(addButton).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: /Sugar-free syrup/ })).toBeDisabled();

    await userEvent.click(within(dialog).getByRole("radio", { name: /Large/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: /Oat milk/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Increase quantity" }));
    const confirm = within(dialog).getByRole("button", { name: "Add to cart · ₹620" });
    await userEvent.click(confirm);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const cartList = screen.getByRole("list", { name: "Cart items" });
    expect(within(cartList).getByText("Classic Cappuccino")).toBeInTheDocument();
    expect(within(cartList).getByText("Large · + Oat milk")).toBeInTheDocument();
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("₹620");
  });

  it("sends cart context with chat requests", async () => {
    fetchMock.mockReturnValue(jsonResponse(chatResponse()));
    renderWithProviders(<Chat restaurant={restaurant} />);
    await userEvent.click(screen.getByRole("button", { name: "Recommend a coffee under ₹250" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add Flat White to cart" }));
    await userEvent.type(screen.getByLabelText("Message Your Coffee Guide"), "what pairs with my order?{Enter}");
    expect(lastRequestBody().cart).toEqual([{ item_id: "fw", quantity: 1 }]);
  });
});
