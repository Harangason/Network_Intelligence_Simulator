import { ToolLoopAgent, InferAgentUIMessage, isStepCount, tool } from "ai";
import { z } from "zod";
import {
  createObject,
  createRelation,
  listObjects,
  listRelations,
} from "@/lib/engineering-server-client";

const RESOURCE_ENUM = ["hardware-nodes", "functions", "interfaces", "messages", "signals"] as const;
const OBJECT_TYPE_ENUM = ["HardwareNode", "Function", "Interface", "Message", "Signal"] as const;

const listEngineeringObjects = tool({
  description:
    "Liste vorhandene Engineering-Objekte (HardwareNode, Function, Interface, Message oder Signal) " +
    "aus dem kanonischen Modell, optional gefiltert nach Domäne oder verknüpfter ID.",
  inputSchema: z.object({
    resource: z.enum(RESOURCE_ENUM).describe("Ressourcentyp im Plural, z. B. 'hardware-nodes'."),
    domain: z.string().optional().describe("Filter nach Anwendungsdomäne, z. B. 'automotive'."),
    hardware_node_id: z.string().optional().describe("Filter für Functions/Interfaces nach Hardware-Knoten-ID."),
    interface_id: z.string().optional().describe("Filter für Messages nach Interface-ID."),
    message_id: z.string().optional().describe("Filter für Signals nach Message-ID."),
  }),
  execute: async ({ resource, domain, hardware_node_id, interface_id, message_id }) => {
    const result = await listObjects(resource, {
      domain,
      hardware_node_id,
      interface_id,
      message_id,
    });
    return { count: result.count, items: result.items };
  },
});

const proposeEngineeringObject = tool({
  description:
    "Schlage ein neues Engineering-Objekt vor und lege es im Status 'draft' mit " +
    "source='ai_generated' und review_state='unreviewed' an, sodass ein Mensch es " +
    "später prüfen muss. Nutze dies statt Nutzer zu bitten, es selbst einzugeben.",
  inputSchema: z.object({
    resource: z.enum(RESOURCE_ENUM),
    name: z.string(),
    description: z.string().optional(),
    domain: z.string().optional(),
    device_type: z
      .string()
      .optional()
      .describe("Nur für 'hardware-nodes', z. B. 'ECU', 'PLC', 'Gateway'."),
    interface_type: z
      .string()
      .optional()
      .describe("Nur für 'interfaces', z. B. 'CAN', 'Ethernet', 'ModbusTCP'."),
    hardware_node_id: z.string().optional().describe("Für 'functions'/'interfaces': zugehöriger HardwareNode."),
    interface_id: z.string().optional().describe("Für 'messages': zugehöriges Interface."),
    message_id: z.string().optional().describe("Für 'signals': zugehörige Message."),
    direction: z.enum(["rx", "tx", "bidirectional"]).optional().describe("Nur für 'messages'."),
  }),
  execute: async (input) => {
    const { resource, ...rest } = input;
    const payload: Record<string, unknown> = {
      name: rest.name,
      description: rest.description ?? null,
      domain: rest.domain ?? null,
      source: "ai_generated",
      review_state: "unreviewed",
      approval_state: "pending",
      provenance: { agent: "engineering-chat-agent", reason: "user-requested proposal" },
    };
    if (resource === "hardware-nodes") payload.device_type = rest.device_type ?? "GenericDevice";
    if (resource === "interfaces") {
      payload.interface_type = rest.interface_type ?? "Other";
      payload.hardware_node_id = rest.hardware_node_id ?? null;
    }
    if (resource === "functions") payload.hardware_node_id = rest.hardware_node_id ?? null;
    if (resource === "messages") {
      payload.interface_id = rest.interface_id ?? null;
      payload.direction = rest.direction ?? "tx";
    }
    if (resource === "signals") payload.message_id = rest.message_id ?? null;

    const created = await createObject(resource, payload);
    return {
      created: true,
      resource,
      object: created,
      note: "Objekt wurde als Entwurf (draft, unreviewed) angelegt und muss noch geprüft werden.",
    };
  },
});

const listEngineeringRelationsTool = tool({
  description: "Liste Relations (Kanten des Knowledge Graphs) für ein Engineering-Objekt oder nach Typ.",
  inputSchema: z.object({
    object_type: z.enum(OBJECT_TYPE_ENUM).optional(),
    object_id: z.string().optional(),
    relation_type: z.string().optional(),
  }),
  execute: async ({ object_type, object_id, relation_type }) => {
    const result = await listRelations({ object_type, object_id, relation_type });
    return { count: result.count, items: result.items };
  },
});

const proposeEngineeringRelation = tool({
  description:
    "Schlage eine neue Relation zwischen zwei Engineering-Objekten vor (z. B. " +
    "HardwareNode HAS_INTERFACE Interface, oder Message CONTAINS_SIGNAL Signal).",
  inputSchema: z.object({
    source_type: z.enum(OBJECT_TYPE_ENUM),
    source_id: z.string(),
    target_type: z.enum(OBJECT_TYPE_ENUM),
    target_id: z.string(),
    relation_type: z.string().describe("z. B. HAS_INTERFACE, CONNECTED_TO, CONTAINS_SIGNAL, COMMUNICATES_WITH."),
  }),
  execute: async (input) => {
    const created = await createRelation(input);
    return { created: true, relation: created };
  },
});

export const engineeringAgent = new ToolLoopAgent({
  model: "anthropic/claude-sonnet-5",
  instructions: `Du bist der Network-Engineering-Assistent des Communication Simulators.

Du hilfst dabei, das kanonische Engineering-Modell zu verstehen und zu erweitern:
HardwareNode (Geräte wie ECU, PLC, Gateway), Function (Funktionen auf einem
Gerät), Interface (Kommunikationsschnittstelle wie CAN, Ethernet), Message
(Nachricht auf einem Interface) und Signal (Feld innerhalb einer Message).
Relations verbinden diese Objekte zu einem Knowledge Graph (z. B.
HAS_INTERFACE, CONTAINS_SIGNAL, COMMUNICATES_WITH).

Regeln:
- Nutze die Lese-Tools, um bestehende Objekte zu recherchieren, bevor du neue vorschlägst.
- Wenn der Nutzer ein neues Objekt oder eine neue Relation möchte, nutze die
  "propose"-Tools. Sie legen Objekte IMMER als Entwurf an (lifecycle 'draft',
  review_state 'unreviewed') - das ist beabsichtigt, ein Mensch muss sie
  später im Engineering-Tab prüfen und freigeben.
- Antworte auf Deutsch, präzise und technisch korrekt.
- Wenn Angaben fehlen (z. B. UUIDs für Relations), frage danach oder nutze die
  Such-Tools, um sie zu finden, statt sie zu erfinden.
- Erkläre kurz, was du getan hast, nachdem ein Tool ausgeführt wurde.`,
  tools: {
    listEngineeringObjects,
    proposeEngineeringObject,
    listEngineeringRelations: listEngineeringRelationsTool,
    proposeEngineeringRelation,
  },
  stopWhen: isStepCount(8),
});

export type EngineeringAgentUIMessage = InferAgentUIMessage<typeof engineeringAgent>;
