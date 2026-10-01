export function isUnexpectedProjectRevisionChange({
  baseline,
  revision,
  localWriteUnchanged,
  wizardSessionActive,
}: {
  baseline: string;
  revision: string;
  localWriteUnchanged: boolean;
  wizardSessionActive: boolean;
}) {
  if (!baseline || baseline === revision || !localWriteUnchanged) return false;
  // A running wizard updates the shared project from its server-owned worker.
  // Those revisions belong to the current view even though no browser-side
  // engineering:write-completed event can be emitted for them.
  return !wizardSessionActive;
}

export function projectRevisionRefreshMode(pathname: string) {
  // The simulation workbench already has a targeted workflow refresh. A full
  // navigation would unnecessarily destroy its live job, trace and controls.
  return pathname === "/studio/simulation" ? "in-place" : "reload";
}
