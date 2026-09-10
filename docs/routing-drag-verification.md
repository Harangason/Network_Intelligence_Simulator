# Routing-Navigation mit der Maus

Stand: 10.09.2026, Build `06da19a5cf6d`, Projekt `20260910042736034-d11591d0`.

Die Routing-Tabelle, alle drei Matrixebenen und die TX/RX-Tabelle verwenden denselben Scrollbereich. Linke Maustaste halten und ziehen verschiebt den Inhalt ab 6 Pixel Bewegung. Eingabefelder und Aktionsschaltflächen behalten ihre Bedienung. Matrixkacheln unterstützen sowohl Ziehen als auch Klicken. Pointer-Capture beginnt erst nach Überschreiten der Schwelle; ein anschließender Klick wird unterdrückt. Die Bewegung aktualisiert nur die Scrollposition, ohne die Matrix neu zu rendern.

## Prüfung im laufenden Browser

- Routing-Tabelle diagonal gezogen: Scrollposition von `(0, 0)` auf `(460, 190)`, anschließend zurück. Ausgewählte Route blieb `RT-FF5ECDF0`; kein Dialog wurde geöffnet.
- Nach Loslassen keine verbleibende Ziehen-Klasse.
- Filter „Abgasnachbehandlung“: 12 passende Routen. Checkbox aktivieren/deaktivieren und einfacher Routenklick funktionierten getrennt.
- ECU-Matrix: Ziehen über Kacheln verschob die Ansicht um `(350, 130)`, ohne einen Dialog zu öffnen. Anschließender einfacher Klick auf „Anlegen“ öffnete „Route anlegen“; ohne Speichern abgebrochen.
- Funktions- und Interface-Matrix: horizontales und vertikales Ziehen geprüft, ohne Dialogöffnung.
- TX/RX: Empfängerfilter und Auswahl geprüft. Die gezeigten zwei Zeilen passten vollständig in den Scrollbereich; in dieser Darstellung war kein Scrollen erforderlich.
- Paginierung von Seite 1 auf 2 und zurück erfolgreich. Abschließend Table, Seite 1, ohne Filter, Scrollposition `(0, 0)` und ursprüngliche Route wiederhergestellt.
- Browser-Fehlerprotokoll leer. Produktionsbuild einschließlich TypeScript erfolgreich.

Die vollständige Routing-API-Antwort vor und nach den Prüfungen ist identisch (386 Routen). SHA-256 des sortiert serialisierten JSON: `c6ad905a9332f98c9efab3e7f08a26565cda306fb7e2bbb0ae079b99ecec5e79`.
