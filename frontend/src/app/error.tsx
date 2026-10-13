"use client";

import { WakeError } from "@/components/wake-error";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return <WakeError reset={reset} />;
}
