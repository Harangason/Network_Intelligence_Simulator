# RAG Signal Generation Schema

## Zweck

Rohe Signallisten wie die eingefuegte Automotive-Liste sind wertvolle
Namens-Evidence, aber noch keine vollstaendigen Signaldefinitionen. Das Schema
`config/rag-signal-generation.schema.json` beschreibt deshalb RAG-Records, die
einen Generator fuehren koennen, ohne fehlende technische Fakten zu erfinden.
Die Trennung nach Branche erfolgt ueber `IndustryRAGOrchestrator` und
`rag_partition`.

## Bestehende Verwalter

Es gibt bereits mehrere Manager, aber mit unterschiedlichen Zustaendigkeiten:

- `IndustryKnowledgeService`: branchenspezifischer Lernspeicher und
  Knowledge-Graph fuer Simulationslaeufe.
- `TechnologyRegistry`: branchenspezifische Technologieprofile fuer Automotive,
  Industrial Automation, Embedded Systems, Aerospace, Rail, Marine,
  Building Automation, Energy, Robotics ROS und Generic Networking.
- `EngineeringWorkloadOrchestrator`: Workload-, Proposal-, Validierungs- und
  Repair-Orchestrierung.
- `IndustryRAGOrchestrator`: RAG-Routing fuer Signal-Generation-Evidence.

Damit ist RAG nicht hart an Automotive gebunden. Automotive ist nur ein Profil
unter mehreren.

## Industrie-Partitionen

Signal-RAG wird logisch in Partitionen getrennt:

```text
signal-generation:generic
signal-generation:automotive
signal-generation:industrial_automation
signal-generation:embedded_systems
signal-generation:aerospace
signal-generation:rail
signal-generation:marine
signal-generation:building_automation
signal-generation:energy
signal-generation:robotics_ros
signal-generation:generic_networking
```

Ein Generator darf die passende Industrie-Partition plus
`signal-generation:generic` als Fallback verwenden. Branchenspezifische Hinweise
stehen in `industry_tags`; neutrale Bedeutung steht in `semantic_tags`.

Wenn eine Quelle eine bekannte Branche hat, soll der Import `industry` explizit
setzen. Ohne explizite Branche versucht `IndustryRAGOrchestrator` eine
vorsichtige Erkennung aus Namensraeumen und Fachbegriffen; nicht erkannte
Signale landen in `signal-generation:generic`.

## Quelle `signal-list`

`SignalListSourceAdapter` liest eine Plain-Text-Liste mit einem Signalnamen pro
Zeile. Die Namen werden nur fluechtig fuer Klassifikation und Zaehlen
verwendet. Sie werden danach verworfen und nicht als einzelne `Signal`-Records
gestaged, indexiert oder persistiert.

Stattdessen entsteht pro erkannter Industrie-Partition ein
`SignalCorpusProfile`:

- `observed_signal_count`: Anzahl gueltiger, eindeutiger Signalnamen.
- `duplicate_count` und `rejected_count`: Importqualitaet ohne Rohdaten.
- `semantic_type_counts`: Verteilung von `NUMERIC`, `STATE`, `FLAG`,
  `COUNTER`, `STRING`, `BYTE_ARRAY` oder `UNKNOWN`.
- `semantic_tag_counts`: neutrale Retrieval-Tags wie `object_tracking`,
  `fault`, `status`, `counter`, `position`, `velocity`, `angle`, `identity`,
  `payload`, `temperature`, `pressure`, `voltage` oder `current`.
- `industry_tag_counts`: Profilhinweise wie `lane_assistance`,
  `object_perception`, `ros_topic`, `avionics`, `fieldbus`, `hvac`,
  `battery`, `train_control` oder `navigation`.
- `namespace_pattern_counts`: verdichtete Namensraum-Muster wie
  `BV_Obj_<n>` statt konkreter Signalnamen.
