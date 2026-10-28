"""How much of a video goes into a map. Pure arithmetic, so the API can use it without the
photogrammetry dependencies."""

import math


def video_frame_rate(duration: float | None, fps: float, limit: int) -> float:
    """Frames per second to sample: ``fps``, or slower so a long video is covered end to end
    within ``limit`` frames instead of stopping part-way."""
    if not duration or duration <= 0:
        return fps
    return min(fps, limit / duration)


def estimated_frames(duration: float | None, fps: float, limit: int) -> int:
    """How many frames a video will contribute (used to check limits before queueing)."""
    if not duration or duration <= 0:
        return limit
    return max(1, min(limit, math.ceil(duration * video_frame_rate(duration, fps, limit))))
