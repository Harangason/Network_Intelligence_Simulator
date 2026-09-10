/** Readable labels; the physical network ID remains the stable model key. */
export function networkLabel(value: string | undefined, technology?: string): string {
  const name = (value ?? "").trim();
  const local = name.match(/^.+-IO-(.+)-(can-fd|can-xl|can|lin|automotive-ethernet|flexray)-S(\d+)(?:-CAP-S(\d+))?$/i);
  if (local) {
    const owner = local[1].replace(/-/g, " ");
    const bus = (technology ?? local[2]).replace(/_/g, "-");
    const label = bus === "automotive-ethernet" ? "Ethernet" : bus.toUpperCase();
    return `${owner[0].toLocaleUpperCase("de")}${owner.slice(1)} ${label} ${local[3]}${local[4] ? `.${local[4]}` : ""}`;
  }
  const backbone = name.match(/^(.+?)(?:_\d+)?-S(\d+)(?:-CAP-S(\d+))?$/);
  return backbone ? `${backbone[1]}_${backbone[2]}${backbone[3] ? `.${backbone[3]}` : ""}` : name;
}

/** Remove zero-length terminal segments that turn SVG arrowheads sideways. */
export function branchPath(points: Array<{ x: number; y: number }>): string {
  return points.filter((point, index) => !index || point.x !== points[index - 1].x || point.y !== points[index - 1].y)
    .map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
}
