import { registeredCatalogResponse } from "@/features/communication/lib/catalog-proxy";
import { proxyBackend } from "../_backend";

// DEV-OPT: v0 runs the frontend without the Python service. In Vercel Services,
// the /api prefix is owned by Flask and this Next.js fallback is bypassed.
export async function GET() {
  return registeredCatalogResponse(() => proxyBackend("/technologies"));
}
