"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  ClipboardCheck,
  Coins,
  FileUp,
  Leaf,
  MessageCircle,
  QrCode,
  RotateCcw,
  ShoppingBag,
  Sparkles,
  Users,
} from "lucide-react";
import { Toaster } from "sonner";
import { Button } from "@/components/ui/button";
import { LinkCard, ReviewStep, UploadStep } from "@/components/onboard/steps";
import { PRODUCT, publicClient, type DraftMenu, type OnboardingStatus, type PublishedCafe } from "@/lib/onboarding";

type Stage = { name: "upload" } | { name: "review"; draft: DraftMenu } | { name: "done"; cafe: PublishedCafe };

const STEPS = [
  { icon: FileUp, title: "Upload your menu", body: "A PDF, or photos of each page. Nothing to type in." },
  { icon: ClipboardCheck, title: "Check it", body: "We read every item and price. Fix anything we got wrong." },
  { icon: QrCode, title: "Share your link", body: "Put the QR code on your tables, or the link in your Instagram bio." },
];

const FEATURES = [
  { icon: Coins, title: "Recommends within a budget", body: "\"A cold coffee under ₹200\" gets real items from your menu, cheapest first if asked." },
  { icon: Users, title: "Plans for groups", body: "\"4 of us, starters and mains, ₹2000\" gets a full order that fits the budget." },
  { icon: Leaf, title: "Filters veg and dietary needs", body: "It only calls something veg when your menu says so, and is honest when it doesn't know." },
  { icon: ShoppingBag, title: "Builds the order", body: "Customers add items to a cart with checked prices, then order at the counter." },
];

const FAQ = [
  {
    q: "Do my customers need to install anything?",
    a: "No. It's a web link that opens on any phone, from a QR code, Instagram or Google Maps.",
  },
  {
    q: "Can the AI make up dishes or prices?",
    a: "No. Every answer comes from the menu you checked. Prices are shown exactly as you set them, and the cart re-checks them.",
  },
  {
    q: "What about allergens?",
    a: "Uploaded menus start with allergens marked as unconfirmed, so the assistant tells customers to check with your staff.",
  },
  {
    q: "How do I change my menu later?",
    a: "Get in touch and we'll update your page, or upload the new menu here for a fresh link.",
  },
];

