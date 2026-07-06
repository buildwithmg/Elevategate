import { ElevationRequestDetail } from "@/components/elevation-requests/detail-view";

export default async function ElevationRequestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ElevationRequestDetail id={Number(id)} />;
}
