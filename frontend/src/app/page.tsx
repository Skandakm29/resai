import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function Home() {
  redirect(`/r/${process.env.DEFAULT_RESTAURANT_SLUG || "moai"}`);
}
