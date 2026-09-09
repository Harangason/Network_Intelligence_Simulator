# Erneute Freigabe nach Korrektur

Build: `8b58750d4cd3`, lokal auf Port 13500 bereitgestellt.

Die Validierung setzte den Routenstatus auf CONFLICT bzw. READY_FOR_REVIEW, ließ jedoch eine frühere approval_state=APPROVED samt Freigabedatum bestehen. Der Detailknopf wertete ausschließlich dieses alte Kennzeichen aus und sperrte damit eine erneute Freigabe.

Eine erneute Validierung setzt die aktuelle Freigabe jetzt auf PENDING und entfernt Datum und Bearbeiter der alten Freigabe aus dem aktuellen Zustand. Die Historie bleibt im Audit erhalten. Der Detailknopf berücksichtigt zusätzlich aktuellen Status und gültige Validierung. Historische, abgelehnte oder veraltete Revisionen können nicht über die Freigabe-API wieder freigegeben werden.

Bedienung: Befehlssignale ergänzen, betroffene Route validieren, anschließend freigeben. Eine unvollständige Nachricht bleibt gesperrt.

Prüfung:

- 35 Routing-Tests bestanden; Produktionsbuild inklusive TypeScript erfolgreich.
- `scripts/verify-route-reapproval.py`: echte Datenbanktransaktion, fehlendes Signal verhindert Freigabe, temporäre Signaldefinition ermöglicht Validierung und Freigabe. Alle Teständerungen zurückgerollt.
- `scripts/verify-route-reapproval-browser.mjs`: Browserknopf bei Konflikt gesperrt; bei simulierter erfolgreicher Validierung auch mit altem APPROVED-Kennzeichen verfügbar. Dieser UI-Test verändert keine Modelldaten.

Die 100 fachlich unvollständigen Befehlsrouten werden durch diese technische Korrektur nicht automatisch freigegeben.
