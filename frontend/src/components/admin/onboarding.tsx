"use client";

import * as React from "react";
import { Copy, Loader2, Mail, RotateCcw, Trash2 } from "lucide-react";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { copy, field, label, LinkCard, ReviewStep, store, stored, UploadStep } from "@/components/onboard/steps";
import {
  AdminError,
  adminClient,
  onboarding,
  pitchEmail,
  type DraftMenu,
  type OnboardingStatus,
  type PublishedCafe,
} from "@/lib/onboarding";
import { cn } from "@/lib/utils";

const KEY_STORAGE = "onboarding-admin-key";
const SENDER_STORAGE = "onboarding-sender";

type Stage = { name: "upload" } | { name: "review"; draft: DraftMenu } | { name: "done"; cafe: PublishedCafe };

export function OnboardingPage() {
  const [key, setKey] = React.useState("");
  const [keyInput, setKeyInput] = React.useState("");
  const [status, setStatus] = React.useState<OnboardingStatus | null>(null);
  const [checking, setChecking] = React.useState(false);
  const [cafes, setCafes] = React.useState<PublishedCafe[]>([]);
  const [stage, setStage] = React.useState<Stage>({ name: "upload" });
  const client = React.useMemo(() => adminClient(key), [key]);

  const unlock = React.useCallback(async (candidate: string) => {
    setChecking(true);
    try {
      const s = await adminClient(candidate).status();
      setStatus(s);
      setKey(candidate);
      store(KEY_STORAGE, candidate);
      setCafes(await onboarding.list(candidate));
    } catch (e) {
      if (e instanceof AdminError && e.status === 401) store(KEY_STORAGE, "");
      toast.error(e instanceof Error ? e.message : "Couldn't sign in");
    } finally {
      setChecking(false);
    }
  }, []);

  React.useEffect(() => {
    const saved = stored(KEY_STORAGE);
    if (saved) void unlock(saved);
  }, [unlock]);

  const refresh = React.useCallback(async () => {
    try {
      setCafes(await onboarding.list(key));
    } catch {
      /* list is a convenience; keep the old one */
    }
  }, [key]);

  return (
    <div className="min-h-dvh bg-background">
      <Toaster position="top-center" richColors />
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <div>
            <h1 className="font-display text-2xl">Café onboarding</h1>
            <p className="text-sm text-muted-foreground">Upload a menu, check it, and get a live link to send.</p>
          </div>
          {key && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                store(KEY_STORAGE, "");
                setKey("");
                setStatus(null);
              }}
            >
              Sign out
            </Button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        {!key ? (
          <form
            className="mx-auto mt-10 max-w-sm space-y-3 rounded-2xl border bg-card p-6"
            onSubmit={(e) => {
              e.preventDefault();
              if (keyInput.trim()) void unlock(keyInput.trim());
            }}
          >
            <label className={label} htmlFor="admin-key">
              Admin key (ADMIN_API_KEY on the backend)
            </label>
            <input
              id="admin-key"
              type="password"
              autoComplete="current-password"
              className={field}
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
            />
            <Button type="submit" className="w-full" disabled={checking || !keyInput.trim()}>
              {checking && <Loader2 className="animate-spin" />}
              {checking ? "Checking (the server may be waking up)…" : "Continue"}
            </Button>
          </form>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
            <section className="min-w-0">
              {stage.name === "upload" && (
                <UploadStep client={client} mode="admin" status={status} onDraft={(draft) => setStage({ name: "review", draft })} />
              )}
              {stage.name === "review" && (
                <ReviewStep
                  client={client}
                  mode="admin"
                  draft={stage.draft}
                  onBack={() => setStage({ name: "upload" })}
                  onPublished={(cafe) => {
                    setStage({ name: "done", cafe });
                    void refresh();
                  }}
                />
              )}
              {stage.name === "done" && <DoneStep cafe={stage.cafe} onAnother={() => setStage({ name: "upload" })} />}
            </section>
            <CafeList
              cafes={cafes}
              onDelete={async (slug) => {
                if (!window.confirm(`Take /r/${slug} offline? Its link will stop working.`)) return;
                try {
                  await onboarding.remove(key, slug);
                  toast.success("Page taken down");
                  void refresh();
                } catch (e) {
                  toast.error(e instanceof Error ? e.message : "Couldn't delete");
                }
              }}
            />
          </div>
        )}
      </main>
    </div>
  );
}

function DoneStep({ cafe, onAnother }: { cafe: PublishedCafe; onAnother: () => void }) {
  const url = typeof window === "undefined" ? cafe.path : `${window.location.origin}${cafe.path}`;
  const [sender, setSender] = React.useState("");
  React.useEffect(() => setSender(stored(SENDER_STORAGE)), []);
  const email = pitchEmail({ name: cafe.name, itemCount: cafe.item_count, url }, sender);
  const mailto = `mailto:?subject=${encodeURIComponent(email.subject)}&body=${encodeURIComponent(email.body)}`;

  return (
    <div className="space-y-6">
      <LinkCard cafe={cafe} />

      <div className="rounded-2xl border bg-card p-5">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <Mail className="size-5" /> Cold email
        </h2>
        <label className={label} htmlFor="sender">
          Sign as
        </label>
        <input
          id="sender"
          className={cn(field, "mb-3 max-w-xs")}
          value={sender}
          placeholder="Your name"
          onChange={(e) => {
            setSender(e.target.value);
            store(SENDER_STORAGE, e.target.value);
          }}
        />
        <div className="rounded-lg border bg-background p-3 text-sm">
          <div className="mb-2 font-medium">Subject: {email.subject}</div>
          <pre className="whitespace-pre-wrap font-sans text-sm">{email.body}</pre>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => copy(`Subject: ${email.subject}\n\n${email.body}`, "Email")}>
            <Copy /> Copy email
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={mailto}>
              <Mail /> Open in mail app
            </a>
          </Button>
        </div>
      </div>

      <Button variant="ghost" onClick={onAnother}>
        <RotateCcw /> Onboard another café
      </Button>
    </div>
  );
}

function CafeList({ cafes, onDelete }: { cafes: PublishedCafe[]; onDelete: (slug: string) => void }) {
  return (
    <aside className="h-fit rounded-2xl border bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold">Published pages ({cafes.length})</h2>
      {cafes.length === 0 ? (
        <p className="text-xs text-muted-foreground">None yet.</p>
      ) : (
        <ul className="space-y-2">
          {cafes.map((c) => (
            <li key={c.slug} className="group rounded-lg border px-3 py-2">
              <div className="flex items-start gap-2">
                <a href={c.path} target="_blank" rel="noreferrer" className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium hover:underline">{c.name}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {c.path} · {c.item_count} items
                  </div>
                  {c.owner_email && (
                    <div className="truncate text-xs text-muted-foreground">
                      Self-serve: {c.owner_name} · {c.owner_email}
                    </div>
                  )}
                </a>
                <button
                  type="button"
                  aria-label={`Copy link for ${c.name}`}
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => copy(`${window.location.origin}${c.path}`, "Link")}
                >
                  <Copy className="size-4" />
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${c.name}`}
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => onDelete(c.slug)}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
