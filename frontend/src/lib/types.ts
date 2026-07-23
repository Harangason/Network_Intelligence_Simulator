export type Technology = {
  id: string;
  kind: string;
  family: string;
  medium: string;
  topology: string;
  default_bitrate?: number | null;
  max_payload_bytes?: number | null;
  native_formats?: string[];
};

export type TechnologyDomain = {
  id: string;
  label: string;
  technologies: Technology[];
};

export type Catalog = {
  technology_count: number;
  domains: TechnologyDomain[];
  formats: string[];
};

export type ArtifactDownload = {
  index: number;
  name: string;
  url: string;
};

export type SimulationResultPayload = {
  status: string;
  output_dir: string;
  warnings: string[];
  hardware_validation: {
    valid: boolean;
    findings: Array<{ code?: string; message?: string; severity?: string }>;
  };
  trace: {
    events: number;
    routes?: number;
    technologies?: string[];
    duration_s?: number;
  };
};

export type SimulationJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  validate_only: boolean;
  created_at: string;
  updated_at: string;
  error: string | null;
  result: SimulationResultPayload | null;
  artifact_downloads?: ArtifactDownload[];
};
