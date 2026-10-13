"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

/**
 * Streams while the restaurant layout fetches its data. The [slug] segment's
 * own loading.tsx sits inside that layout, so without this the browser shows
 * a blank page for the up-to-a-minute it takes a sleeping backend to wake.
 */
export default function Loading() {
  const [slow, setSlow] = React.useState(false);
  React.useEffect(() => {
    const t = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-6 text-center"
      aria-busy="true"
      aria-live="polite"
    >
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden />
      {slow ? (
        <>
          <h1 className="font-display text-2xl font-semibold">The café is waking up…</h1>
          <p className="text-muted-foreground">
            The menu service was asleep and is starting up. This usually takes under a minute.
          </p>
        </>
      ) : (
        <p className="text-muted-foreground">Loading the café…</p>
      )}
    </div>
  );
}
