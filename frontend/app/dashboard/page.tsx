import { Metadata } from "next";
import AnalyticsDashboard from "../components/dashboard/AnalyticsDashboard";

export const metadata: Metadata = {
  title: "Enforcement Analytics Dashboard — NiyamDrishti",
  description:
    "Legal Metrology Department of Consumer Affairs supervisory intelligence & compliance velocity portal",
};

export default function DashboardPage() {
  return <AnalyticsDashboard />;
}
