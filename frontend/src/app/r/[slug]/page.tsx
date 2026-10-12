import { notFound } from "next/navigation";
import { AssistantPage } from "@/components/assistant/assistant-page";
import { getRestaurant } from "@/lib/server";

export default async function Page({ params }: { params: { slug: string } }) {
  const restaurant = await getRestaurant(params.slug);
  if (!restaurant) notFound();
  return <AssistantPage restaurant={restaurant} />;
}
