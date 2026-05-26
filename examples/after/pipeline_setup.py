# examples/after/pipeline_setup.py
# Humanly rewrite — conservative extraction, English-only comments,
# named constants, no mid-function imports.

import json
import math
import os
import time

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from mjpeg_server import MjpegServer
from recording_manager import RecordingManager

# Tracker input size — minimum resolution for nvmultiobjecttracker at this model.
TRACKER_INPUT_WIDTH  = 320
TRACKER_INPUT_HEIGHT = 192
TRACKER_GPU_ID       = 0
TRACKER_LIB_PATH     = (
    "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
)

# Tiler output size — composited preview for QA dashboard (not used in production).
TILER_OUTPUT_WIDTH  = 640
TILER_OUTPUT_HEIGHT = 360

QA_MJPEG_PORT    = 8080
RECORDINGS_DIR   = "/nx_tech/recordings"


def _build_tracker(cfg: PipelineConfig) -> Gst.Element:
    """Create and configure the nvtracker element.

    Tracker input is downscaled to save GPU memory — full-res frames
    are handled by the probe directly, not the tracker.

    Raises:
        RuntimeError: If GStreamer cannot create the nvtracker element.
    """
    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        raise RuntimeError("Failed to create nvtracker — check gst-nvtracker plugin.")

    tracker.set_property("tracker-width", TRACKER_INPUT_WIDTH)
    tracker.set_property("tracker-height", TRACKER_INPUT_HEIGHT)
    tracker.set_property("gpu-id", TRACKER_GPU_ID)
    tracker.set_property("ll-lib-file", TRACKER_LIB_PATH)
    tracker.set_property("ll-config-file", cfg.tracker_config_path())
    tracker.set_property("display-tracking-id", 1)
    return tracker


def build_sgie_elements(cfg: PipelineConfig) -> list[Gst.Element]:
    """Instantiate one nvinfer SGIE element per active capability.

    Capabilities backed by Python workers are skipped — they don't use
    a GStreamer inference element and are handled downstream by probes.

    Raises:
        RuntimeError: If GStreamer cannot create an nvinfer element.
    """
    elements = []

    for cap in cfg.active_sgies():
        config_path = SGIE_CONFIGS.get(cap)

        if config_path is None:
            # Python-worker capability — no GStreamer element needed.
            logger.info("Skipping SGIE for '%s': handled by Python worker", cap)
            continue

        sgie = Gst.ElementFactory.make("nvinfer", f"sgie-{cap}")
        if not sgie:
            raise RuntimeError(
                f"Failed to create nvinfer element for capability '{cap}'. "
                "Check that the gst-nvinfer plugin is installed."
            )

        sgie.set_property("config-file-path", config_path)

        if cfg.sgie_interval_is_enabled():
            # Interval = frames skipped between inferences.
            # Lower = more accurate, higher = cheaper. Set per client in config.yaml.
            sgie.set_property("interval", cfg.sgie_interval)

        elements.append(sgie)
        logger.info("SGIE loaded: %s → %s", cap, config_path)

    if not elements:
        logger.info("No SGIEs loaded — pipeline will run people_counting only")

    return elements


def _build_tiler(n_streams: int) -> tuple[Gst.Element, int, int]:
    """Create an nvmultistreamtiler sized to fit all streams.

    Grid dimensions are derived from stream count to keep cells roughly square.

    Returns:
        Tuple of (tiler element, cols, rows).

    Raises:
        RuntimeError: If GStreamer cannot create the tiler element.
    """
    cols = math.ceil(math.sqrt(n_streams))
    rows = math.ceil(n_streams / cols)

    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        raise RuntimeError("Failed to create nvmultistreamtiler element.")

    tiler.set_property("rows", rows)
    tiler.set_property("columns", cols)
    tiler.set_property("width", TILER_OUTPUT_WIDTH)
    tiler.set_property("height", TILER_OUTPUT_HEIGHT)
    return tiler, cols, rows


def _build_qa_status_payload(
    cfg: PipelineConfig,
    tiler_cols: int,
    tiler_rows: int,
) -> dict:
    """Build the status dict published to nx:qa:status in Redis.

    Read by the Streamlit dashboard on load to display current pipeline state.
    Extracted from the setup flow because the shape is large enough to obscure
    the surrounding logic when inline.
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


# ── Main pipeline setup ───────────────────────────────────────────────────────

def setup_pipeline_elements(cfg: PipelineConfig, n_streams: int) -> PipelineElements:
    """Build and wire all GStreamer + service elements for the pipeline.

    Handles both production and QA mode. In QA mode, additional services
    (tiler, MJPEG server, Redis state) are started to power the dashboard.

    Args:
        cfg: Client pipeline configuration.
        n_streams: Number of active camera streams.

    Returns:
        PipelineElements with all constructed elements and service handles.
    """
    tracker      = _build_tracker(cfg)
    sgie_elements = build_sgie_elements(cfg)

    # Tiler is only used in QA mode to composite a preview for the dashboard.
    # In production the probe receives full-res frames per camera directly.
    tiler, tiler_cols, tiler_rows = None, 0, 0
    if _IS_QA_ENABLED:
        tiler, tiler_cols, tiler_rows = _build_tiler(n_streams)

    # Recording is always active in QA; in production only if explicitly enabled.
    recording_manager = None
    if cfg.recording_enabled or _IS_QA_ENABLED:
        recording_manager = RecordingManager(
            recordings_dir=RECORDINGS_DIR,
            redis_client=_redis_qa,
        )
        set_recording_manager(recording_manager)
        recording_manager.start()
        logger.info("RecordingManager started — writing to %s", RECORDINGS_DIR)

    # QA services: live preview dashboard, MJPEG streams, Redis pipeline state.
    mjpeg_server = None
    if _IS_QA_ENABLED:
        cell_w = TILER_OUTPUT_WIDTH  // tiler_cols
        cell_h = TILER_OUTPUT_HEIGHT // tiler_rows
        init_qa_grid(tiler_cols, tiler_rows, cell_w, cell_h)

        mjpeg_server = MjpegServer(
            tiled_frame_queue=tiled_frame_queue,
            camera_queues=camera_frame_queues,
            port=QA_MJPEG_PORT,
            recorder=recording_manager,
        )
        mjpeg_server.start()
        logger.info(
            "MjpegServer started on :%d — /stream/all and /stream/<camera_id>",
            QA_MJPEG_PORT,
        )

        if _redis_qa:
            _redis_qa.set("nx:qa:status", json.dumps(
                _build_qa_status_payload(cfg, tiler_cols, tiler_rows)
            ))

            # New startup — clear stale editor overrides and bump config generation
            # so the Streamlit dashboard detects the restart and resets session_state.
            _redis_qa.delete("nx:qa:config_overrides")
            _redis_qa.set("nx:qa:config_gen", str(time.time()))

            # Write per-session defaults only if the key doesn't exist yet —
            # preserves any live QA overrides made through the dashboard editor.
            defaults = {
                "nx:qa:entry_exit":        json.dumps(cfg.entry_exit_channels),
                "nx:qa:external_channels": json.dumps(cfg.external_channels),
                "nx:qa:count_internal":    "1" if cfg.count_internal else "0",
                "nx:qa:count_external":    "1" if cfg.count_external else "0",
            }
            for key, value in defaults.items():
                if not _redis_qa.exists(key):
                    _redis_qa.set(key, value)

            init_pipeline_stats(cfg.channels)

    return PipelineElements(
        tracker=tracker,
        sgies=sgie_elements,
        tiler=tiler,
        recording_manager=recording_manager,
        mjpeg_server=mjpeg_server,
    )
