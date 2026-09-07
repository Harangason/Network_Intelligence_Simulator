# Device-Class Addressability

Standardpolicy: Class 0 und 1 nicht adressierbar, Class 2 optional, Class 3 profilabhängig/optional, Class 4 automatisch adressierbar. Eine explizite Benutzer- oder Importentscheidung überschreibt den Klassenstandard und wird in `address_provenance.addressability_source` festgehalten.

Einfache Sensoren und Aktoren erhalten daher nicht unnötig eine Adresse; intelligente Subsysteme, Gateways, ECUs und PLCs werden über ihre Class-4-Klassifikation adressiert.
