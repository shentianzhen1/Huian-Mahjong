"""Development-only rectification of a reviewed visible face quadrilateral.

Corners describe the visible artwork surface, not an occluded tile's imagined
outline. This helper neither detects corners nor assigns identity. Reject invalid
or out-of-frame polygons instead of filling missing source pixels.
"""
from __future__ import annotations

import math
from typing import Any, Sequence


def rectify_reviewed_visible_face(
    image: Any,
    corners: Sequence[Sequence[float]],
    *,
    output_size: tuple[int, int],
) -> Any:
    """Warp TL/TR/BR/BL source corners to the supplied face dimensions.

Output size must be fixed by the caller before identity results are inspected.
No enlargement here creates independent evidence or a missing tile face.
"""
    import cv2
    import numpy as np
    from PIL import Image

    if len(corners) != 4:
        raise ValueError("exactly four reviewed visible corners required")
    width, height = image.size
    points = []
    for point in corners:
        if len(point) != 2:
            raise ValueError("each corner needs x/y")
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in point):
            raise ValueError("finite numeric corners required")
        x, y = point
        if not (0 <= x <= width - 1 and 0 <= y <= height - 1):
            raise ValueError("visible corners outside source image")
        points.append((float(x), float(y)))
    if len(output_size) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or v < 8 for v in output_size):
        raise ValueError("output_size needs two integer dimensions >=8")
    # TL/TR/BR/BL must describe a strictly convex clockwise image polygon.
    turns = []
    for i in range(4):
        a, b, c = points[i], points[(i + 1) % 4], points[(i + 2) % 4]
        turns.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if any(turn <= 0 for turn in turns):
        raise ValueError("corners must be convex TL/TR/BR/BL")
    area = abs(sum(points[i][0] * points[(i+1)%4][1] - points[(i+1)%4][0] * points[i][1] for i in range(4))) / 2
    if area < 64:
        raise ValueError("visible surface too small")
    out_width, out_height = output_size
    target = np.float32(((0, 0), (out_width-1, 0), (out_width-1, out_height-1), (0, out_height-1)))
    matrix = cv2.getPerspectiveTransform(np.float32(points), target)
    warped = cv2.warpPerspective(np.array(image.convert("RGB")), matrix, output_size,
                                 flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return Image.fromarray(warped)
