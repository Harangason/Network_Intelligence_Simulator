# Topologie: Kommunikation, Filter und Zoom

Nutzeranforderung vom 11.09.2026: Die vollständige Kommunikation soll auch ohne
Suchfilter erkennbar sein, Datenflussanimationen zuverlässig weiterlaufen, Zoom
innerhalb der Ansicht bleiben und Filter beim Darstellungswechsel erhalten bleiben.

## Befund und Änderung

- `switchMode` rief bisher den vollständigen Reset auf. Hardware, Functions und
  Combined behalten nun Suche, Typ und Bus. Auch der Wechsel 2D/3D erhält diese
  Felder. Ein in einer Ansicht nicht vorhandener Knotentyp liefert weiterhin keine
  Treffer; er wird nicht stillschweigend durch einen anderen Typ ersetzt.
- Die Kommunikation stammt aus sämtlichen aktuellen Routen mit Nutzdaten und
  `COMMUNICATES_WITH`-Beziehungen. Es gab keinen Diagnosefilter. Der geprüfte
  Projektstand enthält 438 Routen und 426 zusammengefasste Hardware-Sender/
  Empfängerpaare. 56 davon betreffen Knoten mit Diagnose im Namen; 370 weitere
  enthalten unter anderem `Motorsteuerung → Kombiinstrument` (`RT-48BEDE64`).
  Diese Namensauswertung dient nur dieser Untersuchung, nicht der Datenmodellierung.
- Die einklappbare Liste „Kommunikationswege“ macht die sichtbaren Paare samt
  Beziehungen/Status auswählbar. Die Fußzeile zeigt sichtbare/gesamte Paare. Die
  Functions-Ansicht benötigt explizite Funktionszuordnungen und hat deshalb andere
  Zahlen als Hardware. Es werden keine Empfänger aus Namen geraten.
- Die Knotenauswahl hatte Animationen außerhalb direkt angeschlossener Wege
  entfernt; bei Strukturknoten verschwanden damit sämtliche bewegten Punkte.
  Auswahl hebt nun hervor, ohne die übrigen Flüsse abzuschalten. Gerichtete
  modellierte Kommunikation wird auch bei ausstehender Prüfung animiert. Orange
  bleibt die Kennzeichnung ungeprüfter/veralteter Wege. Ungerichtete Beziehungen
  und reine physische Busverbindungen erzeugen keine erfundene Senderichtung.
  Bewegung ist eine Illustration, kein Nachweis aktiver Übertragung oder gültigen
  Timings. Pausenschalter und Systemeinstellung für reduzierte Bewegung gelten weiter.
- Ein nicht passiver Wheel-Listener in der Capture-Phase der Zeichenfläche
  verarbeitet Zoom in beiden Dimensionen. Er erfasst auch 3D-Beschriftungen und
  verhindert Scrollen während einer Pointer-Geste; OrbitControls behält Drehen und
  Verschieben. Das Eigenschaftsfenster kann separat scrollen. Listener werden beim
  Wechsel entfernt. Die Kamera wird nur bei geänderter Knotenanordnung eingepasst,
  nicht durch Hervorhebungen, Layer-Schalter oder identische Datenaktualisierungen.

## Prüfung und lokaler Betrieb

Aktiver NIS-Build: `2b53ca8596f8`, Health `ok`.

- 13 Graph-Tests bestanden, einschließlich vollständiger Kommunikation gegenüber
  gefilterter Teilmenge, Senderichtung und Warnfarben bei ungeprüften Wegen.
- TypeScript-Prüfung und Docker-Produktionsbuild erfolgreich.
- Echter Chrome auf dem laufenden NIS: alle sechs Modus/Dimensionskombinationen,
  alle drei Filterfelder, CSS-Animation und 3D-Bildänderungen ohne Kamerabewegung,
  Auswahl eines Strukturknotens, Animationspause und Fortsetzen, Wheel-Zoom über
  Canvas und Labels sowie während Ziehen, Rückkehr nach Verlassen des Sichtbereichs,
  Erhalt des 2D-Zooms beim Layer-Wechsel und reduzierte Bewegung bestanden.
- Keine JavaScript-Seitenfehler. Topologie und Bearbeitungstoken vor/nach dem Test
  identisch. Nur die bestehende Navigation aktualisiert den aktiven Workflow-Schritt.

Reproduzierbar:

```powershell
cd frontend
node --experimental-strip-types --test src/lib/hardware-graph.test.mjs
node --experimental-strip-types scripts/verify-hardware-view-stability.mjs
```

Nachweise: `backend/runtime/hardware-view-stability.json`,
`hardware-view-stability-2d.png`, `hardware-view-stability-3d.png`,
`hardware-view-browser.log` und `hardware-view-build.log`.
