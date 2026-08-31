"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EcuStructureTransferDialog } from "@/components/ecu-structure-transfer-dialog";
import {
  applyEngineeringStructure,
  evaluateEngineeringStructure,
  listAllEngineeringObjects,
  listSystemDuplicateCandidates,
  mergeSystemDuplicate,
  rejectEngineeringStructureProposal,
  updateEngineeringObject,
} from "@/lib/engineering-api";
import { publishEngineeringModelChanged } from "@/lib/engineering-events";
import {
  engineeringHardwareName,
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
  isMergedHardwareAlias,
} from "@/lib/engineering-object-style";
import { readActiveProjectId } from "@/lib/user-settings";
import type {
  EngineeringObject,
  EngineeringObjectType,
  EngineeringResource,
  HardwareNode,
  StructureAssignment,
  StructureEvaluation,
  SystemDuplicateCandidate,
} from "@/lib/types";

type Level = {
  type: EngineeringObjectType;
  resource: EngineeringResource;
  label: string;
  singular: string;
  parentType?: EngineeringObjectType;
  parentField?: string;
  relationType?: string;
};

const LEVELS: Level[] = [
  { type: "HardwareNode", resource: "hardware-nodes", label: "Hardware", singular: "Hardware" },
  { type: "Function", resource: "functions", label: "Funktionen", singular: "Funktion", parentType: "HardwareNode", parentField: "hardware_node_id", relationType: "HAS_FUNCTION" },
  { type: "Interface", resource: "interfaces", label: "Interfaces", singular: "Interface", parentType: "Function", parentField: "function_id", relationType: "HAS_INTERFACE" },
  { type: "Message", resource: "messages", label: "Nachrichten", singular: "Nachricht", parentType: "Interface", parentField: "interface_id", relationType: "HAS_MESSAGE" },
  { type: "Signal", resource: "signals", label: "Signale", singular: "Signal", parentType: "Message", parentField: "message_id", relationType: "CONTAINS_SIGNAL" },
];

const LEVEL_BY_TYPE = Object.fromEntries(LEVELS.map((level) => [level.type, level])) as Record<EngineeringObjectType, Level>;
const WIZARD_STEPS = [...LEVELS.map((level) => level.label), "KI-Prüfung"];
const STRUCTURE_NAME_COLLATOR = new Intl.Collator("de-DE", { numeric: true, sensitivity: "base" });
const SYSTEM_FRAME_FAMILIES: Array<{ sources: string[]; owners: string[] }> = [
  { sources: ["airbag", "crash", "impact", "seatbelt", "gurt"], owners: ["airbag", "rueckhalt"] },
  { sources: ["brake", "brems", "wheelspeed"], owners: ["bremsregelung"] },
  { sources: ["damper", "daempfer"], owners: ["daempferregelung"] },
  { sources: ["suspension", "wheelload", "verticalacceleration"], owners: ["fahrwerk"] },
  { sources: ["steering", "wheelangle", "lenk"], owners: ["lenkung"] },
  { sources: ["yaw", "pitch", "rollrate", "lateralacceleration", "longitudinalacceleration"], owners: ["stabilitaetsregelung"] },
  { sources: ["cabintemperature", "ambienttemperature", "refrigerant", "innenraum", "klima"], owners: ["klima", "klimatisierung"] },
  { sources: ["battery", "batterie", "cellvoltage"], owners: ["batteriemanagement"] },
  { sources: ["transmission", "clutch", "gearselector"], owners: ["getriebesteuerung"] },
  { sources: ["exhaust", "egrvalve", "urea", "abgas"], owners: ["abgasnachbehandlung"] },
  { sources: ["motorspeed", "motorcurrent"], owners: ["elektromotorsteuerung"] },
  { sources: ["engine", "boostpressure", "accelerator", "throttle", "turbo"], owners: ["motorsteuerung"] },
  { sources: ["radar"], owners: ["radarverarbeitung"] },
  { sources: ["camera", "kamera"], owners: ["kameraverarbeitung"] },
  { sources: ["fuel", "kraftstoff"], owners: ["kraftstoffsystem"] },
  { sources: ["tire", "reifen"], owners: ["reifendruckkontrolle"] },
  { sources: ["wheelacceleration", "wheeltorque"], owners: ["stabilitaetsregelung", "fahrdynamik"] },
  { sources: ["inverter", "dclink"], owners: ["invertersteuerung"] },
  { sources: ["alternator", "accessorycurrent", "lowvoltage"], owners: ["energieversorgung"] },
  { sources: ["rain", "washerfluid"], owners: ["wischersteuerung", "bodycontrol"] },
  { sources: ["ambientlight"], owners: ["aussenlicht", "bodycontrol"] },
  { sources: ["coolant", "oiltemperature", "intakeairtemperature", "oillevel", "temperature", "temperatur"], owners: ["thermal", "thermomanagement", "klimatisierung"] },
];

type StructureViewMode = "canonical" | "system-frames";

type SystemFrameGroup = {
  id: string;
  name: string;
  owner: HardwareNode | null;
  members: HardwareNode[];
  basis: "explicit" | "inferred" | "unassigned";
};

function objectParentId(item: EngineeringObject, level: Level) {
  if (!level.parentField || !(level.parentField in item)) return null;
  return String(item[level.parentField as keyof EngineeringObject] ?? "") || null;
}

