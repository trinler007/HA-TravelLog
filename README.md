# TravelLog für Home Assistant

HACS Custom Integration für die [TravelLog WebApp](https://github.com/trinler007/TravelLog).
Wartungen im Dashboard anzeigen und Bordbucheinträge direkt aus Home Assistant oder dem openHASP-Display im Fahrerhaus speichern.

## Funktionen

- Einrichtung über die Oberfläche mit WebApp-URL und API-Schlüssel.
- Kilometerstand aus TravelLog, Anzahl überfälliger, bald fälliger und noch nie erfasster Wartungen.
- Ein Sensor pro aktiver Wartungsaufgabe mit Status, letztem Termin, Kilometerstand, Ausführendem und Intervallen als Attribute. Neue Aufgaben erscheinen automatisch, entfernte Aufgaben werden nicht verfügbar.
- Die 25 vom API-Endpunkt gelieferten Bordbucheinträge als Attribute des Bordbuchsensors.
- KM-Eingabe als `number`-Entität; Buttons für Tagesabschluss und Tanken.
- Aktion `travellog.add_logbook_entry` mit allen dokumentierten optionalen API-Feldern und optionaler Antwort.
- openHASP-Beispiel mit Ziffernblock, Löschfunktion, Tagesabschluss, Tanken und Speicherrückmeldung.
- Gemeinsame Aktualisierung alle fünf Minuten und nach dem Speichern.

## Installation über HACS

Voraussetzungen: Home Assistant **2025.1 oder neuer**, HACS und eine TravelLog-Version mit den Endpunkten aus [docs/API.md](https://github.com/trinler007/TravelLog/blob/main/docs/API.md).

**Repository-Sichtbarkeit:** HACS unterstützt nur öffentliche GitHub-Repositories. Solange `trinler007/HA-TravelLog` privat ist, ist nur die manuelle Installation möglich. Ein privates Repository wird nicht durch einen zusätzlichen API-Schlüssel HACS-kompatibel.

Sobald dieses Repository öffentlich ist:

1. In HACS das Menü **Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/trinler007/HA-TravelLog` hinzufügen, Kategorie **Integration**.
3. **TravelLog** herunterladen und Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → TravelLog**.
5. Die URL der WebApp (z. B. `https://travel.example` oder `https://example.com/travel`) und den API-Schlüssel eingeben.

Der Schlüssel wird in TravelLog unter **Einstellungen → Allgemein & Dienste** erzeugt. Bei IP-Beschränkung muss die aus Sicht von TravelLog verwendete Quell-IP von Home Assistant freigegeben sein. HTTPS wird mit Zertifikatsprüfung verwendet; für eine lokale HTTP-Installation kann eine HTTP-URL eingegeben werden. Bei vorgeschalteten Weiterleitungen bitte die endgültige URL verwenden.

### Manuelle Installation

Den Ordner `custom_components/travellog` nach `/config/custom_components/travellog` kopieren, Home Assistant neu starten und die Integration wie oben hinzufügen. Zugangsdaten gehören ausschließlich in den Einrichtungsdialog. Kein `travellog:`-Block in `configuration.yaml` notwendig.

## Dashboard und Bedienung

Eine direkt verwendbare Kartenkonfiguration liegt in [examples/dashboard.yaml](examples/dashboard.yaml). Die dort genannten Entitäts-IDs entsprechen den Standardnamen einer einzelnen Instanz. Bei abweichenden Namen oder mehreren Instanzen die IDs anpassen.

| Entität | Bedeutung |
| --- | --- |
| `sensor.travellog_odometer` | In TravelLog gespeicherter Kilometerstand |
| `sensor.travellog_maintenance` | Anzahl aktiver Aufgaben; Attribut `tasks` |
| `sensor.travellog_maintenance_overdue` | Überfällige Aufgaben |
| `sensor.travellog_maintenance_soon` | Bald fällige Aufgaben |
| `sensor.travellog_maintenance_never_recorded` | Noch nie erfasste Aufgaben |
| Sensor je Wartungsaufgabe | `ok`, `soon`, `overdue`, `never` oder `neutral` |
| `sensor.travellog_logbook` | Anzahl gelieferter Einträge, höchstens 25; Attribut `entries` |
| `number.travellog_odometer_input` | Vorläufige KM-Eingabe, schreibt allein nichts in TravelLog |
| `button.travellog_day_end` / `button.travellog_fuel` | Speichern mit der KM-Eingabe |
| `sensor.travellog_write_status` | Status des letzten Speichervorgangs dieser HA-Sitzung |

Vor dem ersten Button-Druck nach einem Neustart muss der aktuelle Kilometerstand eingegeben werden. Die Integration übernimmt nicht automatisch den möglicherweise alten Serverwert. Die Eingabe bleibt während der Sitzung erhalten und ist vor jedem neuen Eintrag zu prüfen.

Speicherstatus: `idle`, `saving`, `saved`, `needs_review`, `error`, `uncertain`.
`needs_review` bedeutet **erfolgreich gespeichert**, aber in der WebApp zu ergänzen. Bei `uncertain` zuerst im TravelLog-Bordbuch nachsehen: Ein Verbindungsabbruch kann nach dem Speichern erfolgt sein. Schreibanfragen werden nicht automatisch wiederholt. Gleichartige Wiederholungen werden für 30 Sekunden abgefangen; dies ist keine serverseitige Idempotenzgarantie.

## Bordbuch-Aktion

Minimaler Tagesabschluss:

```yaml
action: travellog.add_logbook_entry
data:
  log_type: day_end
  odometer_km: 102607
response_variable: result
```

Tankvorgang:

```yaml
action: travellog.add_logbook_entry
data:
  log_type: fuel
  odometer_km: 102607
  liters: 131.2
  price_per_liter: 2.119
  is_full_tank: true
  country_code: DE
  vendor: Tanken
response_variable: result
```

Unterstützte Typen: `day_end`, `fuel`, `maintenance`, `repair`, `cost`, `odometer`. Pflichtfelder sind immer `log_type` und `odometer_km`. Optional sind `occurred_on`, `vendor`, `country_code`, `liters`, `price_per_liter`, `is_full_tank`, `amount`, `currency`, `performed_by`, `notes`. Ohne Datum gilt das heutige Datum auf dem TravelLog-Server.

Bei mehreren TravelLog-Instanzen ist außerdem `config_entry_id` erforderlich; im Aktionseditor lässt sie sich auswählen. Die Antwort enthält `id`, `needs_review` und die von TravelLog ergänzten Daten. Das Ereignis `travellog_logbook_created` enthält zusätzlich `entry_id`. Es wird nur nach einer bestätigten Speicherung ausgelöst.

## openHASP im Fahrerhaus

Die vollständige Anleitung steht in [examples/openhasp/README.md](examples/openhasp/README.md).
Das Beispiel nutzt die openHASP-Integration und ein **320 × 480**-Display im Hochformat. Die TravelLog-Integration selbst setzt openHASP nicht voraus.

## Grenzen der aktuellen TravelLog-API

- `/maintenance` liefert aktive Aufgaben mit der **letzten** Durchführung, keine vollständige Historie aller Wartungsdurchführungen.
- Der derzeitige Servercode liefert den berechneten Status und Intervalle, jedoch kein explizites nächstes Fälligkeitsdatum. Die Integration übernimmt die Serverbewertung unverändert.
- Ein Bordbucheintrag vom Typ `maintenance` ergänzt das Bordbuch, markiert aber keine Wartungsaufgabe als erledigt. Dafür fehlt ein API-Endpunkt für `maintenance_records`.
- `/logbook` sortiert aktuell primär nach Kilometerstand, dann Datum und ID. Der Sensor bezeichnet deshalb die gelieferten 25 Einträge nicht als chronologisch letzte 25.
- Ein minimaler Tankvorgang ohne Liter/Betrag wird gespeichert und muss in TravelLog nachbearbeitet werden. Ziele für Tagesabschlüsse ergänzt der Server nach Möglichkeit über GPSGate.
- Ohne erreichbaren TravelLog-Server werden keine Einträge offline zwischengespeichert.

Die Bordbuchattribute enthalten Notizen und können umfangreich sein. Wer keine zweite Historie in Home Assistant benötigt, kann die beiden Sammelsensoren im `recorder` ausschließen:

```yaml
recorder:
  exclude:
    entities:
      - sensor.travellog_logbook
      - sensor.travellog_maintenance
```

## Entwicklung und Prüfung

```sh
python -m venv .venv
# Virtuelle Umgebung aktivieren; vollständige HA-Tests unter Linux ausführen.
pip install homeassistant pytest pytest-asyncio ruff
ruff check .
ruff format --check .
python -m pytest -q
```

GitHub Actions prüft Home Assistant 2025.1.4 und die aktuell installierbare Version, HTTP-Verhalten, Schreibschutz gegen Doppelklicks, Konfigurationsdialog, Entitäten, Aktionen und Unload sowie `hassfest`. Ohne installiertes Home Assistant wird die HA-Testdatei explizit übersprungen; API- und Beispieldateitests laufen unabhängig davon. Ein Test mit der produktiven WebApp und dem physischen Display ist zusätzlich erforderlich.

Referenzen: [TravelLog API](https://github.com/trinler007/TravelLog/blob/main/docs/API.md), [HA Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/), [HACS-Anforderungen](https://www.hacs.xyz/docs/publish/start/), [openHASP-Anbindung](https://www.openhasp.com/0.7.0/integrations/home-assistant/howto/).
