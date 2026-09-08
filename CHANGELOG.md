# Changelog

## 0.2.0

- Day end sends the current odometer input and resolved destination from a
  configurable HA sensor (default: `sensor.nx_01_position_gps_location`).
- Fuel supports optional liters, price per liter, total price and a full-tank
  toggle. Unset values are omitted; explicit zero values are preserved.
- Fuel drafts clear after confirmed saves and remain intact on failures.
- Added a reset-draft button and dashboard form; updated openHASP button bindings.

## 0.1.1

- Use the documented `X-API-Key` authentication header. This fixes HTTP 401
  on deployments where Apache or a proxy does not forward `Authorization`
  to PHP, even though the API key and source IP are valid.
- Verified maintenance and logbook reads against a live TravelLog instance.

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
