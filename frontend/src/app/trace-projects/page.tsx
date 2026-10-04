import { MarketingShell } from "@/features/marketing/ui/marketing-shell";
import { ProjectGallery } from "@/features/projects/ui/project-gallery";

export default function TraceProjectsPage() {
  return <MarketingShell><ProjectGallery mode="trace" /></MarketingShell>;
}
