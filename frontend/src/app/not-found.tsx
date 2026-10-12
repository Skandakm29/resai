import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-24 text-center">
      <h1 className="font-display text-2xl font-semibold">Page not found</h1>
      <p className="text-muted-foreground">We couldn&apos;t find that restaurant or page.</p>
      <Link className="font-medium text-primary underline-offset-4 hover:underline" href="/">
        Go to the demo café
      </Link>
    </div>
  );
}
