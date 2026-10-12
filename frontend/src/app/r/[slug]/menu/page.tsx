import { notFound } from "next/navigation";
import { MenuBrowser } from "@/components/menu/menu-browser";
import { api, ApiError } from "@/lib/api";

export default async function MenuPage({ params }: { params: { slug: string } }) {
  try {
    const menu = await api.menu(params.slug);
    return <MenuBrowser menu={menu} slug={params.slug} />;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}
