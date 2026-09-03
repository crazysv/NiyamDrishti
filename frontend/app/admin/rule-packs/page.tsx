import { Metadata } from "next";
import RulePackManagement from "../../components/admin/RulePackManagement";

export const metadata: Metadata = {
  title: "Rule-Pack Governance & Management Portal — NiyamDrishti Admin",
  description:
    "Legal Metrology Department of Consumer Affairs central rule-pack governance, JSON schema validation, diff inspection, and statutory activation portal.",
};

export default function RulePacksAdminPage() {
  return <RulePackManagement />;
}
