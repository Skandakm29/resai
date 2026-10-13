"use client";

import "./globals.css";
import { WakeError } from "@/components/wake-error";

// Last-resort boundary for errors in the root layout itself.
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en-IN">
      <body>
        <WakeError reset={reset} />
      </body>
    </html>
  );
}