export function Landing({ demoSlug }: { demoSlug: string }) {
  const [stage, setStage] = React.useState<Stage>({ name: "upload" });
  const [status, setStatus] = React.useState<OnboardingStatus | null>(null);
  const flowRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    publicClient.status().then(setStatus, () => setStatus(null));
  }, []);

  const go = (next: Stage) => {
    setStage(next);
    requestAnimationFrame(() => flowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  return (
    <div className="min-h-dvh bg-background">
      <Toaster position="top-center" richColors />

      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <Sparkles className="size-4" />
            </span>
            <span className="font-display text-xl">{PRODUCT}</span>
          </Link>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link href={`/r/${demoSlug}`}>Live example</Link>
            </Button>
            <Button asChild size="sm">
              <a href="#start">Get your link</a>
            </Button>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-12 md:py-20 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              For cafés and restaurants
            </p>
            <h1 className="font-display text-4xl leading-[1.05] sm:text-5xl md:text-6xl">
              Turn your menu into an AI waiter.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-muted-foreground">
              Upload your menu and get a link in about two minutes. Customers ask what they feel like, and get
              answers straight from your menu, with your prices.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <a href="#start">
                  Upload your menu <ArrowRight />
                </a>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href={`/r/${demoSlug}`}>Try a live example</Link>
              </Button>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">No app for your customers. No setup for you.</p>
          </div>
          <ChatPreview />
        </section>

        {/* How it works */}
        <section className="border-y bg-card">
          <div className="mx-auto max-w-6xl px-4 py-12">
            <h2 className="mb-8 text-center font-display text-3xl">How it works</h2>
            <ol className="grid gap-4 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <li key={s.title} className="rounded-2xl border bg-background p-5">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <s.icon className="size-5" />
                    </span>
                    <span className="text-xs font-semibold text-muted-foreground">STEP {i + 1}</span>
                  </div>
                  <h3 className="font-semibold">{s.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* The flow */}
        <section id="start" className="scroll-mt-16">
          <div ref={flowRef} className="mx-auto max-w-4xl scroll-mt-20 px-4 py-12">
            <div className="mb-6 text-center">
              <h2 className="font-display text-3xl">Get your link</h2>
              <p className="mt-2 text-muted-foreground">Upload, check, done. Your page goes live straight away.</p>
            </div>
            {stage.name === "upload" && (
              <UploadStep client={publicClient} mode="public" status={status} onDraft={(draft) => go({ name: "review", draft })} />
            )}
            {stage.name === "review" && (
              <ReviewStep
                client={publicClient}
                mode="public"
                draft={stage.draft}
                onBack={() => go({ name: "upload" })}
                onPublished={(cafe) => go({ name: "done", cafe })}
              />
            )}
            {stage.name === "done" && (
              <div className="space-y-6">
                <LinkCard cafe={stage.cafe} />
                <NextSteps cafe={stage.cafe} />
                <Button variant="ghost" onClick={() => go({ name: "upload" })}>
                  <RotateCcw /> Upload another menu
                </Button>
              </div>
            )}
          </div>
        </section>

        {/* Features */}
        <section className="border-y bg-card">
          <div className="mx-auto max-w-6xl px-4 py-12">
            <h2 className="mb-8 text-center font-display text-3xl">What your customers get</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <div key={f.title} className="flex gap-4 rounded-2xl border bg-background p-5">
                  <f.icon className="mt-0.5 size-5 shrink-0 text-primary" />
                  <div>
                    <h3 className="font-semibold">{f.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{f.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="mx-auto max-w-3xl px-4 py-12">
          <h2 className="mb-6 text-center font-display text-3xl">Questions</h2>
          <div className="divide-y rounded-2xl border bg-card">
            {FAQ.map((f) => (
              <details key={f.q} className="group px-5 py-4">
                <summary className="cursor-pointer list-none font-medium marker:hidden">
                  <span className="flex items-center justify-between gap-4">
                    {f.q}
                    <span className="text-muted-foreground transition-transform group-open:rotate-45">+</span>
                  </span>
                </summary>
                <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-xs text-muted-foreground">
          <span>{PRODUCT} · AI menu assistants for restaurants</span>
          <Link href={`/r/${demoSlug}`} className="hover:underline">
            See a live example
          </Link>
        </div>
      </footer>
    </div>
  );
}

/** An illustration of the customer experience (not live data). */
function ChatPreview() {
  return (
    <div aria-hidden className="relative">
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-primary/15 via-accent to-transparent blur-2xl" />
      <div className="mx-auto max-w-sm rounded-[2rem] border bg-card p-4 shadow-xl">
        <div className="mb-4 flex items-center gap-2 border-b pb-3">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            BR
          </span>
          <div>
            <div className="text-sm font-semibold">The Brew Room</div>
            <div className="text-xs text-muted-foreground">Menu assistant</div>
          </div>
        </div>
        <div className="space-y-3 text-sm">
          <div className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-primary-foreground">
            Something cold under ₹250?
          </div>
          <div className="w-fit max-w-[90%] rounded-2xl rounded-bl-md bg-muted px-3 py-2">
            Here are three cold coffees under ₹250. I&apos;d start with the Iced Americano.
          </div>
          {[
            ["Iced Americano", "₹170", "Served iced"],
            ["Vietnamese Iced Coffee", "₹230", "Sweet, strong"],
            ["Cold Brew Tonic", "₹240", "Bright, fizzy"],
          ].map(([name, price, note]) => (
            <div key={name} className="flex items-center justify-between rounded-xl border bg-background px-3 py-2">
              <div>
                <div className="font-medium">{name}</div>
                <div className="text-xs text-muted-foreground">{note}</div>
              </div>
              <div className="font-semibold">{price}</div>
            </div>
          ))}
          <div className="flex items-center gap-2 rounded-full border bg-background px-3 py-2 text-muted-foreground">
            <MessageCircle className="size-4" /> Ask for a recommendation…
          </div>
        </div>
      </div>
    </div>
  );
}

function NextSteps({ cafe }: { cafe: PublishedCafe }) {
  const [url, setUrl] = React.useState(cafe.path);
  React.useEffect(() => setUrl(`${window.location.origin}${cafe.path}`), [cafe.path]);
  const share = `Ask our menu assistant what to order at ${cafe.name}: ${url}`;
  return (
    <div className="rounded-2xl border bg-card p-5">
      <h3 className="mb-3 font-semibold">Put it in front of customers</h3>
      <ul className="space-y-2 text-sm text-muted-foreground">
        <li>Print the QR code on table cards, the counter, or the back of your printed menu.</li>
        <li>Add the link to your Instagram bio and your Google Business profile.</li>
        <li>Save this link and the QR code now. You&apos;ll need them to share your page.</li>
      </ul>
      <Button asChild variant="outline" size="sm" className="mt-4">
        <a href={`https://wa.me/?text=${encodeURIComponent(share)}`} target="_blank" rel="noreferrer">
          <MessageCircle /> Share on WhatsApp
        </a>
      </Button>
    </div>
  );
}
