# Address Allocator

`LogicalNodeAddressAllocator` ist die einzige Vergabestelle. Er inspiziert Belegungen, findet freie Werte, validiert, weist atomar zu, gibt frei, reserviert Werte und erkennt Konflikte. Ein projektspezifischer PostgreSQL Advisory Transaction Lock serialisiert parallele Vergaben; der Unique Index bleibt die letzte Sicherung.

KI und Frontend berechnen keine Eindeutigkeit. KI-Proposal-Adressen werden verworfen; nach dem kanonischen INSERT vergibt der Allocator eine AUTO-Adresse.
