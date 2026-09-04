import { projectQuerySuffixFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";
import { redirect } from "next/navigation";

export default async function TraceAnalysisPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const params = await searchParams;
  redirect(`/trace-analysis${projectQuerySuffixFromSearchParams(params)}`);
}
