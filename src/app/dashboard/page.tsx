import type { Metadata } from "next";
import { Overview } from "@/components/dashboard/overview";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Requests routed, what they cost, and what the same traffic would have cost on one frontier model.",
};

export default function DashboardPage() {
  return <Overview />;
}
