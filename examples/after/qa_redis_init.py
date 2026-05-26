"""
QA mode Redis initialization block from app.py (main()).

After constructing the GStreamer pipeline in QA mode, this block publishes the
full client configuration to Redis so the Streamlit dashboard (streamlit_app.py)
can display it. It also initializes live-editable config keys, taking care not
to overwrite values the operator may have changed while the pipeline was running.
"""
# examples/after/qa_redis_init.py
# Humanly rewrite — payload extracted to builder, aliased re-import removed,
# repeated set-if-not-exists pattern collapsed to a loop, Spanish comments translated.

import json
import os
import time

# Module-level globals (from the real app.py)
_IS_QA_ENABLED = True
_redis_qa       = None   # redis.Redis | None — set at module level when QA active
cfg             = None   # ClientConfig — loaded via load_config()
tiler_cols      = 2
tiler_rows      = 2


def _build_qa_status_payload(cfg, tiler_cols: int, tiler_rows: int) -> dict:
    """Build the status dict published to app:qa:status in Redis.

    Read by the Streamlit dashboard on load to display current pipeline state.
    Extracted because the shape is large enough to obscure the surrounding logic inline.
    """
    return {
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
    }


def _init_redis_qa_state() -> None:
    """Initialize QA Redis keys after the pipeline is built."""
    if not _redis_qa:
        return

    _redis_qa.set("app:qa:status", json.dumps(
        _build_qa_status_payload(cfg, tiler_cols, tiler_rows)
    ))

    # New startup — clear stale editor overrides and bump config generation so
    # the Streamlit dashboard detects the restart and resets its session_state.
    _redis_qa.delete("app:qa:config_overrides")
    _redis_qa.set("app:qa:config_gen", str(time.time()))

    # Write session defaults only if the key doesn't exist yet — preserves any
    # live QA overrides made through the dashboard editor between restarts.
    defaults = {
        "app:qa:entry_exit":        json.dumps(cfg.entry_exit_channels),
        "app:qa:external_channels": json.dumps(cfg.external_channels),
        "app:qa:count_internal":    "1" if cfg.count_internal else "0",
        "app:qa:count_external":    "1" if cfg.count_external else "0",
    }
    for key, value in defaults.items():
        if not _redis_qa.exists(key):
            _redis_qa.set(key, value)
