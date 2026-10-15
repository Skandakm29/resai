import type { Metadata } from "next";
import { OnboardingPage } from "@/components/admin/onboarding";

export const metadata: Metadata = {
  title: "Café onboarding",
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return <OnboardingPage />;
}
