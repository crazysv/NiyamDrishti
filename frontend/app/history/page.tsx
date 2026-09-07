import HistoryScreen from "../components/history/HistoryScreen";

export const metadata = {
  title: "Inspection Archive | NiyamDrishti",
  description: "Search and inspect past Legal Metrology compliance verification records.",
};

export default function HistoryPage() {
  return (
    <main className="min-h-screen bg-[#EAE7DC] sm:py-6 flex items-center justify-center">
      <HistoryScreen />
    </main>
  );
}
