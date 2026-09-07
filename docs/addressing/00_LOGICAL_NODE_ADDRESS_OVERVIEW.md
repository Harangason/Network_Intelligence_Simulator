# Logical Node Address – Überblick

Die Logical Node Address ist die technologieunabhängige 16-Bit-Identität eines diagnostisch adressierbaren `HardwareNode`. Der gültige Vergabebereich ist `0x0001` bis `0xFFFE`; `0x0000` bedeutet nicht zugewiesen/ungültig und `0xFFFF` ist reserviert. Darstellung und Exporte verwenden stets vier große Hex-Ziffern.

Auflösung: Logical Address → Hardware Node → Hardware Interfaces → Networks → Technology Bindings → Routes → Simulation/Trace. Objekt-Referenzen bleiben die kanonische Relation; die Adresse ergänzt sie als reproduzierbare Identität.
