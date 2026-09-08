# Fahrerhaus-Display

## Einrichtung

1. TravelLog-Integration einrichten. MQTT und die zur Display-Firmware passende openHASP-Integration müssen bereits funktionieren.
2. `pages.jsonl` auf das Display laden. Das Beispiel belegt **Seite 1, IDs 1–6**, für 320 × 480 Pixel. Bestehende Belegung vorher prüfen und bei Bedarf Seitennummern sowohl in JSONL als auch YAML ändern.
3. `package.yaml` nach `/config/packages/travellog_display.yaml` kopieren. In `configuration.yaml` unter dem vorhandenen `homeassistant:`-Block `packages: !include_dir_named packages` ergänzen.
4. Im Paket `fahrerhaus` durch den in openHASP eingerichteten Plate-Namen ersetzen. Bestehende `openhasp`-Objekte für dasselbe Display zusammenführen, statt doppelte Definitionen anzulegen.
5. Die Entitäts-IDs `number.travellog_odometer_input`, `button.travellog_day_end`, `button.travellog_fuel` und `sensor.travellog_write_status` prüfen. Bei mehreren TravelLog-Instanzen alle Entitäten derselben Instanz auswählen.
6. Home-Assistant-Konfiguration prüfen und neu starten. Seite 1 am Display öffnen.

## Bedienung

KM über die Zifferntasten eingeben. `C` löscht alles, `<` die letzte Ziffer. Anschließend **Tagesabschluss** oder **Tanken** drücken. Das Beispiel verwendet ganze Kilometer; die Integration unterstützt auch Dezimalwerte über ihre Zahleneingabe oder Aktion.

Die Rückmeldung zeigt das API-Ergebnis. Nach bestätigter Speicherung wird das Eingabefeld geleert. Ein Tankvorgang mit lediglich Kilometerstand ist erfolgreich erfasst und wird zur Ergänzung von Litern und Kosten in TravelLog markiert.

Ab Version 0.2.0 ruft das Speicher-Script die Integrationsbuttons auf. Dadurch
verwendet der Tagesabschluss den in den TravelLog-Optionen ausgewählten Ortssensor
(Standard: `sensor.nx_01_position_gps_location`). Der Tankbutton übernimmt außerdem
die optionalen Tankangaben aus der HA-Dashboard-Karte. Das Display-Beispiel selbst
enthält weiterhin nur die KM-Tastatur. Ein bereits installiertes `package.yaml`
muss für diese Änderung manuell durch die neue Fassung ersetzt werden.

Bei einem Fehler bleibt die Eingabe stehen. Bei „Unklar“ zuerst im Web-Bordbuch nachsehen, bevor erneut gespeichert wird. Ein doppelter Tastendruck während eines laufenden Speichervorgangs wird durch `mode: single` verworfen. Der KM-Puffer startet nach jedem HA-Neustart leer.

Die Speicherrückmeldung gehört zum letzten Schreibvorgang, nicht zum noch nicht gespeicherten Eingabepuffer. Eine leere oder ungültige KM-Eingabe löst keine Anfrage aus. Der API-Schlüssel befindet sich nur in der HA-Konfiguration, niemals auf dem Display oder in MQTT-Nachrichten.

## Vor-Ort-Abnahme

- Einmal Ziffern, `C` und `<` prüfen. Pro Loslassen darf nur eine Ziffer erscheinen.
- Unter MQTT beobachten, dass die Tastenmatrix beim Ereignis `up` das Feld `text` mit der gedrückten Beschriftung sendet (openHASP 0.7). Falls die Firmware andere Ereignisse liefert, die Bindung entsprechend anpassen.
- Einen bewusst gewünschten Tagesabschluss speichern; Kilometerstand, Datum, Ziel und Rückmeldung im Bordbuch vergleichen.
- Einen gewünschten Tankvorgang speichern; Nachbearbeitungskennzeichnung prüfen.
- Doppelklick prüfen: nur ein Eintrag.
- Verbindung trennen: keine Erfolgsmeldung, Eingabe bleibt erhalten. Nach Wiederverbindung zuerst prüfen, ob der Eintrag bereits gespeichert wurde.

Die Beispiele sind auf die dokumentierten openHASP-Objekte abgestimmt. Display-Auflösung, Firmware, Plate-Name und reale Entitäts-IDs müssen zur jeweiligen Installation passen.
