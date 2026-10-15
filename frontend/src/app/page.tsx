import type { Metadata } from "next";
import { Landing } from "@/components/onboard/landing";
import { PRODUCT } from "@/lib/onboarding";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: `${PRODUCT} · Turn your menu into an AI waiter`,
  description: "Upload your restaurant's menu and get a link to an AI menu assistant your customers can use on any phone.",
};

export default function Home() {
  return <Landing demoSlug={process.env.DEFAULT_RESTAURANT_SLUG || "moai"} />;
}
