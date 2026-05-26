# examples/after/sector_aware_api.py
# Humanly rewrite — Spanish docstrings translated to English, repeated ternary
# dict-key pattern extracted to _person_id_key(), no logic changes.

_JETSON_SECTOR: str = "comercio"  # set at runtime from config


def _person_id_key() -> str:
    """Return the event field name for the person identifier in the current sector.

    Hogar sector identifies residents by 'name'; all other sectors use 'employee_id'.
    """
    return "name" if _JETSON_SECTOR == "hogar" else "employee_id"


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

    def post_employee_seen(
        self,
        camera_id: str,
        employee_id: str,
        track_id: int,
        similarity: float,
        bbox: dict,
    ) -> None:
        """Emit employee_seen (or known_person_seen in hogar) when a known face is identified."""
        # Hogar sector uses 'known_person_seen' to reflect resident rather than employee context.
        evt = "known_person_seen" if _JETSON_SECTOR == "hogar" else "employee_seen"
        payload = self._base_event(evt, camera_id)
        payload.update({
            "track_id":       track_id,
            "bbox":           bbox,
            "similarity":     round(similarity, 3),
            _person_id_key(): employee_id,
        })
        self.enqueue("POST", "/api/events", payload)

    def post_employee_presence(
        self,
        camera_id: str,
        employee_id: str,
        track_id: int,
    ) -> None:
        """Emit employee_presence periodically for persons still on camera (heartbeat)."""
        payload = self._base_event("employee_presence", camera_id)
        payload.update({
            "track_id":       track_id,
            _person_id_key(): employee_id,
        })
        self.enqueue("POST", "/api/events", payload)

    def post_employee_exit(
        self,
        camera_id: str,
        employee_id: str,
        track_id: int,
        dwell_seconds: float,
    ) -> None:
        """Emit employee_exit (or known_person_exit in hogar) with time on camera."""
        # Hogar sector uses 'known_person_exit' to reflect resident rather than employee context.
        evt = "known_person_exit" if _JETSON_SECTOR == "hogar" else "employee_exit"
        payload = self._base_event(evt, camera_id)
        payload.update({
            "track_id":       track_id,
            "dwell_seconds":  round(dwell_seconds, 1),
            _person_id_key(): employee_id,
        })
        self.enqueue("POST", "/api/events", payload)
