"use client";

import * as React from "react";
import { useCart } from "@/components/cart/cart-context";
import { api, ApiError } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

export type ChatMessage =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; response: ChatResponse }
  | { id: string; role: "error"; content: string; retryText: string; retryable: boolean };

interface AssistantContextValue {
  messages: ChatMessage[];
  pending: boolean;
  send: (text: string) => void;
  retry: (errorId: string) => void;
  reset: () => void;
}

const AssistantContext = React.createContext<AssistantContextValue | null>(null);

let counter = 0;
const nextId = () => `m${Date.now().toString(36)}${(counter++).toString(36)}`;

interface Stored {
  conversationId: string | null;
  messages: ChatMessage[];
}

export function AssistantProvider({ slug, children }: { slug: string; children: React.ReactNode }) {
  const cart = useCart();
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [pending, setPending] = React.useState(false);
  const conversationId = React.useRef<string | null>(null);
  const pendingRef = React.useRef(false);
  const storageKey = `chat:${slug}`;

  // Restore the conversation for this tab (survives reloads, not new tabs).
  React.useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (raw) {
        const stored = JSON.parse(raw) as Stored;
        conversationId.current = stored.conversationId;
        setMessages(stored.messages.filter((m) => m.role !== "error"));
      }
    } catch {
      /* ignore */
    }
  }, [storageKey]);

  React.useEffect(() => {
    try {
      const data: Stored = { conversationId: conversationId.current, messages: messages.slice(-40) };
      window.sessionStorage.setItem(storageKey, JSON.stringify(data));
    } catch {
      /* ignore */
    }
  }, [messages, storageKey]);

  const request = React.useCallback(
    async (text: string, history: ChatMessage[]) => {
      pendingRef.current = true;
      setPending(true);
      try {
        const response = await api.chat(slug, {
          conversation_id: conversationId.current,
          message: text,
          history: history
            .filter((m): m is Exclude<ChatMessage, { role: "error" }> => m.role !== "error")
            .slice(-10)
            .map((m) => ({ role: m.role, content: m.content })),
          cart: cart.lines.map((l) => ({ item_id: l.itemId, quantity: l.quantity })),
        });
        conversationId.current = response.conversation_id;
        setMessages((prev) => [...prev, { id: nextId(), role: "assistant", content: response.message, response }]);
      } catch (e) {
        const err = e instanceof ApiError ? e : new ApiError("Something went wrong. Please try again.", 0, true);
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "error", content: err.message, retryText: text, retryable: err.retryable },
        ]);
      } finally {
        pendingRef.current = false;
        setPending(false);
      }
    },
    [slug, cart.lines],
  );

  const send = React.useCallback(
    (raw: string) => {
      const text = raw.trim().slice(0, 500);
      if (!text || pendingRef.current) return;
      const history = messages;
      setMessages((prev) => [...prev.filter((m) => m.role !== "error"), { id: nextId(), role: "user", content: text }]);
      void request(text, history);
    },
    [messages, request],
  );

  const retry = React.useCallback(
    (errorId: string) => {
      const err = messages.find((m) => m.id === errorId);
      if (!err || err.role !== "error" || pendingRef.current) return;
      const remaining = messages.filter((m) => m.id !== errorId);
      setMessages(remaining);
      void request(err.retryText, remaining.slice(0, -1));
    },
    [messages, request],
  );

  const reset = React.useCallback(() => {
    if (pendingRef.current) return;
    conversationId.current = null;
    setMessages([]);
  }, []);

  const value = React.useMemo(() => ({ messages, pending, send, retry, reset }), [messages, pending, send, retry, reset]);
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant() {
  const ctx = React.useContext(AssistantContext);
  if (!ctx) throw new Error("useAssistant must be used inside AssistantProvider");
  return ctx;
}
