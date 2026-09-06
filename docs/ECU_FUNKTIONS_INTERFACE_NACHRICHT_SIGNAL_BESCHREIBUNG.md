# ECU → Funktion → Logisches Interface → Nachricht → Signal
## Beschreibung der Zielstruktur für den Simulator

## 1. Ziel

Dieses Dokument beschreibt die gewünschte **kanonische Beispielstruktur** für den Simulator.

Die Struktur soll **industrieneutral** sein, aber **CAN-FD als verständliches Beispiel** verwenden.

Ziel ist eine eindeutige, visuell und fachlich klare Darstellung des folgenden Aufbaus:

```text
ECU
→ Funktion
→ Logisches Interface
→ Nachricht
→ Signal
```

---

## 2. Grundaufbau

Der **äußerste Rahmen** stellt eine:

```text
ECU
```

dar.

Innerhalb der ECU befinden sich:

```text
mindestens 2 Funktionen
```

Wichtig ist dabei:

```text
eine ECU enthält mindestens eine Funktion
```

Die Darstellung soll aber im Beispiel **mindestens zwei Funktionen** zeigen, damit die Struktur eindeutig sichtbar wird.

---

## 3. Aufbau innerhalb einer Funktion

Jede Funktion enthält einen eigenen Rahmen für das:

```text
logische Interface
```

Dieses logische Interface beschreibt die **fachliche/logische Kommunikationssicht** der Funktion.

Es ist **kein physisches Hardware-Interface**, sondern die logische Ebene, über die die Funktion ihre Daten strukturiert bereitstellt.

---

## 4. Aufbau innerhalb des logischen Interfaces

Ein logisches Interface enthält:

```text
mindestens eine Nachricht
```

Die Nachricht soll im Beispiel als:

```text
Beispiel CAN-FD
```

gekennzeichnet werden.

Wichtig ist die fachliche Regel:

```text
Eine Nachricht darf maximal die zulässige Nutzlastgröße verwenden.
```

Im Beispiel CAN-FD bedeutet dies:

```text
maximal 64 Byte pro Nachricht
```

---

## 5. Aufbau innerhalb der Nachricht

Innerhalb jeder Nachricht befinden sich:

```text
Signale
```

Diese Signale werden so lange in die Nachricht eingefügt, bis die zulässige Größe der Nachricht erreicht ist.

Beispiel:

```text
Nachricht 1
├── Signal A
├── Signal B
├── Signal C
└── Signal D
```

Wenn die Nachricht dadurch ihre maximale Nutzlast erreicht, gilt:

```text
64/64 Byte
(voll genutzt)
```

---

## 6. Regel bei Überschreitung des Limits

Wenn weitere Signale hinzugefügt werden sollen, das definierte Nachrichtenlimit aber bereits erreicht ist, dann muss:

```text
eine neue Nachricht angelegt werden
```

Beispiel:

```text
Nachricht 1
→ Limit erreicht

weitere Signale vorhanden
→ neue Nachricht öffnen

Nachricht 2
├── Signal E
└── Signal F
```

Beispielhafte Anzeige:

```text
18/64 Byte
(teilweise genutzt)
```

Damit gilt die zentrale Packing-Regel:

```text
Signale werden in Nachrichten gepackt.
Wenn die Nachricht voll ist, wird mit einer neuen Nachricht fortgesetzt.
```

---

## 7. Beispielhafte Hierarchie

Die fachliche Hierarchie lautet:

```text
ECU
→ Funktionen
→ Logische Interfaces
→ Nachrichten
→ Signale
```

Diese Reihenfolge ist im Bild explizit sichtbar zu machen.

---

## 8. Wichtige Modellregel

Die Grafik beschreibt die **logische Struktur innerhalb einer ECU**.

Sie soll verdeutlichen:

```text
ECU
enthält Funktionen

Funktionen
enthalten logische Interfaces

logische Interfaces
enthalten Nachrichten

Nachrichten
enthalten Signale
```

Zusätzlich soll klar sein:

```text
Nachrichten nutzen die verfügbare Nutzlast maximal aus.
Wird das Limit überschritten, beginnt eine neue Nachricht.
```

---

## 9. Bezug zu CAN-FD

Die Darstellung ist **industrieneutral**, verwendet aber CAN-FD als **konkretes Beispiel**.

Daher soll im Bild an den Nachrichten bzw. am logischen Interface erkennbar sein:

```text
Beispiel CAN-FD
max. 64 Byte pro Nachricht
```

Wichtig:

```text
64 Byte = Beispiel für die maximale Nutzlast einer CAN-FD-Nachricht
```

Die Grafik soll dabei nicht als vollständige Busspezifikation verstanden werden, sondern als **leicht verständliche Strukturvisualisierung für den Simulator**.

---

## 10. Aussage für den Simulator

Diese Darstellung ist wichtig für den Simulator, weil sie den gewünschten inneren Aufbau verdeutlicht.

Insbesondere soll sie bestätigen bzw. als Soll-Struktur vorgeben:

```text
eine ECU enthält mehrere Funktionen
jede Funktion besitzt mindestens ein logisches Interface
jedes logische Interface enthält Nachrichten
jede Nachricht enthält Signale
Signale werden bis zur maximalen Nachrichtenkapazität gepackt
bei Überschreitung wird eine neue Nachricht angelegt
```

---

## 11. Hinweis zur Umsetzung

Die Grafik ist als:

```text
fachliches Zielbild / Soll-Struktur
```

zu verstehen.

Sie zeigt den gewünschten Aufbau, bedeutet aber **nicht automatisch**, dass diese Logik bereits vollständig korrekt im Simulator umgesetzt ist.

Genau deshalb dient die Darstellung als:

```text
Referenzbild
+
Dokumentationsgrundlage
+
Kommunikationshilfe für die weitere Implementierung
```

---

## 12. Kurzfassung

```text
ECU
└── Funktion 1
    └── Logisches Interface
        ├── Nachricht 1
        │   ├── Signal A
        │   ├── Signal B
        │   ├── Signal C
        │   └── Signal D
        └── Nachricht 2
            ├── Signal E
            └── Signal F

ECU
└── Funktion 2
    └── Logisches Interface
        └── Nachricht 1
            ├── Signal X
            ├── Signal Y
            └── Signal Z
```

Packing-Regel:

```text
Signale füllen Nachrichten.
Nachrichten nutzen maximal die zulässige Nutzlast.
Wird das Limit überschritten, wird eine neue Nachricht angelegt.
```

---

## 13. Zugehöriges Bild

Die zugehörige Grafik wurde separat erstellt und zeigt genau diese Struktur als visuelle Infografik.
