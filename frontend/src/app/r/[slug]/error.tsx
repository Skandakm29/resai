"use client";

import { Button } from "@/components/ui/button";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-24 text-center">
      <h1 className="font-display text-2xl font-semibold">We couldn&apos;t load the café</h1>
      <p className="text-muted-foreground">The menu service is unavailable right now. Please try again in a moment.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
