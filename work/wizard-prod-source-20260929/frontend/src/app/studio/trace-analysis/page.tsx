import { type ProjectQueryRecord } from "@/lib/user-settings";
import { redirect } from "next/navigation";

export default async function TraceAnalysisPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of ['project', 'view', 'job', 'focus_s']) {
    const value = params[key];
    if (typeof value === 'string') query.set(key, value);
  }
  redirect(`/trace-analysis?${query}`);
}