function objectDetail(item: EngineeringObject) {
  if ("device_type" in item) return item.domain || "Hardware-Objekt";
  if ("interface_type" in item) return item.interface_type;
  if ("message_id_hex" in item) return [item.message_id_hex, item.cycle_ms !== null ? `${item.cycle_ms} ms` : null].filter(Boolean).join(" · ") || "Message";
  if ("length_bits" in item) return [item.length_bits !== null ? `${item.length_bits} Bit` : null, item.unit].filter(Boolean).join(" · ") || "Signal";
  return item.domain || item.object_type;
}

function structureTypeLabel(item: EngineeringObject, level: Level) {
  if (!("device_type" in item)) return level.singular;
  return {
    ActuatorController: "Aktor",
    EmbeddedController: "Controller",
    SensorController: "Sensor",
  }[item.device_type] ?? item.device_type ?? "Hardware";
}

function structureDisplayName(item: EngineeringObject) {
  let value = item.name;
  if ("device_type" in item) {
    value = engineeringHardwareName(value);
  } else {
    value = value.replace(/ECU(?=[A-ZÄÖÜ_ -]|$)/g, "").replace(/Gateway(?=[A-ZÄÖÜ_ -]|$)/gi, "");
  }
  value = value.replace(/[_]+/g, " ").replace(/\s{2,}/g, " ").replace(/^[- ]+|[- ]+$/g, "").trim();
  return value || item.name;
}

function compareStructureObjects(left: EngineeringObject, right: EngineeringObject) {
  return STRUCTURE_NAME_COLLATOR.compare(structureDisplayName(left), structureDisplayName(right))
    || left.id.localeCompare(right.id);
}

function systemFrameKey(value: unknown) {
  let normalized = engineeringHardwareName(String(value || "")).toLowerCase();
  for (const [source, target] of [["ä", "ae"], ["ö", "oe"], ["ü", "ue"], ["ß", "ss"]] as const) {
    normalized = normalized.replaceAll(source, target);
  }
  return normalized.replace(/[^a-z0-9]/g, "");
}

function explicitSystemOwnerId(item: HardwareNode) {
  const value = item.identity?.system_owner_id ?? item.identity?.systemOwnerId;
  return typeof value === "string" && value ? value : null;
}

