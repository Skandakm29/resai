"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Shown when a page can't load its data - usually because the free-tier API
 * is still waking up. Retries automatically a few times before giving up.
 */
export function WakeError({ reset }: { reset: () => void }) {
  const router = useRouter();
  const [attempt, setAttempt] = React.useState(0);
  const [pending, startTransition] = React.useTransition();
  const maxAuto = 6;

  const retry = React.useCallback(() => {
    startTransition(() => {
      router.refresh();
      reset();
    });
  }, [reset, router]);

  React.useEffect(() => {
    if (attempt >= maxAuto) return;
    const t = setTimeout(() => {
      setAttempt((a) => a + 1);
      retry();
    }, 8000);
    return () => clearTimeout(t);
  }, [attempt, retry]);

  const auto = attempt < maxAuto;
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-6 text-center" role="alert">
      {auto && <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden />}
      <h1 className="font-display text-2xl font-semibold">{auto ? "The café is waking up…" : "We couldn't load the café"}</h1>
      <p className="text-muted-foreground">
        {auto
          ? "The menu service was asleep and is starting up. This usually takes under a minute - we'll keep trying."
          : "The menu service is unavailable right now. Please try again in a moment."}
      </p>
      <Button onClick={retry} disabled={pending} variant={auto ? "outline" : "default"}>
        Try again now
      </Button>
    </div>
  );
}
