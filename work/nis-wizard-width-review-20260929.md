# Wizard-Schritt 1: verfügbare Breite nutzen

Quelle: Browser-Markierung am Feldset „Projekt benennen“ im Projekt `20260929100838036-cd9c24c2`.

Die vier direkten Eingabebereiche Projektname, Projektbeschreibung, Weitere Hinweise und Datei-Upload waren durch `.agent-project-name-step > label { max-width: 720px; }` begrenzt, obwohl das Feldset breiter ist. In `frontend/src/app/globals.css` wurde die feste Begrenzung durch `width: 100%; max-width: none; min-width: 0` ersetzt. Andere Wizard-Schritte und Formulardaten wurden dafür nicht geändert.

Visuelle Prüfung im isolierten Stack `work/nis-wizard-correction-isolated/f19e524288a5/receipt.json`: Das aktuelle lokale Stylesheet wurde in die laufende isolierte Browseransicht eingeblendet. Bei 1589 × 1244 px Ansichtsgröße maß das Feldset 1226 px; alle vier Labels waren zuvor 720 px und danach jeweils 1226 px breit. Bei 640 × 900 px Ansichtsgröße waren Feldset und Labels jeweils 578 px breit. In beiden Größen trat kein horizontales Überlaufen der Seite auf.

Bildbelege: `work/nis-wizard-width-desktop-20260929.png` und `work/nis-wizard-width-narrow-20260929.png`. `git diff --check -- frontend/src/app/globals.css` war ohne Befund.

Grenze: Die Browserprüfung verwendete das geänderte Stylesheet über einem zuvor isoliert gebauten App-Abbild; für diese CSS-Änderung wurde noch kein neues Release-Abbild gebaut. Der bekannte, separat protokollierte ECU-Korrekturfehler aus `work/nis-wizard-correction-report-20260929.md` verhindert weiterhin einen Release-Gate-PASS. Die produktive Instanz auf Port 13500 enthält die Breitenänderung noch nicht.