- `rag_partition`: Zielpartition fuer getrenntes Retrieval.
- `raw_signal_names_persisted`: immer `false`.
- `quality.mapping_quality`: bei Signallisten immer `aggregate_profile`.

## Generator-Vertrag

Die Retrieval-Treffer duerfen dem Signal-Generator helfen bei:

- realistischen Namensraum-Mustern,
- semantischer Gruppierung,
- Auswahl passender Modelltypen fuer Status-, Positions-, Geschwindigkeits-,
  Winkel-, Zeit-, Qualitaets- und Identitaetssignale,
- Erkennen verwandter Signalgruppen fuer Message-Packing.

Der Generator muss weiterhin selbst oder aus staerkeren Quellen vervollstaendigen:

- konkrete Signalnamen,
- `message_id`,
- `start_bit`,
- `length_bits`,
- `byte_order`,
- `data_type`,
- `factor`,
- `offset_value`,
- `unit`,
- `min_value`,
- `max_value`,
- `data.allowed_values`,
- `data.enum_values`,
- konkrete `protocol_bindings`.

## Beispiel

```json
{
  "name": "automotive_signal_generation_profile",
  "display_name": "Automotive Signal Generation Profile",
  "domain": "automotive",
  "industry": "automotive",
  "description": "Aggregated signal-list profile for generation retrieval. Raw signal names are not persisted.",
  "profile_kind": "signal_generation_corpus",
  "generation_role": "corpus_profile",
  "rag_partition": "signal-generation:automotive",
  "observed_signal_count": 2446,
  "duplicate_count": 0,
  "rejected_count": 0,
  "raw_signal_names_persisted": false,
  "semantic_type_counts": {
    "NUMERIC": 720,
    "FLAG": 510,
    "STATE": 430,
    "BYTE_ARRAY": 80,
    "UNKNOWN": 706
  },
  "semantic_tag_counts": [
    { "value": "status", "count": 410 },
    { "value": "position", "count": 180 }
  ],
  "industry_tag_counts": [
    { "value": "object_perception", "count": 96 },
    { "value": "lane_assistance", "count": 44 }
  ],
  "namespace_pattern_counts": [
    { "value": "BV_Obj_<n>", "count": 39 },
    { "value": "BAP_LDW", "count": 24 }
  ],
  "retrieval_queries": [
    "signal-generation:automotive Automotive status position object_perception lane_assistance",
    "BV_Obj_<n> BAP_LDW"
  ],
  "generator_contract": {
    "may_use": [
      "industry partition",
      "semantic distribution",
      "namespace patterns",
      "tag distributions"
    ],
    "must_not_use": ["raw signal name lookup", "implicit approval"],
    "must_complete": [
      "signal names",
      "message assignment",
      "start bits",
      "bit lengths",
      "byte order",
      "value domains",
      "protocol bindings"
    ]
  },
  "quality": {
    "confidence": 0.42,
    "source_quality": 0.42,
    "semantic_complete": false,
    "value_domain_complete": false,
    "encoding_complete": false,
    "mapping_quality": "aggregate_profile",
    "assumptions": [
      "Only aggregate signal-list patterns are retained; individual names were discarded."
    ]
  },
  "metadata": {
    "domain": "automotive",
    "industry": "automotive",
    "knowledge_level": "L1_IMPORTED",
    "source_quality": 0.42,
    "rag_schema": "rag-signal-generation.v1",
    "rag_partition": "signal-generation:automotive",
    "raw_signal_names_persisted": false
  }
}
```

## Wichtig

RAG-Evidence ist keine Freigabe. Sie darf generierte Vorschlaege begruenden und
ranken, aber niemals `COMPLETED` oder `APPROVED` setzen.

Ebenso wichtig: eine eingefuegte Signalliste bleibt kein Suchkorpus aus
Einzelnamen. Sie ist nur ein fluechtiger Rohinput fuer aggregierte Profile.
