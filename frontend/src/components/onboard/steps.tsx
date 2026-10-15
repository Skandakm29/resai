"use client";

import * as React from "react";
import { AlertTriangle, Check, Copy, Download, ExternalLink, FileText, Loader2, Plus, Trash2, Upload, X } from "lucide-react";
import QRCode from "qrcode";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AdminError,
  EMAIL_RE,
  PRICE_RE,
  slugify,
  type CafeProfile,
  type DraftItem,
  type DraftMenu,
  type ExtractProgress,
  type OnboardClient,
  type OnboardingStatus,
  type Owner,
  type PublishedCafe,
} from "@/lib/onboarding";
import { cn } from "@/lib/utils";

export function stored(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function store(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* storage blocked: the value just isn't remembered */
  }
}

export async function copy(text: string, what: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${what} copied`);
  } catch {
    toast.error("Couldn't copy - select and copy it manually");
  }
}

export const field =
  "h-9 w-full rounded-lg border border-input bg-card px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";
export const label = "mb-1 block text-xs font-medium text-muted-foreground";

const EMPTY_PROFILE: CafeProfile = {
  name: "",
  slug: "",
  tagline: "",
  address_line: "",
  city: "",
  phone: "",
  brand_color: "#1f5135",
  assistant_icon: "coffee",
};

const METHOD_LABEL: Record<DraftMenu["method"], string> = {
  "text-llm": "Read with OCR and structured by the AI",
  "text-rules": "Text layer parsed by rules (check carefully)",
};

export function StepTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <h2 className="mb-4 flex items-center gap-3 text-lg font-semibold">
      <span className="flex size-7 items-center justify-center rounded-full bg-primary text-sm text-primary-foreground">
        {n}
      </span>
      {children}
    </h2>
  );
}

export type Mode = "admin" | "public";

export function UploadStep({
  client,
  mode,
  status,
  onDraft,
}: {
  client: OnboardClient;
  mode: Mode;
  status: OnboardingStatus | null;
  onDraft: (d: DraftMenu) => void;
}) {
  const [files, setFiles] = React.useState<File[]>([]);
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [elapsed, setElapsed] = React.useState(0);
  const [progress, setProgress] = React.useState<ExtractProgress | null>(null);
  React.useEffect(() => {
    if (!busy) return;
    setElapsed(0);
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  const [dragging, setDragging] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const add = (list: FileList | null) => {
    if (list) setFiles((prev) => [...prev, ...Array.from(list)].slice(0, 10));
  };

  const run = async () => {
    setBusy(true);
    try {
      setProgress(null);
      const draft = await client.extract(files, text, setProgress);
      if (!draft.items.length) {
        toast.error(draft.warnings[0] || "No menu items were found.");
        return;
      }
      onDraft(draft);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Couldn't read the menu");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border bg-card p-5">
      <StepTitle n={1}>{mode === "public" ? "Upload your menu" : "Upload the menu"}</StepTitle>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "hover:bg-muted",
        )}
      >
        <Upload className="size-6 text-muted-foreground" />
        <span className="font-medium">Drop a menu PDF or photos here, or click to choose</span>
        <span className="text-xs text-muted-foreground">
          {status === null || status.reads_photos_and_scans
            ? `PDF or photos of each page (JPG, PNG, WebP). Up to 10 files, ${status?.max_upload_mb ?? 20} MB in total.`
            : mode === "public"
              ? "A PDF menu works best. For photos, paste the menu text below instead."
              : "PDFs with selectable text only. Photos and scans need the OCR packages on the backend."}
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="application/pdf,image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      {files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-sm">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{f.name}</span>
              <span className="text-xs text-muted-foreground">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
              <button
                type="button"
                aria-label={`Remove ${f.name}`}
                onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
              >
                <X className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className={cn(label, "mt-4")} htmlFor="menu-text">
        Or paste the menu text (one item per line, e.g. &quot;Cappuccino 210&quot;)
      </label>
      <textarea
        id="menu-text"
        rows={5}
        className={cn(field, "h-auto py-2 font-mono text-xs")}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"HOT COFFEE\nCappuccino ...... 210\nLatte ₹230 - velvety microfoam"}
      />
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={run} disabled={busy || (!files.length && !text.trim())}>
          {busy && <Loader2 className="animate-spin" />}
          {busy
            ? `${
                progress?.phase === "ocr"
                  ? `Reading page ${Math.min(progress.done + 1, progress.total)} of ${progress.total}…`
                  : progress?.phase === "structuring"
                    ? "Organising the items…"
                    : "Getting ready…"
              } ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
            : "Read menu"}
        </Button>
        {busy && (
          <span className="text-xs text-muted-foreground">
            {progress?.phase === "structuring"
              ? "Sorting items into sections and checking prices. Usually under two minutes."
              : "Pages are read on this device, a few seconds each. Keep this tab open."}
          </span>
        )}
      </div>
    </div>
  );
}

