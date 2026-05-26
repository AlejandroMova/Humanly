"""
Lazy GPU→CPU frame copy decision in the GStreamer probe (pre_tiler_analytics_probe).

At every probe invocation, the pipeline must decide whether to copy the current
frame from GPU VRAM to CPU RAM. The copy is expensive (~2ms on Orin Nano) and
blocks the GStreamer thread, so it should only happen when at least one worker
actually needs pixel data for this frame.

The block below accumulates this decision across several independent conditions
by mutating a single `_needs_pixel` flag in multiple steps.

New pattern to note: multi-step accumulator boolean — the decision is spread
across several mutation points instead of being expressed as a single predicate.
"""

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


def pre_tiler_analytics_probe(_pad, info):
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        return Gst.PadProbeReturn.OK
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    if not batch_meta:
        return Gst.PadProbeReturn.OK

    for frame_meta in _iter_pyds_list(batch_meta.frame_meta_list, pyds.NvDsFrameMeta.cast):
        frame_num  = frame_meta.frame_num
        pad_index  = frame_meta.pad_index
        camera_id  = f"cam-{pad_index}"

        # Lazy frame read: GPU→CPU copy only when a worker genuinely needs pixel data.
        # For pose/face: always copy when detections exist.
        # For appearance/ReID: only copy when there are new tracks or tracks still awaiting
        # their first embedding — once all settled, skip the copy to avoid blocking GStreamer.
        # For recording: always copy when the RecordingManager is actively recording.
        frame_np = None
        _needs_pixel = _recording_manager is not None and _recording_manager.is_recording
        if frame_meta.num_obj_meta > 0:
            if _pose_worker is not None or _face_recognizer is not None:
                _needs_pixel = True
            if not _needs_pixel and _appearance_worker is not None:
                # Count only person tracks (class 0), not bags/faces which inflate num_obj_meta.
                n_persons_in_frame = sum(
                    1 for om in _iter_pyds_list(frame_meta.obj_meta_list, pyds.NvDsObjectMeta.cast)
                    if int(om.class_id) == PGIE_CLASS_PERSON
                )
                n_known = sum(1 for k in _active_tracks if k[0] == pad_index)
                _needs_pixel = (
                    n_persons_in_frame > n_known
                    or any(not s.appearance_sent
                           for k, s in _active_tracks.items() if k[0] == pad_index)
                )
        if _needs_pixel:
            try:
                n_frame = pyds.get_nvds_buf_surface(hash(gst_buffer), frame_meta.batch_id)
                frame_np = np.array(n_frame, copy=True, order='C')
                frame_np = cv2.cvtColor(frame_np, cv2.COLOR_RGBA2BGR)
                if frame_num == 0:
                    fh, fw = frame_np.shape[:2]
                    print(f"[Probe A] Resolución full-res cámara {camera_id}: {fw}x{fh}")
                # Pasar frame full-res al recorder (ya es copia; no se necesita copia adicional)
                if _recording_manager is not None and _recording_manager.is_recording:
                    _recording_manager.push_camera_frame(camera_id, frame_np)
            except Exception as e:
                if frame_num % 30 == 0:
                    print(f"pre_tiler get_nvds_buf_surface frame={frame_num}: {e}")

        # ... rest of probe continues with frame_np (may be None if not needed)

    return Gst.PadProbeReturn.OK
