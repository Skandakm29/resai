import { notFound } from "next/navigation";
import { AssistantPage } from "@/components/assistant/assistant-page";
import { api } from "@/lib/api";
import { signatures } from "@/lib/menu";
import { getRestaurant } from "@/lib/server";

export default async function Page({ params }: { params: { slug: string } }) {
  const restaurant = await getRestaurant(params.slug);
  if (!restaurant) notFound();
  // Signature photos for the welcome screen; the chat works without them.
  const menu = await api.menu(params.slug).catch(() => null);
  const featured = menu ? signatures(menu.categories.flatMap((c) => c.items)) : [];
  return <AssistantPage restaurant={restaurant} featured={featured} />;
}
