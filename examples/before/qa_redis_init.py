"""
QA mode Redis initialization block from app.py (main()).

After constructing the GStreamer pipeline in QA mode, this block publishes the
full client configuration to Redis so the Streamlit dashboard (streamlit_app.py)
can display it. It also initializes live-editable config keys, taking care not
to overwrite values the operator may have changed while the pipeline was running.

New patterns to note:
  1. Large inline dict (30+ keys) built directly in a function body — no builder.
  2. Aliased re-import (`import json as _json`) inside a conditional block, even
     though `json` is already imported at the top of the file. The alias solves
     no naming conflict — it's pure noise that makes the reader wonder why.
  3. Repeated conditional comments all saying the same thing ("igual que entry_exit,
     no sobreescribir si ya existe") instead of a shared helper.
"""

import json
import os
import time

# These exist as module-level globals in the real app.py
_IS_QA_ENABLED = True
_redis_qa       = None   # redis.Redis | None — set at module level when QA active
cfg             = None   # ClientConfig — loaded via load_config()
tiler_cols      = 2
tiler_rows      = 2


def _init_redis_qa_state() -> None:
    """Initialize QA Redis keys after the pipeline is built."""

    if not _redis_qa:
        return

    _redis_qa.set("app:qa:status", json.dumps({
        "client":              cfg.client_name,
        "package":             cfg.package,
        "capabilities":        cfg.pipeline,
        "channels":            cfg.channels,
        "tracker":             cfg.tracker,
        "sector":              cfg.sector,
        "tiler_cols":          tiler_cols,
        "tiler_rows":          tiler_rows,
        "jetson_id":           os.environ.get("JETSON_ID", ""),
        "entry_exit_channels": cfg.entry_exit_channels,
        "external_channels":   cfg.external_channels,
        "count_internal":      cfg.count_internal,
        "count_external":      cfg.count_external,
        "stream_width":        cfg.stream_width,
        "stream_height":       cfg.stream_height,
        "stream_type":         cfg.stream_type,
        "dvr_port":            cfg.dvr_port,
        "rtsp_url_pattern":    cfg.rtsp_url_pattern,
        "pgie_batch_size":     cfg.pgie_batch_size,
        "pgie_interval":       cfg.pgie_interval,
        "sgie_interval":       cfg.sgie_interval,
        "reid_gallery_size":   cfg.reid_gallery_size,
        "recording_enabled":   cfg.recording_enabled,
        "component_resolutions": {
            "source":           f"{cfg.stream_width}x{cfg.stream_height}",
            "probe_a_frame":    f"{cfg.stream_width}x{cfg.stream_height}",
            "probe_b_frame":    "640x360",
            "pgie_input":       "960x544",
            "age_gender_input": "224x224",
            "facedetect_input": "240x136",
            "movenet_input":    "192x192",
            "osnet_input":      "128x256",
        },
    }))
    # Nuevo arranque — borrar overrides viejos del config editor y publicar generación
    # para que el dashboard Streamlit detecte el reinicio y resetee su session_state.
    _redis_qa.delete("app:qa:config_overrides")
    _redis_qa.set("app:qa:config_gen", str(time.time()))
    # Inicializar app:qa:entry_exit solo si no existe (preserva cambios QA en vivo)
    if not _redis_qa.exists("app:qa:entry_exit"):
        import json as _json
        _redis_qa.set("app:qa:entry_exit", _json.dumps(cfg.entry_exit_channels))
    # external_channels: igual que entry_exit, no sobreescribir si ya existe
    if not _redis_qa.exists("app:qa:external_channels"):
        _redis_qa.set("app:qa:external_channels", json.dumps(cfg.external_channels))
    # count_internal/count_external: igual que entry_exit, no sobreescribir si ya existe
    if not _redis_qa.exists("app:qa:count_internal"):
        _redis_qa.set("app:qa:count_internal", "1" if cfg.count_internal else "0")
    if not _redis_qa.exists("app:qa:count_external"):
        _redis_qa.set("app:qa:count_external", "1" if cfg.count_external else "0")
