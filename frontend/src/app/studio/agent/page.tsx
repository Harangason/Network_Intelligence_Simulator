import { projectQuerySuffixFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";
import { redirect } from "next/navigation";

export default async function AgentPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const params = await searchParams;
  redirect(`/studio${projectQuerySuffixFromSearchParams(params)}`);
}
