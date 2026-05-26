# examples/before/deepstream_sgie.py
# Raw AI-generated / unstructured version

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