export function ReviewStep({
  client,
  mode,
  draft,
  onBack,
  onPublished,
}: {
  client: OnboardClient;
  mode: Mode;
  draft: DraftMenu;
  onBack: () => void;
  onPublished: (c: PublishedCafe) => void;
}) {
  const [items, setItems] = React.useState<DraftItem[]>(draft.items);
  const [profile, setProfile] = React.useState<CafeProfile>(() => ({
    ...EMPTY_PROFILE,
    name: draft.profile.name ?? "",
    slug: slugify(draft.profile.name ?? ""),
    tagline: draft.profile.tagline ?? "",
    address_line: draft.profile.address_line ?? "",
    city: draft.profile.city ?? "",
    phone: draft.profile.phone ?? "",
  }));
  const [slugEdited, setSlugEdited] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [conflict, setConflict] = React.useState<string | null>(null);
  const [owner, setOwner] = React.useState<Owner>({ name: "", email: "" });
  const isPublic = mode === "public";

  const set = <K extends keyof CafeProfile>(k: K, v: CafeProfile[K]) => setProfile((p) => ({ ...p, [k]: v }));
  const update = (i: number, patch: Partial<DraftItem>) =>
    setItems((prev) => prev.map((it, j) => (j === i ? { ...it, ...patch } : it)));

  const badPrices = items.filter((i) => !PRICE_RE.test(i.price.trim())).length;
  const blank = items.filter((i) => !i.name.trim() || !i.category.trim()).length;
  const slugOk = !profile.slug || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(profile.slug);
  const ownerOk = !isPublic || (owner.name.trim() && EMAIL_RE.test(owner.email.trim()));
  const canPublish = profile.name.trim() && items.length > 0 && !badPrices && !blank && slugOk && ownerOk && !busy;

  const publish = async (replace: boolean) => {
    setBusy(true);
    setConflict(null);
    try {
      const clean = items.map((i) => ({
        ...i,
        name: i.name.trim(),
        category: i.category.trim(),
        price: i.price.trim(),
        description: i.description?.trim() || null,
      }));
      const trimmedOwner = { name: owner.name.trim(), email: owner.email.trim() };
      onPublished(
        await client.publish({ ...profile, name: profile.name.trim() }, clean, {
          replace,
          owner: isPublic ? trimmedOwner : undefined,
        }),
      );
    } catch (e) {
      if (e instanceof AdminError && e.status === 409) setConflict(e.message);
      else toast.error(e instanceof Error ? e.message : "Couldn't publish");
    } finally {
      setBusy(false);
    }
  };

  // Rows keep their index into `items` so edits land on the right row.
  const groups = React.useMemo(() => {
    const out = new Map<string, number[]>();
    items.forEach((it, i) => {
      const k = it.category.trim() || "(no section)";
      out.set(k, [...(out.get(k) ?? []), i]);
    });
    return Array.from(out.entries());
  }, [items]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border bg-card p-5">
        <StepTitle n={2}>{isPublic ? "Your restaurant" : "Check the café details"}</StepTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={label} htmlFor="cafe-name">
              {isPublic ? "Restaurant name *" : "Café name *"}
            </label>
            <input
              id="cafe-name"
              className={field}
              value={profile.name}
              onChange={(e) => {
                set("name", e.target.value);
                if (!slugEdited) set("slug", slugify(e.target.value));
              }}
            />
          </div>
          <div>
            <label className={label} htmlFor="cafe-slug">
              Link: /r/{profile.slug || "…"}
            </label>
            <input
              id="cafe-slug"
              className={cn(field, !slugOk && "border-destructive")}
              value={profile.slug}
              onChange={(e) => {
                setSlugEdited(true);
                set("slug", e.target.value.toLowerCase());
              }}
            />
          </div>
          <div className="sm:col-span-2">
            <label className={label} htmlFor="cafe-tagline">
              Tagline
            </label>
            <input id="cafe-tagline" className={field} value={profile.tagline} onChange={(e) => set("tagline", e.target.value)} />
          </div>
          <div>
            <label className={label} htmlFor="cafe-address">
              Area / address
            </label>
            <input
              id="cafe-address"
              className={field}
              value={profile.address_line}
              onChange={(e) => set("address_line", e.target.value)}
            />
          </div>
          <div>
            <label className={label} htmlFor="cafe-city">
              City
            </label>
            <input id="cafe-city" className={field} value={profile.city} onChange={(e) => set("city", e.target.value)} />
          </div>
          <div>
            <label className={label} htmlFor="cafe-phone">
              Phone
            </label>
            <input id="cafe-phone" className={field} value={profile.phone} onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div className="flex gap-3">
            <div>
              <label className={label} htmlFor="cafe-color">
                Brand colour
              </label>
              <input
                id="cafe-color"
                type="color"
                className="h-9 w-14 cursor-pointer rounded-lg border border-input bg-card p-1"
                value={profile.brand_color}
                onChange={(e) => set("brand_color", e.target.value)}
              />
            </div>
            <div className="flex-1">
              <label className={label} htmlFor="cafe-icon">
                Assistant icon
              </label>
              <select
                id="cafe-icon"
                className={field}
                value={profile.assistant_icon}
                onChange={(e) => set("assistant_icon", e.target.value as CafeProfile["assistant_icon"])}
              >
                <option value="coffee">Coffee</option>
                <option value="tea">Tea</option>
                <option value="utensils">Cutlery</option>
                <option value="pizza">Pizza</option>
                <option value="drink">Drink</option>
                <option value="dessert">Dessert</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border bg-card p-5">
        <StepTitle n={3}>
          {isPublic ? "Check your menu" : "Check the menu"} ({items.length} items)
        </StepTitle>
        <p className="-mt-2 mb-3 text-xs text-muted-foreground">
          {isPublic
            ? "We read this from your menu. Fix any name or price, and delete anything that isn't sold any more."
            : `${METHOD_LABEL[draft.method]}. Spot-check prices against the original.`}
        </p>
        {draft.warnings.length > 0 && (
          <ul className="mb-4 space-y-1 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {draft.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                {w}
              </li>
            ))}
          </ul>
        )}
        {draft.unparsed_lines.length > 0 && (
          <details className="mb-4 text-xs">
            <summary className="cursor-pointer text-muted-foreground">
              {draft.unparsed_lines.length} lines weren&apos;t understood
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-muted p-2">{draft.unparsed_lines.join("\n")}</pre>
          </details>
        )}

        <div className="space-y-5">
          {groups.map(([category, rows]) => (
            <div key={category}>
              <h3 className="mb-2 text-sm font-semibold">
                {category} <span className="font-normal text-muted-foreground">· {rows.length}</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground">
                      <th className="pb-1 font-medium">Name</th>
                      <th className="w-24 pb-1 font-medium">Price ₹</th>
                      <th className="w-36 pb-1 font-medium">Section</th>
                      <th className="w-28 pb-1 font-medium">Type</th>
                      <th className="w-24 pb-1 font-medium">Veg</th>
                      <th className="w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((i) => {
                      const it = items[i];
                      return (
                        <tr key={i} className="align-top">
                          <td className="py-1 pr-2">
                            <input
                              aria-label="Item name"
                              className={cn(field, "h-8", !it.name.trim() && "border-destructive")}
                              value={it.name}
                              onChange={(e) => update(i, { name: e.target.value })}
                            />
                            {it.variants.length > 0 && (
                              <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                                {it.variants.map((v) => `${v.name} ₹${v.price}`).join(" · ")}
                                <button
                                  type="button"
                                  className="underline"
                                  onClick={() => update(i, { variants: [] })}
                                >
                                  remove sizes
                                </button>
                              </div>
                            )}
                            {it.description && (
                              <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{it.description}</div>
                            )}
                          </td>
                          <td className="py-1 pr-2">
                            <input
                              aria-label="Price"
                              inputMode="decimal"
                              className={cn(field, "h-8", !PRICE_RE.test(it.price.trim()) && "border-destructive")}
                              value={it.price}
                              // With sizes, the first size's price is the item's price.
                              onChange={(e) =>
                                update(i, {
                                  price: e.target.value,
                                  variants: it.variants.map((v, j) => (j === 0 ? { ...v, price: e.target.value } : v)),
                                })
                              }
                            />
                          </td>
                          <td className="py-1 pr-2">
                            <input
                              aria-label="Section"
                              className={cn(field, "h-8")}
                              value={it.category}
                              onChange={(e) => update(i, { category: e.target.value })}
                            />
                          </td>
                          <td className="py-1 pr-2">
                            <select
                              aria-label="Type"
                              className={cn(field, "h-8 px-2")}
                              value={it.item_type}
                              onChange={(e) => update(i, { item_type: e.target.value as DraftItem["item_type"] })}
                            >
                              <option value="beverage">Drink</option>
                              <option value="food">Food</option>
                              <option value="dessert">Dessert</option>
                            </select>
                          </td>
                          <td className="py-1 pr-2">
                            <select
                              aria-label="Vegetarian"
                              className={cn(field, "h-8 px-2")}
                              value={it.is_vegetarian === null ? "" : String(it.is_vegetarian)}
                              onChange={(e) =>
                                update(i, { is_vegetarian: e.target.value === "" ? null : e.target.value === "true" })
                              }
                            >
                              <option value="">Unknown</option>
                              <option value="true">Veg</option>
                              <option value="false">Non-veg</option>
                            </select>
                          </td>
                          <td className="py-1">
                            <button
                              type="button"
                              aria-label={`Delete ${it.name}`}
                              className="mt-1.5 text-muted-foreground hover:text-destructive"
                              onClick={() => setItems((prev) => prev.filter((_, j) => j !== i))}
                            >
                              <Trash2 className="size-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() =>
            setItems((prev) => [
              ...prev,
              {
                category: prev.at(-1)?.category ?? "Menu",
                name: "",
                price: "",
                description: null,
                item_type: "food",
                temperature: null,
                contains_coffee: null,
                is_vegetarian: null,
                tags: [],
                variants: [],
              },
            ])
          }
        >
          <Plus /> Add item
        </Button>
      </div>

      {isPublic && (
        <div className="rounded-2xl border bg-card p-5">
          <StepTitle n={4}>Where should we send your link?</StepTitle>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={label} htmlFor="owner-name">
                Your name *
              </label>
              <input
                id="owner-name"
                autoComplete="name"
                className={field}
                value={owner.name}
                onChange={(e) => setOwner((o) => ({ ...o, name: e.target.value }))}
              />
            </div>
            <div>
              <label className={label} htmlFor="owner-email">
                Email *
              </label>
              <input
                id="owner-email"
                type="email"
                autoComplete="email"
                className={field}
                value={owner.email}
                onChange={(e) => setOwner((o) => ({ ...o, email: e.target.value }))}
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Only used to contact you about your page. It isn&apos;t shown to customers.
          </p>
        </div>
      )}

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t bg-background/95 px-4 py-3 backdrop-blur">
        <Button variant="ghost" onClick={onBack} disabled={busy}>
          Back
        </Button>
        <div className="flex-1 text-xs text-muted-foreground">
          {!profile.name.trim()
            ? "Add the restaurant name."
            : badPrices
              ? `${badPrices} price${badPrices > 1 ? "s" : ""} need fixing (numbers only).`
              : blank
                ? `${blank} item${blank > 1 ? "s" : ""} need a name and section.`
                : !slugOk
                  ? "The link can only use a-z, 0-9 and single hyphens."
                  : !ownerOk
                    ? "Add your name and email."
                    : conflict ?? "Ready to publish."}
        </div>
        {!isPublic && conflict && conflict.includes("replace") && (
          <Button variant="outline" onClick={() => publish(true)} disabled={!canPublish}>
            Replace existing
          </Button>
        )}
        <Button onClick={() => publish(false)} disabled={!canPublish}>
          {busy && <Loader2 className="animate-spin" />}
          {isPublic ? "Get my link" : "Publish page"}
        </Button>
      </div>
    </div>
  );
}


/** The live link with copy/open buttons and a downloadable QR code for tables. */
export function LinkCard({ cafe, children }: { cafe: PublishedCafe; children?: React.ReactNode }) {
  const [url, setUrl] = React.useState(cafe.path);
  const [qr, setQr] = React.useState<string | null>(null);

  React.useEffect(() => {
    const full = `${window.location.origin}${cafe.path}`;
    setUrl(full);
    QRCode.toDataURL(full, { width: 720, margin: 2, errorCorrectionLevel: "M" })
      .then(setQr)
      .catch(() => setQr(null));
  }, [cafe.path]);

  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="mb-3 flex items-center gap-2 text-primary">
        <Check className="size-5" />
        <h2 className="text-lg font-semibold">{cafe.name} is live</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        {cafe.item_count} items in {cafe.category_count} sections. Open it and ask it something, the way a customer would.
      </p>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <div className="min-w-0 flex-1 space-y-3">
          <code className="block truncate rounded-lg bg-muted px-3 py-2 text-sm">{url}</code>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => copy(url, "Link")}>
              <Copy /> Copy link
            </Button>
            <Button asChild size="sm">
              <a href={cafe.path} target="_blank" rel="noreferrer">
                <ExternalLink /> Open
              </a>
            </Button>
          </div>
          {children}
        </div>
        {qr && (
          <div className="flex flex-col items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element -- a generated data URL */}
            <img src={qr} alt={`QR code for ${url}`} className="size-36 rounded-lg border bg-white" />
            <Button asChild variant="ghost" size="sm">
              <a href={qr} download={`${cafe.slug}-qr.png`}>
                <Download /> Download QR
              </a>
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
