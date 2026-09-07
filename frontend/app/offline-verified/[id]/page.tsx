import OfflineVerifiedCheck from "@/app/components/offline/OfflineVerifiedCheck";

interface OfflineVerifiedPageProps {
  params: Promise<{ id: string }>;
}

export default async function OfflineVerifiedPage({ params }: OfflineVerifiedPageProps) {
  const { id } = await params;
  return <OfflineVerifiedCheck inspectionId={id} />;
}