function inferredSystemOwner(item: HardwareNode, processors: HardwareNode[]) {
  if (item.device_type === "Gateway") return null;
  if (item.device_type === "ECU") return item;
  const itemKey = systemFrameKey(item.name);
  const scored = processors
    .map((processor) => {
      const ownerKey = systemFrameKey(processor.name);
      let score = ownerKey.length > 3 && itemKey.startsWith(ownerKey) ? ownerKey.length + 2000 : 0;
      for (const family of SYSTEM_FRAME_FAMILIES) {
        const specificity = Math.max(...family.sources.map((token) => itemKey.includes(token) ? token.length : 0));
        if (!specificity) continue;
        for (const [index, owner] of family.owners.entries()) {
          if (ownerKey.includes(owner)) score = Math.max(score, (owner === ownerKey ? 1200 : 800) + specificity * 20 - index * 80);
        }
      }
      return { processor, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);
  return scored.length && (scored.length === 1 || scored[0].score > scored[1].score) ? scored[0].processor : null;
}

function buildSystemFrameGroups(hardware: HardwareNode[]) {
  const processors = hardware.filter((item) => item.device_type === "ECU");
  const byId = new Map(hardware.map((item) => [item.id, item]));
  const groups = new Map<string, SystemFrameGroup>();
  const ensureGroup = (owner: HardwareNode | null, basis: SystemFrameGroup["basis"]) => {
    const id = owner?.id ?? "unassigned";
    const current = groups.get(id);
    if (current) {
      if (current.basis !== "explicit" && basis === "explicit") current.basis = "explicit";
      return current;
    }
    const group = {
      id,
      name: owner ? `Systemrahmen ${structureDisplayName(owner)}` : "Ohne Systemrahmen",
      owner,
      members: [],
      basis,
    };
    groups.set(id, group);
    return group;
  };
  for (const item of hardware) {
    if (item.device_type === "Gateway") continue;
    const explicitOwner = explicitSystemOwnerId(item);
    const owner = explicitOwner && byId.get(explicitOwner)?.device_type === "ECU"
      ? byId.get(explicitOwner) as HardwareNode
      : inferredSystemOwner(item, processors);
    const basis = explicitOwner && owner ? "explicit" : owner ? "inferred" : "unassigned";
    ensureGroup(owner, basis).members.push(item);
  }
  for (const processor of processors) ensureGroup(processor, "inferred");
  return [...groups.values()].map((group) => ({
    ...group,
    members: [...new Map(group.members.map((member) => [member.id, member])).values()].sort(compareStructureObjects),
  })).sort((left, right) => {
    if (left.id === "unassigned") return 1;
    if (right.id === "unassigned") return -1;
    return STRUCTURE_NAME_COLLATOR.compare(left.name, right.name);
  });
}

function emptySelection(): Record<EngineeringObjectType, string[]> {
  return { HardwareNode: [], Function: [], Interface: [], Message: [], Signal: [] };
}

function includesText(item: EngineeringObject, query: string) {
  if (!query) return true;
  return [item.name, item.description, item.domain, objectDetail(item)]
    .some((value) => String(value ?? "").toLocaleLowerCase("de-DE").includes(query));
}

function isHardwareNode(item: EngineeringObject): item is HardwareNode {
  return item.object_type === "HardwareNode" && "device_type" in item;
}

export function StructureTreeWorkbench({ onChanged }: { onChanged: () => void }) {
  const [objects, setObjects] = useState<Record<EngineeringObjectType, EngineeringObject[]>>({
    HardwareNode: [], Function: [], Interface: [], Message: [], Signal: [],
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<EngineeringObjectType | "all">("all");
  const [viewMode, setViewMode] = useState<StructureViewMode>("canonical");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [hardwareOrder, setHardwareOrder] = useState<string[]>([]);
  const draggedTypeRef = useRef<EngineeringObjectType | null>(null);
  const draggedIdRef = useRef<string | null>(null);
  const [renaming, setRenaming] = useState<{ type: EngineeringObjectType; id: string; value: string } | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [systemDuplicates, setSystemDuplicates] = useState<SystemDuplicateCandidate[]>([]);
  const [mergeCandidate, setMergeCandidate] = useState<SystemDuplicateCandidate | null>(null);
  const activeHardware = useMemo(
    () => objects.HardwareNode.filter(isHardwareNode).filter((item) => !isMergedHardwareAlias(item)),
    [objects.HardwareNode],
  );
  const activeObjects = useMemo(
    () => ({ ...objects, HardwareNode: activeHardware }),
    [activeHardware, objects],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [groups, duplicates] = await Promise.all([
        Promise.all(LEVELS.map((level) => listAllEngineeringObjects(level.resource))),
        listSystemDuplicateCandidates(),
      ]);
      const next = Object.fromEntries(LEVELS.map((level, index) => [level.type, groups[index]])) as Record<EngineeringObjectType, EngineeringObject[]>;
      setObjects(next);
      setSystemDuplicates(duplicates);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Structure Tree konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!activeHardware.length) return;
    const available = [...activeHardware].sort(compareStructureObjects).map((item) => item.id);
    try {
      const key = `engineering-structure-hardware-order:${readActiveProjectId()}`;
      const saved = JSON.parse(localStorage.getItem(key) ?? "null") as {
        ids?: unknown;
        mode?: unknown;
        version?: unknown;
      } | null;
      const stored = saved?.version === 2 && saved.mode === "custom" && Array.isArray(saved.ids)
        ? saved.ids.filter((id): id is string => typeof id === "string")
        : [];
      const restored = [...stored.filter((id) => available.includes(id)), ...available.filter((id) => !stored.includes(id))];
      setHardwareOrder(restored);
    } catch {
      setHardwareOrder(available);
    }
  }, [activeHardware]);

  const objectMap = useMemo(
    () => new Map(LEVELS.flatMap((level) => objects[level.type]).map((item) => [item.id, item])),
    [objects],
  );

  const childrenByParent = useMemo(() => {
    const result = new Map<string, EngineeringObject[]>();
    for (const level of LEVELS.slice(1)) {
      for (const item of objects[level.type]) {
        const parentId = objectParentId(item, level);
        if (!parentId) continue;
        const current = result.get(parentId) ?? [];
        current.push(item);
        result.set(parentId, current);
      }
    }
    for (const items of result.values()) items.sort(compareStructureObjects);
    return result;
  }, [objects]);

  const children = useCallback(
    (parent: EngineeringObject) => childrenByParent.get(parent.id) ?? [],
    [childrenByParent],
  );

  const systemDuplicatesByHardware = useMemo(() => {
    const result = new Map<string, SystemDuplicateCandidate[]>();
    for (const candidate of systemDuplicates) {
      for (const id of [candidate.canonical_hardware.id, candidate.duplicate_hardware.id]) {
        result.set(id, [...(result.get(id) ?? []), candidate]);
      }
    }
    return result;
  }, [systemDuplicates]);

  const normalizedQuery = query.trim().toLocaleLowerCase("de-DE");
  const treeVisible = useCallback((item: EngineeringObject): boolean => {
    const direct = (typeFilter === "all" || typeFilter === item.object_type) && includesText(item, normalizedQuery);
    return direct || children(item).some(treeVisible);
  }, [children, normalizedQuery, typeFilter]);

  const orphans = useMemo(() => LEVELS.slice(1).flatMap((level) => (
    objects[level.type].filter((item) => {
      const parentId = objectParentId(item, level);
      return !parentId || !objectMap.has(parentId);
    })
  )).sort(compareStructureObjects), [objectMap, objects]);

  const orderedHardware = useMemo(() => {
    const rank = new Map(hardwareOrder.map((id, index) => [id, index]));
    return [...activeHardware].sort((left, right) => {
      const ranked = (rank.get(left.id) ?? Number.MAX_SAFE_INTEGER) - (rank.get(right.id) ?? Number.MAX_SAFE_INTEGER);
      return ranked || compareStructureObjects(left, right);
    });
  }, [activeHardware, hardwareOrder]);

  const systemFrameGroups = useMemo(() => buildSystemFrameGroups(activeHardware), [activeHardware]);

  const visibleSystemFrameGroups = useMemo(() => systemFrameGroups.filter((group) => {
    if (!normalizedQuery) return true;
    return group.name.toLocaleLowerCase("de-DE").includes(normalizedQuery)
      || group.members.some((member) => treeVisible(member));
  }), [normalizedQuery, systemFrameGroups, treeVisible, typeFilter]);

  function toggleExpanded(id: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function assignByDrop(child: EngineeringObject, parent: EngineeringObject) {
    const level = LEVEL_BY_TYPE[child.object_type];
    if (!level.parentType || level.parentType !== parent.object_type || !level.parentField || !level.relationType) return;
    setBusy(true);
    setError("");
    try {
      await applyEngineeringStructure({
        assignments: [{
          child_type: child.object_type as Exclude<EngineeringObjectType, "HardwareNode">,
          child_id: child.id,
          child_name: child.name,
          parent_type: parent.object_type,
          parent_id: parent.id,
          parent_name: parent.name,
          parent_field: level.parentField,
          relation_type: level.relationType,
          confidence: 1,
          reason: "Manuelle Drag-and-drop-Zuordnung",
          current_name: child.name,
          recommended_name: child.name,
          learning_key: `manual:${parent.id}>${child.id}`,
          name: child.name,
        }],
      });
      setNotice(`${child.name} wurde ${parent.name} zugeordnet.`);
      setExpanded((current) => new Set(current).add(parent.id));
      publishEngineeringModelChanged({ resource: "relations", id: child.id, name: child.name });
      await load();
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Zuordnung konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
      setDropTarget(null);
    }
  }

  async function assignHardwareToSystemFrame(childId: string, owner: HardwareNode | null) {
    if (!owner || childId === owner.id) return;
    const child = activeHardware.find((item) => item.id === childId);
    if (!child || child.device_type === "Gateway") return;
    setBusy(true);
    setError("");
    try {
      await updateEngineeringObject("hardware-nodes", child.id, {
        identity: {
          ...(child.identity ?? {}),
          system_owner_id: owner.id,
          system_owner_source: "structure_tree",
        },
        actor: "structure-tree-reviewer",
        change_summary: `Systemrahmen ${owner.name} zugeordnet`,
      });
      setNotice(`${structureDisplayName(child)} wurde ${structureDisplayName(owner)} als Systemrahmen zugeordnet.`);
      setExpanded((current) => new Set(current).add(`system-frame:${owner.id}`));
      publishEngineeringModelChanged({ resource: "hardware-nodes", id: child.id, name: child.name });
      await load();
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Systemrahmen-Zuordnung konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
      setDropTarget(null);
    }
  }

  function reorderHardware(sourceId: string, targetId: string) {
    if (sourceId === targetId) return;
    const current = orderedHardware.map((item) => item.id);
    const sourceIndex = current.indexOf(sourceId);
    const targetIndex = current.indexOf(targetId);
    if (sourceIndex < 0 || targetIndex < 0) return;
    current.splice(sourceIndex, 1);
    current.splice(current.indexOf(targetId), 0, sourceId);
    setHardwareOrder(current);
    try {
      localStorage.setItem(
        `engineering-structure-hardware-order:${readActiveProjectId()}`,
        JSON.stringify({ ids: current, mode: "custom", version: 2 }),
      );
    } catch {
      // The visual order still remains active for the current session.
    }
    setNotice("Die ECU-Reihenfolge wurde gespeichert.");
  }

  function canDropOn(target: EngineeringObject) {
    const draggedType = draggedTypeRef.current;
    if (!draggedType) return false;
    if (draggedType === "HardwareNode") {
      return target.object_type === "HardwareNode" && draggedIdRef.current !== target.id;
    }
    return LEVEL_BY_TYPE[draggedType].parentType === target.object_type;
  }

  function canDropOnSystemFrame(group: SystemFrameGroup) {
    return viewMode === "system-frames"
      && draggedTypeRef.current === "HardwareNode"
      && Boolean(group.owner)
      && draggedIdRef.current !== group.owner?.id;
  }

  async function saveName() {
    if (!renaming || !renaming.value.trim()) return;
    const level = LEVEL_BY_TYPE[renaming.type];
    setBusy(true);
    setError("");
    try {
      await updateEngineeringObject(level.resource, renaming.id, {
        name: renaming.value.trim(),
        actor: "structure-tree-reviewer",
        change_summary: "structure tree rename",
      });
      publishEngineeringModelChanged({ resource: level.resource, id: renaming.id, name: renaming.value.trim() });
      setRenaming(null);
      setNotice("Name und abhängige Typwerte wurden aktualisiert.");
      await load();
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Name konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmSystemMerge() {
    if (!mergeCandidate) return;
    setBusy(true);
    setError("");
    try {
      const result = await mergeSystemDuplicate(mergeCandidate);
      setNotice(
        `${result.superseded_hardware.name} wurde reversibel mit ${result.canonical_hardware.name} zusammengeführt.`,
      );
      setMergeCandidate(null);
      publishEngineeringModelChanged({
        resource: "relations",
        id: result.relation_id,
        name: `${result.superseded_hardware.name} → ${result.canonical_hardware.name}`,
      });
      await load();
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Systeme konnten nicht zusammengeführt werden.");
    } finally {
      setBusy(false);
    }
  }

  function renderNode(item: EngineeringObject, depth: number): React.ReactNode {
    if (!treeVisible(item)) return null;
    const nodeChildren = children(item).filter(treeVisible);
    const isExpanded = expanded.has(item.id) || Boolean(normalizedQuery);
    const level = LEVEL_BY_TYPE[item.object_type];
    const displayName = structureDisplayName(item);
    const duplicateCandidates = item.object_type === "HardwareNode"
      ? systemDuplicatesByHardware.get(item.id) ?? []
      : [];
    return (
      <li className="structure-tree-node" key={item.id}>
        <div
          className={`structure-tree-row eng-object-surface ${engineeringObjectTypeClass(item.object_type)} ${dropTarget === item.id ? "drop-target" : ""}`}
          data-depth={depth}
          draggable
          onDragEnd={() => { draggedTypeRef.current = null; draggedIdRef.current = null; setDropTarget(null); }}
          onDragOver={(event) => {
            const raw = event.dataTransfer.types.includes("application/x-engineering-structure");
            if (raw && canDropOn(item)) {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
            }
          }}
          onDragStart={(event) => {
            draggedTypeRef.current = item.object_type;
            draggedIdRef.current = item.id;
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("application/x-engineering-structure", JSON.stringify({ type: item.object_type, id: item.id }));
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDropTarget(null);
            const raw = event.dataTransfer.getData("application/x-engineering-structure");
            if (!raw) return;
            try {
              const dragged = JSON.parse(raw) as { type: EngineeringObjectType; id: string };
              if (dragged.type === "HardwareNode" && item.object_type === "HardwareNode") {
                reorderHardware(dragged.id, item.id);
                return;
              }
              const child = objects[dragged.type]?.find((candidate) => candidate.id === dragged.id);
              if (child) void assignByDrop(child, item);
            } catch {
              setError("Das verschobene Objekt konnte nicht gelesen werden.");
            }
          }}
          onDragEnter={() => canDropOn(item) && setDropTarget(item.id)}
          onDragLeave={(event) => !event.currentTarget.contains(event.relatedTarget as Node) && setDropTarget(null)}
        >
          <span aria-hidden="true" className="structure-drag-handle" />
          <button
            aria-label={isExpanded ? `${item.name} einklappen` : `${item.name} ausklappen`}
            className="structure-expand"
            disabled={!nodeChildren.length}
            onClick={() => toggleExpanded(item.id)}
            type="button"
          >
            {nodeChildren.length ? (isExpanded ? "−" : "+") : "·"}
          </button>
          <span className={`structure-type eng-object-badge ${engineeringObjectTypeClass(item.object_type)}`}>{structureTypeLabel(item, level)}</span>
          {renaming?.id === item.id ? (
            <span className="structure-rename-control">
              <input autoFocus onChange={(event) => setRenaming({ ...renaming, value: event.target.value })} onKeyDown={(event) => {
                if (event.key === "Enter") { event.preventDefault(); void saveName(); }
                if (event.key === "Escape") setRenaming(null);
              }} value={renaming.value} />
              <button disabled={busy} onClick={() => void saveName()} type="button">Speichern</button>
              <button onClick={() => setRenaming(null)} type="button">Abbrechen</button>
            </span>
          ) : (
            <>
              <span className="structure-object-copy"><strong title={displayName !== item.name ? `Technischer Name: ${item.name}` : undefined}>{displayName}</strong></span>
              <span className="structure-object-meta">
                <span>{objectDetail(item)} · v{item.version}</span>
                {duplicateCandidates.map((candidate) => {
                  const counterpart = candidate.canonical_hardware.id === item.id
                    ? candidate.duplicate_hardware
                    : candidate.canonical_hardware;
                  return <span className="structure-duplicate-badge" key={candidate.candidate_key} title={candidate.reason}>System-Dublette {Math.round(candidate.confidence * 100)} %: {counterpart.name}</span>;
                })}
              </span>
            </>
          )}
          {renaming?.id !== item.id && (
            <button className="button secondary tiny structure-rename" onClick={() => setRenaming({ type: item.object_type, id: item.id, value: displayName })} type="button">Name ändern</button>
          )}
        </div>
        {isExpanded && nodeChildren.length > 0 && <ul>{nodeChildren.map((child) => renderNode(child, depth + 1))}</ul>}
      </li>
    );
  }

  function renderSystemFrame(group: SystemFrameGroup) {
    const isExpanded = expanded.has(`system-frame:${group.id}`) || Boolean(normalizedQuery);
    const members = group.members.filter(treeVisible);
    const counts = {
      ecu: members.filter((item) => item.device_type === "ECU").length,
      sensors: members.filter((item) => item.device_type === "SensorController").length,
      actors: members.filter((item) => item.device_type === "ActuatorController").length,
    };
    return (
      <li className="structure-tree-node structure-system-frame-node" key={group.id}>
        <div
          className={`structure-tree-row structure-system-frame-row ${dropTarget === `system-frame:${group.id}` ? "drop-target" : ""}`}
          draggable={false}
          onDragEnter={() => canDropOnSystemFrame(group) && setDropTarget(`system-frame:${group.id}`)}
          onDragLeave={(event) => !event.currentTarget.contains(event.relatedTarget as Node) && setDropTarget(null)}
          onDragOver={(event) => {
            if (canDropOnSystemFrame(group)) {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDropTarget(null);
            const raw = event.dataTransfer.getData("application/x-engineering-structure");
            if (!raw) return;
            try {
              const dragged = JSON.parse(raw) as { type: EngineeringObjectType; id: string };
              if (dragged.type === "HardwareNode") void assignHardwareToSystemFrame(dragged.id, group.owner);
            } catch {
              setError("Das verschobene Objekt konnte nicht gelesen werden.");
            }
          }}
        >
          <span aria-hidden="true" className="structure-frame-mark" />
          <button
            aria-label={isExpanded ? `${group.name} einklappen` : `${group.name} ausklappen`}
            className="structure-expand"
            disabled={!members.length}
            onClick={() => toggleExpanded(`system-frame:${group.id}`)}
            type="button"
          >
            {members.length ? (isExpanded ? "−" : "+") : "·"}
          </button>
          <span className="structure-type eng-object-badge hardware">System</span>
          <span className="structure-object-copy"><strong>{group.name}</strong></span>
          <span className="structure-object-meta">
            <span>{counts.ecu} ECU · {counts.sensors} Sensoren · {counts.actors} Aktoren</span>
            <span>{group.basis === "explicit" ? "explizit zugeordnet" : group.basis === "inferred" ? "fachlich abgeleitet" : "Zuordnung offen"}</span>
          </span>
          <span className="structure-frame-drop-hint">{group.owner ? "Hardware hierher ziehen" : "Keine Ziel-ECU"}</span>
        </div>
        {isExpanded && members.length > 0 && <ul>{members.map((member) => renderNode(member, 1))}</ul>}
      </li>
    );
  }

  return (
    <section className="structure-tree-workbench">
      <header className="structure-tree-toolbar">
        <div>
          <p className="eyebrow">Kanonische Abhängigkeiten</p>
          <h3>Structure Tree</h3>
          <span>{viewMode === "system-frames" ? `Systemrahmen: ${systemFrameGroups.length} · Hardware: ${activeHardware.length}` : LEVELS.map((level) => `${level.label}: ${activeObjects[level.type].length}`).join(" · ")}</span>
        </div>
        <div className="structure-tree-actions">
          <button className="button secondary" disabled={loading || busy} onClick={() => void load()} type="button">Aktualisieren</button>
          <button className="button secondary ecu-transfer-launch" disabled={loading || busy} onClick={() => setTransferOpen(true)} type="button">KI auf ECUs anwenden</button>
          <button className="button primary" disabled={loading || busy} onClick={() => setWizardOpen(true)} type="button">Structure Wizard</button>
        </div>
      </header>

      <div className="structure-tree-filters">
        <label><span>Baum filtern</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Name, Typ oder Wert" type="search" value={query} /></label>
        <label><span>Objekttyp</span><select onChange={(event) => setTypeFilter(event.target.value as EngineeringObjectType | "all")} value={typeFilter}><option value="all">Alle Stufen</option>{LEVELS.map((level) => <option key={level.type} value={level.type}>{level.label}</option>)}</select></label>
        <div className="structure-view-toggle" aria-label="Structure-Tree-Ansicht" role="group"><button className={viewMode === "canonical" ? "active" : ""} onClick={() => setViewMode("canonical")} type="button">Kanonisch</button><button className={viewMode === "system-frames" ? "active" : ""} onClick={() => setViewMode("system-frames")} type="button">Systemrahmen</button></div>
        <div className="structure-tree-legend"><span><i className="good" />zugeordnet</span><span><i className="warning" />nicht zugeordnet</span></div>
      </div>

      {systemDuplicates.length > 0 && (
        <section aria-label="Erkannte System-Dubletten" className="structure-system-duplicates">
          <header>
            <div><p className="eyebrow">KI-Systemprüfung</p><strong>{systemDuplicates.length} mögliche {systemDuplicates.length === 1 ? "System-Dublette" : "System-Dubletten"} erkannt</strong></div>
            <span>Namen und vollständige technische Struktur wurden gemeinsam bewertet.</span>
          </header>
          <div className="structure-system-duplicate-list">
            {systemDuplicates.map((candidate) => (
              <article key={candidate.candidate_key}>
                <strong>{candidate.canonical_hardware.name}</strong>
                <span>entspricht</span>
                <strong>{candidate.duplicate_hardware.name}</strong>
                <em>{Math.round(candidate.confidence * 100)} %</em>
                <button
                  className="button secondary tiny system-merge-launch"
                  disabled={busy}
                  onClick={() => setMergeCandidate(candidate)}
                  type="button"
                >
                  Zusammenführen
                </button>
                <small>{candidate.reason} Kanonischer Vorschlag: {candidate.canonical_hardware.name} ({candidate.canonical_hardware.child_count} untergeordnete Objekte).</small>
              </article>
            ))}
          </div>
        </section>
      )}

      {error && <div className="inline-error">{error}</div>}
      {notice && <div className="inline-success">{notice}</div>}
      {loading ? <div className="loading-panel">Struktur wird geladen …</div> : (
        <div className="structure-tree-canvas">
          <div aria-hidden="true" className="structure-tree-column-head"><span /><span /><span>Typ</span><span>Name</span><span>Details</span><span /></div>
          <ul className="structure-tree-root">{viewMode === "system-frames" ? visibleSystemFrameGroups.map(renderSystemFrame) : orderedHardware.map((item) => renderNode(item, 0))}</ul>
          {viewMode === "canonical" && orphans.length > 0 && (
            <section className="structure-orphans">
              <header><strong>Nicht zugeordnet</strong><span>{orphans.length}</span></header>
              <ul>{orphans.filter(treeVisible).map((item) => renderNode(item, 0))}</ul>
            </section>
          )}
        </div>
      )}

      {wizardOpen && (
        <StructureWizard
          objects={activeObjects}
          onClose={() => setWizardOpen(false)}
          onSaved={async (message) => {
            setNotice(message);
            setWizardOpen(false);
            await load();
            publishEngineeringModelChanged({ resource: "relations", id: "structure-tree", name: "Structure Tree" });
            onChanged();
          }}
        />
      )}
      {transferOpen && (
        <EcuStructureTransferDialog
          hardware={activeHardware}
          onChanged={async (message) => {
            setNotice(message);
            await load();
            publishEngineeringModelChanged({ resource: "relations", id: "ecu-structure-transfer", name: "ECU-Strukturtransfer" });
            onChanged();
          }}
          onClose={() => setTransferOpen(false)}
        />
      )}
      {mergeCandidate && (
        <div className="project-dialog-backdrop" role="presentation">
          <section
            aria-labelledby="system-merge-title"
            aria-modal="true"
            className="project-dialog system-merge-dialog"
            role="dialog"
          >
            <header>
              <p className="eyebrow">Kanonische Zusammenführung</p>
              <h2 id="system-merge-title">Systeme zusammenführen?</h2>
              <p>
                Die technische Historie bleibt vollständig erhalten. Das zweite System wird als
                abgelöster Alias mit dem kanonischen System verbunden.
              </p>
            </header>
            <dl className="system-merge-summary">
              <div><dt>Kanonisches System</dt><dd>{mergeCandidate.canonical_hardware.name}</dd></div>
              <div><dt>Abgelöster Alias</dt><dd>{mergeCandidate.duplicate_hardware.name}</dd></div>
              <div><dt>KI-Konfidenz</dt><dd>{Math.round(mergeCandidate.confidence * 100)} %</dd></div>
            </dl>
            <p className="system-merge-note">
              Unterobjekte werden nicht gelöscht. Die Alias-Relation ist im Knowledge Graph wirksam
              und kann anhand der gespeicherten Provenienz wieder aufgelöst werden.
            </p>
            <div className="project-dialog-actions">
              <button className="button secondary" disabled={busy} onClick={() => setMergeCandidate(null)} type="button">
                Abbrechen
              </button>
              <button className="button primary" disabled={busy} onClick={() => void confirmSystemMerge()} type="button">
                {busy ? "Wird zusammengeführt …" : "Zusammenführen"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function StructureWizard({
  objects,
  onClose,
  onSaved,
}: {
  objects: Record<EngineeringObjectType, EngineeringObject[]>;
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}) {
  const [step, setStep] = useState(0);
  const [selection, setSelection] = useState<Record<EngineeringObjectType, string[]>>(emptySelection);
  const [filter, setFilter] = useState("");
  const [evaluation, setEvaluation] = useState<StructureEvaluation | null>(null);
  const [assignments, setAssignments] = useState<StructureAssignment[]>([]);
  const [applyHardwareAdjustment, setApplyHardwareAdjustment] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const level = LEVELS[Math.min(step, LEVELS.length - 1)];
  const filteredObjects = step < LEVELS.length
    ? objects[level.type].filter((item) => includesText(item, filter.trim().toLocaleLowerCase("de-DE")))
    : [];

  function selectedName(type: EngineeringObjectType, id: string | null) {
    return objects[type].find((item) => item.id === id)?.name ?? "Nicht gewählt";
  }

  function toggle(type: EngineeringObjectType, id: string) {
    setSelection((current) => {
      if (type === "HardwareNode") return { ...emptySelection(), HardwareNode: [id] };
      const values = current[type];
      return { ...current, [type]: values.includes(id) ? values.filter((value) => value !== id) : [...values, id] };
    });
  }

  async function evaluate() {
    setBusy(true);
    setError("");
    try {
      const result = await evaluateEngineeringStructure(selection);
      setEvaluation(result);
      setAssignments(result.suggestions.map((suggestion) => ({ ...suggestion, name: suggestion.current_name })));
      setStep(LEVELS.length);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "KI-Bewertung konnte nicht erzeugt werden.");
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (step === LEVELS.length - 1) { void evaluate(); return; }
    setStep((current) => Math.min(LEVELS.length, current + 1));
    setFilter("");
  }

  async function apply() {
    if (!evaluation) return;
    setBusy(true);
    setError("");
    try {
      const hardwareUpdates = applyHardwareAdjustment
        ? evaluation.hardware_adjustments
          .filter((item) => item.current_value !== item.suggested_value)
          .map((item) => ({ object_type: item.object_type, id: item.id, updates: { [item.field]: item.suggested_value } }))
        : [];
      const result = await applyEngineeringStructure({
        proposal_id: evaluation.proposal_id,
        assignments,
        object_updates: hardwareUpdates,
      });
      await onSaved(`${result.count} Abhängigkeiten wurden kanonisch gespeichert; die KI-Bewertung wurde als Lernbeispiel übernommen.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Struktur konnte nicht übernommen werden.");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!evaluation) { onClose(); return; }
    setBusy(true);
    try {
      await rejectEngineeringStructureProposal(evaluation.proposal_id);
      await onSaved("Der Vorschlag wurde abgelehnt und als negatives Lernbeispiel gespeichert.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Vorschlag konnte nicht abgelehnt werden.");
    } finally {
      setBusy(false);
    }
  }

  const canContinue = step < LEVELS.length && selection[level.type].length > 0;

  return (
    <div className="proposal-wizard-backdrop structure-wizard-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()} role="presentation">
      <section aria-modal="true" className="proposal-wizard structure-wizard" role="dialog">
        <header>
          <div><p className="eyebrow">Structure Wizard</p><h3>Abhängigkeiten geführt aufbauen</h3><span>Hardware einzeln, alle folgenden Stufen mit Mehrfachauswahl.</span></div>
          <button aria-label="Structure Wizard schließen" className="eng-dialog-close" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <nav className="proposal-wizard-steps" aria-label="Structure-Wizard-Schritte">{WIZARD_STEPS.map((label, index) => <button aria-current={step === index ? "step" : undefined} className={`${index < LEVELS.length ? `eng-object-accent ${engineeringObjectTypeClass(LEVELS[index].type)}` : ""} ${step === index ? "active" : ""}`} disabled={index > step || busy} key={label} onClick={() => { setStep(index); setFilter(""); }} type="button"><span>{index + 1}</span>{label}</button>)}</nav>

        {step < LEVELS.length && (
          <div className="structure-wizard-selection">
            <div className="structure-wizard-filter"><label><span>{level.label} filtern</span><input autoFocus onChange={(event) => setFilter(event.target.value)} placeholder="Name, Domäne oder technischer Wert" type="search" value={filter} /></label><span>{selection[level.type].length} ausgewählt</span></div>
            <div className="structure-choice-list">
              {filteredObjects.map((item) => {
                const checked = selection[level.type].includes(item.id);
                const parentLevel = level.parentType ? LEVEL_BY_TYPE[level.parentType] : null;
                const parentId = objectParentId(item, level);
                return <label className={`structure-choice eng-object-surface ${engineeringObjectTypeClass(item.object_type)} ${checked ? "selected" : ""}`} key={item.id}><input checked={checked} name={level.type === "HardwareNode" ? "structure-hardware" : undefined} onChange={() => toggle(level.type, item.id)} type={level.type === "HardwareNode" ? "radio" : "checkbox"} /><span><strong>{item.name}</strong><small>{objectDetail(item)}{parentLevel ? ` · aktuell: ${selectedName(parentLevel.type, parentId)}` : ""}</small></span><i>{item.approval_state === "approved" ? "freigegeben" : item.review_state}</i></label>;
              })}
              {filteredObjects.length === 0 && <div className="eng-proposal-empty">Keine passenden Objekte gefunden.</div>}
            </div>
          </div>
        )}

        {step === LEVELS.length && evaluation && (
          <div className="structure-ai-review">
            <div className="structure-ai-score"><div><p className="eyebrow">KI-Bewertung</p><strong>{Math.round(evaluation.confidence * 100)} % Konfidenz</strong><span>{evaluation.model} v{evaluation.model_version}</span></div><dl><div><dt>Bestätigt</dt><dd>{evaluation.learning.accepted}</dd></div><div><dt>Abgelehnt</dt><dd>{evaluation.learning.rejected}</dd></div><div><dt>Lernbasis</dt><dd>{evaluation.learning.reviewed}</dd></div></dl></div>
            {evaluation.hardware_adjustments.map((item) => <label className="structure-hardware-adjustment" key={item.id}><input checked={applyHardwareAdjustment} onChange={(event) => setApplyHardwareAdjustment(event.target.checked)} type="checkbox" /><span><strong>{item.name}: {item.current_value} → {item.suggested_value}</strong><small>{item.reason}</small></span></label>)}
            <div className="structure-assignment-table-wrap"><table className="structure-assignment-table"><thead><tr><th>Objekt</th><th>Zielgruppe</th><th>KI-Bewertung</th><th>Name</th></tr></thead><tbody>{assignments.map((assignment, index) => {
              const parentOptions = selection[assignment.parent_type].map((id) => objects[assignment.parent_type].find((item) => item.id === id)).filter((item): item is EngineeringObject => Boolean(item));
              return <tr key={`${assignment.child_type}:${assignment.child_id}`}><td><strong>{assignment.child_name}</strong><small className={`eng-object-badge ${engineeringObjectTypeClass(assignment.child_type)}`}>{engineeringObjectTypeLabel(assignment.child_type)}</small></td><td><select onChange={(event) => { const parent = parentOptions.find((item) => item.id === event.target.value); const original = evaluation.suggestions[index]; setAssignments((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, parent_id: event.target.value, parent_name: parent?.name ?? item.parent_name, confidence: original.parent_id === event.target.value ? original.confidence : 0.5, reason: original.parent_id === event.target.value ? original.reason : "Manuell vom KI-Vorschlag abweichend", learning_key: `${item.relation_type}:manual:${event.target.value}>${item.child_id}` } : item)); }} value={assignment.parent_id}>{parentOptions.map((parent) => <option key={parent.id} value={parent.id}>{parent.name}</option>)}</select></td><td><span className={`structure-confidence ${assignment.confidence >= 0.75 ? "high" : assignment.confidence >= 0.55 ? "medium" : "low"}`}>{Math.round(assignment.confidence * 100)} %</span><small>{assignment.reason}</small></td><td><input onChange={(event) => setAssignments((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item))} value={assignment.name} /><button className="button secondary tiny" onClick={() => setAssignments((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, name: item.recommended_name } : item))} type="button">KI-Name</button><small>Vorschlag: {assignment.recommended_name}</small></td></tr>;
            })}</tbody></table></div>
          </div>
        )}

        {error && <div className="inline-error structure-wizard-error">{error}</div>}
        <footer>
          <div>{step === LEVELS.length && evaluation ? <><button className="button danger" disabled={busy} onClick={() => void reject()} type="button">Vorschlag ablehnen</button><button className="button secondary" disabled={busy} onClick={() => setAssignments((current) => current.map((item) => ({ ...item, name: item.recommended_name })))} type="button">Alle KI-Namen übernehmen</button></> : <button className="button secondary" disabled={busy} onClick={onClose} type="button">Abbrechen</button>}</div>
          <div><button className="button secondary" disabled={step === 0 || busy} onClick={() => { setStep((current) => Math.max(0, current - 1)); setFilter(""); }} type="button">Zurück</button>{step < LEVELS.length ? <button className="button primary" disabled={!canContinue || busy} onClick={next} type="button">{step === LEVELS.length - 1 ? (busy ? "KI bewertet …" : "KI bewerten") : "Weiter"}</button> : <button className="button primary" disabled={busy || !assignments.length} onClick={() => void apply()} type="button">{busy ? "Wird übernommen …" : "Abhängigkeiten übernehmen"}</button>}</div>
        </footer>
      </section>
    </div>
  );
}
