# Changelog

## 0.1.0

- Initial TravelLog integration with UI setup and API-key renewal.
- Maintenance task sensors, overdue/soon counts, odometer and logbook data.
- Logbook action with optional response data and all documented API fields.
- Temporary odometer input and quick buttons for day end and refueling.
- Serialized writes, rapid duplicate suppression and explicit uncertain-save status.
- Dashboard and openHASP 320 × 480 keypad examples, including save feedback.
- HACS metadata, TravelLog brand assets and automated HTTP/Home Assistant checks.

The TravelLog maintenance endpoint currently exposes only the most recent
completion for each task. A maintenance logbook entry does not complete a
maintenance task. Physical display and live-server acceptance testing are
installation-specific.
