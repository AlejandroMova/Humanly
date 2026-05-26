"""
Lazy GPU→CPU frame copy decision in the GStreamer probe (pre_tiler_analytics_probe).

At every probe invocation, the pipeline must decide whether to copy the current
frame from GPU VRAM to CPU RAM. The copy is expensive (~2ms on Orin Nano) and
blocks the GStreamer thread, so it should only happen when at least one worker
actually needs pixel data for this frame.

That decision is expressed as a single predicate — _frame_needs_pixel_data() —
rather than a multi-step accumulator flag spread across the probe body.
"""
# Humanly rewrite — pixel-need decision extracted to named predicate,
# print() replaced with logging, Spanish text translated to English.

import logging

import cv2
import numpy as np
import pyds
from gi.repository import Gst

# (Globals abbreviated for clarity — these exist in the real probe module)
_recording_manager = None   # RecordingManager | None
_pose_worker        = None  # PoseWorker | None
_face_recognizer    = None  # FaceRecognizer | None
_appearance_worker  = None  # AppearanceWorker | None
_active_tracks      = {}    # Dict[(pad_index, track_id), _TrackState]

PGIE_CLASS_PERSON = 0

logger = logging.getLogger(__name__)


def _iter_pyds_list(pyds_list, cast_fn):
    node = pyds_list
    while node is not None:
        try:
            yield cast_fn(node.data)
        except StopIteration:
            return
        try:
            node = node.next
        except StopIteration:
            return


def _frame_needs_pixel_data(frame_meta, pad_index: int) -> bool:
    """Return True if any active worker needs pixel data for this frame.

    Copying from GPU VRAM to CPU RAM costs ~2ms on Orin Nano and blocks the
    GStreamer thread. This check ensures the copy only happens when at least
    one worker will actually consume the pixels.

    Recording always needs pixels when active. Pose and face workers need them
    whenever detections exist. Appearance/ReID only needs pixels when new tracks
    have arrived or existing tracks are still awaiting their first embedding —
    once all tracks have settled, the copy can be skipped.
    """
    if _recording_manager is not None and _recording_manager.is_recording:
        return True

    if frame_meta.num_obj_meta == 0:
        return False

    if _pose_worker is not None or _face_recognizer is not None:
        return True

    if _appearance_worker is not None:
        # Count only person tracks — bags and faces inflate num_obj_meta but
        # do not need appearance embeddings.
        n_persons = sum(
            1 for om in _iter_pyds_list(frame_meta.obj_meta_list, pyds.NvDsObjectMeta.cast)
            if int(om.class_id) == PGIE_CLASS_PERSON
        )
        n_known = sum(1 for k in _active_tracks if k[0] == pad_index)
        has_unsettled_tracks = any(
            not s.appearance_sent
            for k, s in _active_tracks.items() if k[0] == pad_index
        )
        return n_persons > n_known or has_unsettled_tracks

    return False


def pre_tiler_analytics_probe(_pad, info):
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        return Gst.PadProbeReturn.OK
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    if not batch_meta:
        return Gst.PadProbeReturn.OK

    for frame_meta in _iter_pyds_list(batch_meta.frame_meta_list, pyds.NvDsFrameMeta.cast):
        frame_num = frame_meta.frame_num
        pad_index = frame_meta.pad_index
        camera_id = f"cam-{pad_index}"

        frame_np = None
        if _frame_needs_pixel_data(frame_meta, pad_index):
            try:
                n_frame  = pyds.get_nvds_buf_surface(hash(gst_buffer), frame_meta.batch_id)
                frame_np = np.array(n_frame, copy=True, order='C')
                frame_np = cv2.cvtColor(frame_np, cv2.COLOR_RGBA2BGR)

                if frame_num == 0:
                    fh, fw = frame_np.shape[:2]
                    logger.info("[Probe A] Full-res camera %s: %dx%d", camera_id, fw, fh)

                if _recording_manager is not None and _recording_manager.is_recording:
                    # frame_np is already a CPU copy — no additional copy needed here.
                    _recording_manager.push_camera_frame(camera_id, frame_np)

            except Exception as e:
                if frame_num % 30 == 0:
                    logger.warning(
                        "pre_tiler: get_nvds_buf_surface failed at frame %d: %s",
                        frame_num, e,
                    )

        # ... rest of probe continues with frame_np (may be None if not needed)

    return Gst.PadProbeReturn.OK
