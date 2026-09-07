import OfflineVerifiedCheck from "@/app/components/offline/OfflineVerifiedCheck";

export default async function OfflineVerifiedPage(props: PageProps<"/offline-verified/[id]">) {
  const { id } = await props.params;
  return <OfflineVerifiedCheck inspectionId={id} />;
}
