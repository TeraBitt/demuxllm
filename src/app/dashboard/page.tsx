import type { Metadata } from "next";
import { DashboardShell } from "@/components/dashboard/shell";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "A working demo of the routing layer: every question classified, routed to the cheapest model that can answer it, and priced against a frontier-only baseline.",
};

export default function DashboardPage() {
  return <DashboardShell />;
}
