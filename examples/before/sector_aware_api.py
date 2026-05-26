"""
Sector-aware event methods from ApiClient.

The Jetson deploys in one of three sectors (comercio, industrial, hogar).
The sector changes both the event name and the field name used in the payload.
These three methods handle face-recognition lifecycle events for known persons.

New pattern to note: ternary expression used as a dict key.
"""

_JETSON_SECTOR: str = "comercio"  # set at runtime from config


class ApiClient:

    def _base_event(self, event_type: str, camera_id: str, severity: str = "info") -> dict:
        return {
            "event_id":  "...",
            "type":      event_type,
            "sector":    _JETSON_SECTOR,
            "camera_id": camera_id,
            "severity":  severity,
        }

    def enqueue(self, method: str, endpoint: str, payload: dict = None): ...

    def post_employee_seen(self, camera_id: str, employee_id: str, track_id: int,
                           similarity: float, bbox: dict) -> None:
        """Emite employee_seen (o known_person_seen en hogar) cuando se identifica un rostro conocido."""
        evt = "known_person_seen" if _JETSON_SECTOR == "hogar" else "employee_seen"
        payload = self._base_event(evt, camera_id)
        payload.update({
            "track_id": track_id,
            "bbox": bbox,
            "similarity": round(similarity, 3),
            "employee_id" if _JETSON_SECTOR != "hogar" else "name": employee_id,
        })
        self.enqueue("POST", "/api/events", payload)

    def post_employee_presence(self, camera_id: str, employee_id: str, track_id: int) -> None:
        """Emite employee_presence periódicamente para empleados que siguen en cámara (heartbeat)."""
        payload = self._base_event("employee_presence", camera_id)
        payload.update({"track_id": track_id,
                        "employee_id" if _JETSON_SECTOR != "hogar" else "name": employee_id})
        self.enqueue("POST", "/api/events", payload)

    def post_employee_exit(self, camera_id: str, employee_id: str,
                           track_id: int, dwell_seconds: float) -> None:
        """Emite employee_exit (o known_person_exit en hogar) con tiempo de permanencia del empleado."""
        evt = "known_person_exit" if _JETSON_SECTOR == "hogar" else "employee_exit"
        payload = self._base_event(evt, camera_id)
        payload.update({
            "track_id": track_id,
            "dwell_seconds": round(dwell_seconds, 1),
            "employee_id" if _JETSON_SECTOR != "hogar" else "name": employee_id,
        })
        self.enqueue("POST", "/api/events", payload)
