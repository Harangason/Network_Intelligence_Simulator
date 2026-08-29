"""Framework-neutral inventory used by adapters and API documentation tests."""

WORKLOAD_API_ROUTES = (
    ("POST", "/workloads"),
    ("GET", "/workloads"),
    ("GET", "/workloads/{id}"),
    ("POST", "/workloads/{id}/start"),
    ("POST", "/workloads/{id}/pause"),
    ("POST", "/workloads/{id}/resume"),
    ("POST", "/workloads/{id}/cancel"),
    ("POST", "/workloads/{id}/validate"),
    ("POST", "/workloads/{id}/generate-missing"),
    ("POST", "/workloads/{id}/retry-invalid"),
    ("GET", "/workloads/{id}/progress"),
    ("GET", "/workloads/{id}/objects"),
    ("GET", "/workloads/{id}/dependencies"),
    ("GET", "/workloads/{id}/audit"),
)
