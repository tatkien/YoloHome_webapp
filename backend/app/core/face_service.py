"""Face detection (RetinaFace) + alignment + embedding (ArcFace) service.

Exposes a single ``FaceService`` class that is loaded once at startup and
injected into route handlers via a FastAPI dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np
import onnxruntime as ort

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard ArcFace 5-point reference landmarks (for 112×112 crop).
# Source: insightface/utils/face_align.py
# ---------------------------------------------------------------------------
ARCFACE_REF_LANDMARKS = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


@dataclass
class FaceDetection:
    """Single detected face with bounding-box, landmarks, and score."""

    bbox: np.ndarray        # (4,) — x1, y1, x2, y2
    landmarks: np.ndarray   # (5, 2) — left_eye, right_eye, nose, mouth_left, mouth_right
    score: float


class FaceService:
    """Singleton service wrapping RetinaFace + ArcFace ONNX inference."""

    def __init__(
        self,
        retinaface_path: str | None = None,
        arcface_path: str | None = None,
    ) -> None:
        retinaface_path = retinaface_path or settings.RETINAFACE_MODEL_PATH
        arcface_path = arcface_path or settings.ARCFACE_MODEL_PATH

        opts = ort.SessionOptions()
        opts.log_severity_level = 3  # suppress noisy logs

        logger.info("Loading RetinaFace model from %s …", retinaface_path)
        self._retina_session = ort.InferenceSession(
            retinaface_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )

        logger.info("Loading ArcFace model from %s …", arcface_path)
        self._arcface_session = ort.InferenceSession(
            arcface_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )

        # Cache RetinaFace I/O metadata
        _retina_input = self._retina_session.get_inputs()[0]
        self._retina_input_name = _retina_input.name
        self._retina_input_size = tuple(_retina_input.shape[2:4])  # (H, W)

        # Cache ArcFace I/O metadata
        self._arcface_input_name = self._arcface_session.get_inputs()[0].name

        logger.info("Face models loaded successfully.")

    # ------------------------------------------------------------------
    # RetinaFace detection
    # ------------------------------------------------------------------
    def detect_faces(
        self,
        image_bgr: np.ndarray,
        score_threshold: float = 0.5,
        nms_threshold: float = 0.4,
    ) -> list[FaceDetection]:
        """Detect faces in a BGR image using RetinaFace.

        Returns a list of ``FaceDetection`` objects sorted by descending score.
        """
        img_h, img_w = image_bgr.shape[:2]

        # Resolve model input size (640×640 for det_10g)
        input_h, input_w = self._retina_input_size
        if not isinstance(input_h, int) or input_h <= 0:
            input_h, input_w = 640, 640

        # --- Letterbox resize (preserve aspect ratio, pad with zeros) ---
        # Matches the official InsightFace reference implementation.
        # Using a single det_scale avoids the separate scale_x / scale_y that
        # would otherwise distort landmark positions and break ArcFace alignment.
        im_ratio = float(img_h) / float(img_w)
        model_ratio = float(input_h) / float(input_w)
        if im_ratio > model_ratio:
            new_h = input_h
            new_w = int(new_h / im_ratio)
        else:
            new_w = input_w
            new_h = int(new_w * im_ratio)

        det_scale = float(new_h) / float(img_h)  # same in both axes after proportional resize

        resized = cv2.resize(image_bgr, (new_w, new_h))
        canvas = np.zeros((input_h, input_w, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = resized

        blob = cv2.dnn.blobFromImage(
            canvas,
            scalefactor=1.0 / 128.0,
            size=(input_w, input_h),
            mean=(127.5, 127.5, 127.5),
            swapRB=True,
        )

        # Run inference
        outputs = self._retina_session.run(None, {self._retina_input_name: blob})

        # Parse outputs — RetinaFace det_10g produces 9 outputs:
        #   3 stride groups × (scores, bboxes, landmarks)
        detections = self._parse_retinaface_outputs(
            outputs, input_w, input_h, score_threshold
        )

        # Scale all coordinates back to original image space
        for det in detections:
            det.bbox /= det_scale
            det.landmarks /= det_scale

        # NMS
        if not detections:
            return []

        bboxes = np.array([d.bbox for d in detections])
        scores = np.array([d.score for d in detections])
        indices = self._nms(bboxes, scores, nms_threshold)

        return [detections[i] for i in indices]

    def _parse_retinaface_outputs(
        self,
        outputs: list[np.ndarray],
        input_w: int,
        input_h: int,
        score_threshold: float,
    ) -> list[FaceDetection]:
        """Parse raw RetinaFace output tensors into FaceDetection objects.

        Returns detections in the **letterbox coordinate space** (640x640).
        The caller (``detect_faces``) is responsible for dividing by ``det_scale``
        to convert back to original image coordinates.

        Follows the InsightFace reference implementation for anchor generation
        and output decoding.
        """
        fmc = 3  # feature map count
        strides = [8, 16, 32]
        num_anchors = 2  # det_10g uses 2 anchors per location

        detections: list[FaceDetection] = []

        for idx in range(fmc):
            # Each stride group has 3 outputs: scores, bboxes, landmarks
            scores_raw = outputs[idx]           # (1, N, 1) face scores
            bbox_preds = outputs[idx + fmc]     # (1, N, 4)
            kps_preds  = outputs[idx + fmc * 2] # (1, N, 10)

            stride = strides[idx]
            feat_h = input_h // stride
            feat_w = input_w // stride

            # --- Generate anchor centers (matching InsightFace reference) ---
            anchor_centers = np.stack(
                np.mgrid[:feat_h, :feat_w][::-1], axis=-1
            ).astype(np.float32)
            anchor_centers = (anchor_centers * stride).reshape(-1, 2)
            if num_anchors > 1:
                anchor_centers = np.stack(
                    [anchor_centers] * num_anchors, axis=1
                ).reshape(-1, 2)

            # --- Flatten outputs & pre-multiply by stride ---
            scores    = scores_raw.reshape(-1)
            bboxes    = bbox_preds.reshape(-1, 4) * stride
            landmarks = kps_preds.reshape(-1, 10) * stride

            # --- Filter by score threshold ---
            pos_inds = np.where(scores >= score_threshold)[0]
            if len(pos_inds) == 0:
                continue

            pos_scores    = scores[pos_inds]
            pos_bboxes    = bboxes[pos_inds]
            pos_landmarks = landmarks[pos_inds]
            pos_anchors   = anchor_centers[pos_inds]

            # --- Decode bboxes (distance → x1y1x2y2) ---
            x1 = pos_anchors[:, 0] - pos_bboxes[:, 0]
            y1 = pos_anchors[:, 1] - pos_bboxes[:, 1]
            x2 = pos_anchors[:, 0] + pos_bboxes[:, 2]
            y2 = pos_anchors[:, 1] + pos_bboxes[:, 3]
            bboxes_decoded = np.stack([x1, y1, x2, y2], axis=-1)

            # --- Decode landmarks ---
            lms = pos_landmarks.reshape(-1, 5, 2)
            lms[:, :, 0] += pos_anchors[:, 0:1]   # x + anchor_x
            lms[:, :, 1] += pos_anchors[:, 1:2]   # y + anchor_y

            for i in range(len(pos_scores)):
                detections.append(
                    FaceDetection(
                        bbox=bboxes_decoded[i].copy(),
                        landmarks=lms[i].copy(),
                        score=float(pos_scores[i]),
                    )
                )

        # Sort by score descending
        detections.sort(key=lambda d: d.score, reverse=True)
        return detections

    @staticmethod
    def _decode_bboxes(
        anchors: np.ndarray, raw: np.ndarray, stride: int
    ) -> np.ndarray:
        """Decode distance-based bbox predictions to x1,y1,x2,y2."""
        x1 = anchors[:, 0] - raw[:, 0] * stride
        y1 = anchors[:, 1] - raw[:, 1] * stride
        x2 = anchors[:, 0] + raw[:, 2] * stride
        y2 = anchors[:, 1] + raw[:, 3] * stride
        return np.stack([x1, y1, x2, y2], axis=-1)

    @staticmethod
    def _decode_landmarks(
        anchors: np.ndarray, raw: np.ndarray, stride: int
    ) -> np.ndarray:
        """Decode landmark predictions to (N, 5, 2)."""
        lms = raw.reshape(-1, 5, 2)
        lms[:, :, 0] = anchors[:, 0:1] + lms[:, :, 0] * stride
        lms[:, :, 1] = anchors[:, 1:2] + lms[:, :, 1] * stride
        return lms

    @staticmethod
    def _nms(
        bboxes: np.ndarray, scores: np.ndarray, threshold: float
    ) -> list[int]:
        """Simple greedy NMS returning kept indices."""
        x1, y1, x2, y2 = bboxes[:, 0], bboxes[:, 1], bboxes[:, 2], bboxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1] # Plus 1 because we skipped the current top index in iou calculation
        return keep

    # ------------------------------------------------------------------
    # Face alignment
    # ------------------------------------------------------------------
    @staticmethod
    def align_face(
        image_bgr: np.ndarray,
        landmarks_5: np.ndarray,
        output_size: int = 112,
    ) -> np.ndarray:
        """Align and crop a face to 112x112 using similarity transform.

        Parameters
        ----------
        image_bgr : np.ndarray
            Full image in BGR.
        landmarks_5 : np.ndarray
            Five facial landmarks as (5, 2) — [left_eye, right_eye, nose,
            mouth_left, mouth_right].
        output_size : int
            Output square size (default 112 for ArcFace).

        Returns
        -------
        np.ndarray
            Aligned face crop of shape (output_size, output_size, 3), BGR.
        """
        dst = ARCFACE_REF_LANDMARKS.copy()
        # Estimate affine transform (similarity)
        tform = cv2.estimateAffinePartial2D(landmarks_5, dst, method=cv2.LMEDS)[0]
        if tform is None:
            # Fallback — simple crop from bbox center
            tform = cv2.estimateAffinePartial2D(landmarks_5, dst)[0]
        aligned = cv2.warpAffine(
            image_bgr, tform, (output_size, output_size), borderValue=(0, 0, 0)
        )
        return aligned

    # ------------------------------------------------------------------
    # ArcFace embedding
    # ------------------------------------------------------------------
    def extract_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """Run ArcFace on a 112x112 aligned BGR face → L2-normalized 512-d vector."""
        # Preprocess: BGR → RGB, HWC → CHW, normalise to [-1, 1]
        img = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB).astype(np.float32)
        img = (img / 255.0 - 0.5) / 0.5  # → [-1, 1]
        img = np.transpose(img, (2, 0, 1))  # CHW
        blob = np.expand_dims(img, axis=0)  # (1, 3, 112, 112)

        embedding = self._arcface_session.run(None, {self._arcface_input_name: blob})[0]
        embedding = embedding.flatten()
        # L2 normalise
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    # ------------------------------------------------------------------
    # Convenience — full pipeline
    # ------------------------------------------------------------------
    def detect_and_embed(
        self,
        image_bgr: np.ndarray,
        score_threshold: float = 0.5,
    ) -> list[tuple[np.ndarray, np.ndarray, float]]:
        """Detect faces, align each, and extract ArcFace embeddings.

        Returns
        -------
        list[tuple[bbox, embedding, score]]
            Each entry contains:
            - bbox (4,) — x1, y1, x2, y2
            - embedding (512,) — L2-normalised 512-d vector
            - score — detection confidence
        """
        detections = self.detect_faces(image_bgr, score_threshold=score_threshold)
        results: list[tuple[np.ndarray, np.ndarray, float]] = []
        for det in detections:
            aligned = self.align_face(image_bgr, det.landmarks)
            embedding = self.extract_embedding(aligned)
            results.append((det.bbox, embedding, det.score))
        return results


# ---------------------------------------------------------------------------
# FastAPI dependency — lazy singleton
# ---------------------------------------------------------------------------
_face_service: FaceService | None = None


def get_face_service() -> FaceService:
    """Return the global ``FaceService`` singleton (created on first call)."""
    global _face_service
    if _face_service is None:
        _face_service = FaceService()
    return _face_service
