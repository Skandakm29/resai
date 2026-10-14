"use client";

import * as React from "react";
import { ArrowUp, RefreshCw, RotateCcw, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlanCard } from "@/components/assistant/plan-card";
import { RecommendationCard } from "@/components/assistant/recommendation-card";
import { useAssistant, type ChatMessage } from "@/components/assistant/assistant-context";
import { SignatureStrip } from "@/components/menu/signature-strip";
import { assistantIcon, themeFor } from "@/lib/brand";
import type { ChatResponse, MenuItem, Restaurant } from "@/lib/types";
import { cn } from "@/lib/utils";

// The restaurant's assistant icon (coffee cup, cutlery...), set once by <Chat>.
const IconContext = React.createContext<LucideIcon>(assistantIcon("coffee"));

function AssistantAvatar({ className }: { className?: string }) {
  const Icon = React.useContext(IconContext);
  return (
    <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground", className)}>
      <Icon className="h-4 w-4" />
    </div>
  );
}

export function PromptChips({ prompts, onPick, disabled }: { prompts: string[]; onPick: (p: string) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          disabled={disabled}
          onClick={() => onPick(p)}
          className="rounded-full border border-primary/25 bg-card px-3.5 py-2 text-left text-sm text-primary transition-colors hover:border-primary hover:bg-primary/5 disabled:opacity-50"
        >
          {p}
        </button>
      ))}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="rise-in flex items-end gap-2" role="status" aria-label="Assistant is typing">
      <AssistantAvatar />
      <div className="flex gap-1 rounded-3xl rounded-bl-md border bg-card px-4 py-3.5 shadow-sm">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-dot-bounce rounded-full bg-coffee/60"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}

