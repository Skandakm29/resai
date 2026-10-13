import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RestaurantShell } from "@/components/shell";
import { getRestaurant } from "@/lib/server";

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  // Metadata blocks the first byte of HTML, so don't wait out a backend cold
  // start here - that would hide the loading screen. The layout keeps waiting.
  const timedOut = Symbol("timedOut");
  const restaurant = await Promise.race([
    getRestaurant(params.slug).catch(() => null),
    new Promise<typeof timedOut>((resolve) => setTimeout(() => resolve(timedOut), 2000)),
  ]);
  if (restaurant === timedOut) return { title: "Café Guide" };
  return {
    title: restaurant ? `${restaurant.name} · ${restaurant.settings.assistant_name}` : "Restaurant not found",
  };
}

export default async function RestaurantLayout({ children, params }: { children: React.ReactNode; params: { slug: string } }) {
  const restaurant = await getRestaurant(params.slug);
  if (!restaurant) notFound();
  return <RestaurantShell restaurant={restaurant}>{children}</RestaurantShell>;
}
