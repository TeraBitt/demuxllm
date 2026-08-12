import type { Metadata } from "next";
import { DashboardShell } from "@/components/dashboard/shell";

export const metadata: Metadata = {
  title: "Assistant",
  description:
    "Every request scored across the model pool, then answered by the cheapest model that clears the bar.",
};

export default function ChatPage() {
  return <DashboardShell />;
}