function ComparisonTable({ comparison }: { comparison: NonNullable<ChatResponse["comparison"]> }) {
  return (
    <div className="overflow-x-auto rounded-2xl border bg-card">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Comparison of {comparison.item_names.join(" and ")}</caption>
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 font-medium text-muted-foreground" scope="col">
              <span className="sr-only">Attribute</span>
            </th>
            {comparison.item_names.map((n) => (
              <th key={n} className="px-3 py-2 font-semibold" scope="col">
                {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {comparison.rows.map((row) => (
            <tr key={row.label} className="border-b last:border-0">
              <th className="whitespace-nowrap px-3 py-2 font-normal text-muted-foreground" scope="row">
                {row.label}
              </th>
              {row.values.map((v, i) => (
                <td key={i} className="px-3 py-2">
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssistantMessage({
  message,
  isLast,
  onPick,
  pending,
}: {
  message: Extract<ChatMessage, { role: "assistant" }>;
  isLast: boolean;
  onPick: (text: string) => void;
  pending: boolean;
}) {
  const r = message.response;
  const chips = r.clarification?.options?.length ? r.clarification.options : r.follow_ups;
  return (
    <div className="rise-in space-y-3" data-testid="assistant-message">
      <div className="flex items-end gap-2">
        <AssistantAvatar />
        <div className="max-w-[85%] space-y-2 rounded-3xl rounded-bl-md border bg-card px-4 py-3 shadow-sm">
          <p className="whitespace-pre-line text-[15px] leading-relaxed">{message.content}</p>
          {r.filter_summary.length > 0 && (
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              <SlidersHorizontal className="h-3 w-3" aria-hidden />
              <span className="sr-only">Active filters:</span>
              {r.filter_summary.map((f) => (
                <span key={f} className="rounded-full bg-muted px-2 py-0.5">
                  {f}
                </span>
              ))}
            </p>
          )}
        </div>
      </div>
      {r.comparison && (
        <div className="pl-10">
          <ComparisonTable comparison={r.comparison} />
        </div>
      )}
      {r.plan && (
        <div className="sm:pl-10">
          <PlanCard plan={r.plan} />
        </div>
      )}
      {r.recommendations.length > 0 && (
        <div
          className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 scrollbar-none sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:pl-10 sm:pr-0"
          aria-label="Recommendations"
        >
          {r.recommendations.map((rec) => (
            <RecommendationCard key={rec.item.id} rec={rec} />
          ))}
        </div>
      )}
      {isLast && chips.length > 0 && (
        <div className="pl-10">
          <PromptChips prompts={chips} onPick={onPick} disabled={pending} />
        </div>
      )}
    </div>
  );
}

function Welcome({
  restaurant,
  featured,
  onPick,
  disabled,
}: {
  restaurant: Restaurant;
  featured: MenuItem[];
  onPick: (p: string) => void;
  disabled: boolean;
}) {
  const WelcomeIcon = React.useContext(IconContext);
  const dark = Boolean(themeFor(restaurant.slug)?.darkHeader);
  return (
    <div className="mx-auto max-w-3xl space-y-6 py-2 sm:py-6">
      <div
        className={cn(
          "rise-in relative overflow-hidden rounded-[2rem] px-6 py-8 sm:px-10 sm:py-10",
          dark ? "bg-ink text-ink-foreground" : "border bg-card",
        )}
      >
        {/* Soft caramel glow, echoing the printed menu's colour panels. */}
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-primary/30 blur-3xl" />
        <div className="relative space-y-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <WelcomeIcon className="h-5 w-5" />
          </div>
          <h1 className="font-display text-4xl leading-[1.05] tracking-tight sm:text-5xl">{restaurant.settings.assistant_name}</h1>
          <p className={cn("max-w-xl text-balance text-[15px] leading-relaxed", dark ? "text-ink-foreground/75" : "text-muted-foreground")}>
            {restaurant.settings.welcome_message}
          </p>
        </div>
        {featured.length > 0 && (
          <div className="relative mt-7 space-y-3">
            <p className={cn("text-xs font-medium uppercase tracking-[0.18em]", dark ? "text-ink-foreground/60" : "text-muted-foreground")}>
              Signatures
            </p>
            <SignatureStrip
              items={featured}
              tone={dark ? "dark" : "light"}
              onPick={(item) => !disabled && onPick(`Tell me about the ${item.name}`)}
              className="-mx-6 px-6 sm:-mx-10 sm:px-10"
            />
          </div>
        )}
      </div>
      <div className="rise-in space-y-2" style={{ animationDelay: "120ms" }}>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Try asking</p>
        <PromptChips prompts={restaurant.settings.suggested_prompts} onPick={onPick} disabled={disabled} />
      </div>
    </div>
  );
}

export function Chat({ restaurant, featured = [] }: { restaurant: Restaurant; featured?: MenuItem[] }) {
  const { messages, pending, send, retry, reset } = useAssistant();
  const [draft, setDraft] = React.useState("");
  const endRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    // Leave the welcome screen at the top; follow the conversation once it starts.
    if (messages.length === 0) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  function submit(text: string) {
    if (!text.trim() || pending) return;
    send(text);
    setDraft("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit(draft);
    }
  }

  const lastAssistantIndex = messages.map((m) => m.role).lastIndexOf("assistant");

  return (
    <IconContext.Provider value={assistantIcon(restaurant.settings.assistant_icon)}>
    <section className="flex h-full min-h-0 flex-col" aria-label={restaurant.settings.assistant_name}>
      {messages.length > 0 && (
        <div className="flex items-center justify-between border-b px-4 py-2.5">
          <div className="flex items-center gap-2">
            <AssistantAvatar className="h-7 w-7" />
            <div>
              <h1 className="font-display text-base leading-tight">{restaurant.settings.assistant_name}</h1>
              <p className="text-xs text-muted-foreground">Answers come from the live menu</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={reset} disabled={pending}>
            <RotateCcw /> New chat
          </Button>
        </div>
      )}

      <div className="relative min-h-0 flex-1 overflow-y-auto px-4 py-4" aria-live="polite" aria-busy={pending}>
        {messages.length === 0 ? (
          <Welcome restaurant={restaurant} featured={featured} onPick={submit} disabled={pending} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-5">
            {messages.map((m, i) => {
              if (m.role === "user") {
                return (
                  <div key={m.id} className="rise-in flex justify-end">
                    <p className="max-w-[80%] whitespace-pre-line rounded-3xl rounded-br-md bg-primary px-4 py-2.5 text-[15px] text-primary-foreground">
                      {m.content}
                    </p>
                  </div>
                );
              }
              if (m.role === "error") {
                return (
                  <div key={m.id} role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <span className="flex-1">{m.content}</span>
                    {m.retryable && (
                      <Button size="sm" variant="outline" onClick={() => retry(m.id)} disabled={pending}>
                        <RefreshCw /> Retry
                      </Button>
                    )}
                  </div>
                );
              }
              return (
                <AssistantMessage key={m.id} message={m} isLast={i === lastAssistantIndex} onPick={submit} pending={pending} />
              );
            })}
            {pending && <TypingIndicator />}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="border-t bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur"
        onSubmit={(e) => {
          e.preventDefault();
          submit(draft);
        }}
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-3xl border bg-card p-1.5 pl-4 shadow-sm focus-within:ring-2 focus-within:ring-ring">
          <label htmlFor="chat-input" className="sr-only">
            Message {restaurant.settings.assistant_name}
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            rows={1}
            value={draft}
            maxLength={500}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask for a recommendation…"
            className="max-h-32 min-h-[2.5rem] flex-1 resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-muted-foreground"
          />
          <Button type="submit" size="icon" aria-label="Send message" disabled={pending || !draft.trim()}>
            <ArrowUp />
          </Button>
        </div>
        <p className="mx-auto mt-1.5 max-w-3xl text-center text-[11px] text-muted-foreground">
          Prices and availability come from the live menu. Please confirm allergens with staff.
        </p>
      </form>
    </section>
    </IconContext.Provider>
  );
}
