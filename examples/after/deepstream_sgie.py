# examples/after/deepstream_sgie.py
# Humanly rewrite — structure extracted, magic value named, sys.exit removed


def build_sgie_elements(cfg: PipelineConfig) -> list[Gst.Element]:
    """Instantiate one nvinfer SGIE element per active capability.

    Capabilities backed by Python workers are skipped here — they don't
    use a GStreamer inference element and are handled downstream.

    Args:
        cfg: Pipeline configuration with active capability list and interval.

    Returns:
        List of configured nvinfer Gst.Element instances, one per cap.
    """
    elements = []

    for cap in cfg.active_sgies():
        cfg_path = SGIE_CONFIGS.get(cap)

        if cfg_path is None:
            # Python-worker capability — no GStreamer element needed
            logger.info("Skipping SGIE for '%s': handled by Python worker", cap)
            continue

        sgie = _create_nvinfer_element(cap, cfg_path, cfg)
        elements.append(sgie)
        logger.info("SGIE loaded: %s → %s", cap, cfg_path)

    if not elements:
        logger.info("No SGIEs loaded — pipeline will run people_counting only")

    return elements


def _create_nvinfer_element(
    cap: str,
    cfg_path: str,
    cfg: PipelineConfig,
) -> Gst.Element:
    """Create and configure a single nvinfer GStreamer element.

    Args:
        cap: Capability name, used to label the element.
        cfg_path: Path to the nvinfer config file for this capability.
        cfg: Pipeline config, used to apply the inference interval if set.

    Returns:
        A configured Gst.Element ready to be added to the pipeline.

    Raises:
        RuntimeError: If GStreamer cannot create the nvinfer element.
    """
    sgie = Gst.ElementFactory.make("nvinfer", f"sgie-{cap}")
    if not sgie:
        raise RuntimeError(
            f"GStreamer failed to create nvinfer element for capability '{cap}'. "
            "Check that the gst-nvinfer plugin is installed and accessible."
        )

    sgie.set_property("config-file-path", cfg_path)

    if cfg.sgie_interval_is_enabled():
        # Interval controls how many frames are skipped between inferences.
        # Set by the client config — lower = more accurate, higher = cheaper.
        sgie.set_property("interval", cfg.sgie_interval)

    return sgie
