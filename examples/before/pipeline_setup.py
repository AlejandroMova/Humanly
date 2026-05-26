# examples/before/pipeline_setup.py
# Original — mixed Spanish/English, mid-function imports, flat structure,
# magic numbers, repeated QA flag checks, large inline dict.

  # ── Tracker ───────────────────────────────────────────────────────────────
    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    tracker.set_property("tracker-width",  320)
    tracker.set_property("tracker-height", 192)
    tracker.set_property("gpu-id",         0)
    tracker.set_property("ll-lib-file",
        "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so")
    tracker.set_property("ll-config-file", cfg.tracker_config_path())
    tracker.set_property("display-tracking-id", 1)

    # ── SGIEs — one per active capability beyond people_counting ──────────────
    sgie_elements = []
    for cap in cfg.active_sgies():
        cfg_path = SGIE_CONFIGS.get(cap)
        if cfg_path is None:
            logger.info("Capability '%s' uses Python worker — skipping SGIE", cap)
            continue
        sgie = Gst.ElementFactory.make("nvinfer", f"sgie-{cap}")
        if not sgie:
            logger.error("Could not create nvinfer element for capability '%s'", cap)
            sys.exit(1)
        sgie.set_property("config-file-path", cfg_path)
        if cfg.sgie_interval >= 0:
            sgie.set_property("interval", cfg.sgie_interval)
        sgie_elements.append(sgie)
        logger.info("SGIE loaded: %s → %s", cap, cfg_path)

    if not sgie_elements:
        logger.info("No SGIEs loaded — running people_counting only")

    # ── Tiler — solo en QA mode para compositar el video preview ─────────────
    # En producción el probe recibe frames full-res por cámara directamente.
    tiler_cols = math.ceil(math.sqrt(n_streams))
    tiler_rows = math.ceil(n_streams / tiler_cols)
    tiler = None
    if _IS_QA_ENABLED:
        tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
        tiler.set_property("rows",    tiler_rows)
        tiler.set_property("columns", tiler_cols)
        tiler.set_property("width",   640)
        tiler.set_property("height",  360)

    # ── RecordingManager — activo cuando recording_enabled=true en config.yaml ─
    # En QA mode siempre está activo (independiente del valor en config.yaml).
    # En producción solo si cfg.recording_enabled=true.
    _recording_manager = None
    if cfg.recording_enabled or _IS_QA_ENABLED:
        from recording_manager import RecordingManager
        _recording_manager = RecordingManager(
            recordings_dir="/nx_tech/recordings",
            redis_client=_redis_qa,   # None en producción sin QA; se ignora elegantemente
        )
        set_recording_manager(_recording_manager)
        _recording_manager.start()
        logger.info("[Recording] RecordingManager iniciado — /nx_tech/recordings/")

    # QA: informar grid al probe + arrancar MjpegServer
    if _IS_QA_ENABLED:
        cell_w = 640 // tiler_cols
        cell_h = 360 // tiler_rows
        init_qa_grid(tiler_cols, tiler_rows, cell_w, cell_h)

        from mjpeg_server import MjpegServer
        _mjpeg_srv = MjpegServer(
            tiled_frame_queue=tiled_frame_queue,
            camera_queues=camera_frame_queues,
            port=8080,
            recorder=_recording_manager,
        )
        _mjpeg_srv.start()
        logger.info("[QA] MjpegServer en :8080  /stream/all + /stream/<camera_id>")
        # Publicar status del Jetson a Redis para que Streamlit lo muestre
        if _redis_qa:
            _redis_qa.set("nx:qa:status", json.dumps({
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
            _redis_qa.delete("nx:qa:config_overrides")
            _redis_qa.set("nx:qa:config_gen", str(time.time()))
            # Inicializar nx:qa:entry_exit solo si no existe (preserva cambios QA en vivo)
            if not _redis_qa.exists("nx:qa:entry_exit"):
                import json as _json
                _redis_qa.set("nx:qa:entry_exit", _json.dumps(cfg.entry_exit_channels))
            # external_channels: igual que entry_exit, no sobreescribir si ya existe
            if not _redis_qa.exists("nx:qa:external_channels"):
                _redis_qa.set("nx:qa:external_channels", json.dumps(cfg.external_channels))
            # count_internal/count_external: igual que entry_exit, no sobreescribir si ya existe
            if not _redis_qa.exists("nx:qa:count_internal"):
                _redis_qa.set("nx:qa:count_internal", "1" if cfg.count_internal else "0")
            if not _redis_qa.exists("nx:qa:count_external"):
                _redis_qa.set("nx:qa:count_external", "1" if cfg.count_external else "0")
            init_pipeline_stats(cfg.channels)
