# Technology Address Bindings

`engineering_technology_address_bindings` trennt die logische Identität von technologiespezifischen Adressen wie CAN-Identifiern, IP-/MAC-Adressen, LIN-NADs oder Feldbusadressen. Ein optional referenziertes Hardware Interface muss zum HardwareNode gehören.

Die REST-Ressource `/api/engineering/addressing/technology-bindings` listet und erzeugt Bindings. Bei einer logischen Adressänderung werden betroffene Bindings `OUTDATED` und müssen bewusst neu bestätigt oder erzeugt werden.
