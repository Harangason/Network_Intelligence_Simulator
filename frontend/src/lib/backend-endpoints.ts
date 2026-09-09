/** Share the configured backend across rewrites, jobs, agent chat and history. */
export function backendEndpoints(environment: Record<string, string | undefined>) {
  const simulator = (environment.SIMULATOR_BACKEND_API_URL ?? environment.SIMULATOR_API_URL
    ?? "http://127.0.0.1:15050/api").replace(/\/+$/, "");
  const engineering = (environment.SIMULATOR_ENGINEERING_API_URL ?? environment.ENGINEERING_API_URL
    ?? `${simulator}/engineering`).replace(/\/+$/, "");
  return { simulator, engineering };
}
