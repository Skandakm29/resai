import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RestaurantShell } from "@/components/shell";
import { getRestaurant } from "@/lib/server";

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const restaurant = await getRestaurant(params.slug).catch(() => null);
  return {
    title: restaurant ? `${restaurant.name} · ${restaurant.settings.assistant_name}` : "Restaurant not found",
  };
}

export default async function RestaurantLayout({ children, params }: { children: React.ReactNode; params: { slug: string } }) {
  const restaurant = await getRestaurant(params.slug);
  if (!restaurant) notFound();
  return <RestaurantShell restaurant={restaurant}>{children}</RestaurantShell>;
}
