"""
AutoLand Digitizer - Deteksi Polyline Otomatis (Offline Computer Vision)

Modul ini menggantikan penjiplakan manual (PL di AutoCAD) dengan deteksi batas
bidang dari gambar denah. Seluruh proses berjalan lokal; tidak ada internet,
API, atau pengiriman data ke pihak ketiga.

Keluaran utama:
- kandidat polyline dalam koordinat piksel dan ternormalisasi,
- kotak crop saran,
- tingkat keyakinan (confidence),
- berkas koordinat CSV/JSON untuk audit.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class _LazyModule:
    """Pembungkus import lambat: pustaka cuma muat saat pertama diakses."""

    __slots__ = ("_name", "_module")

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_module", None)

    def _load(self):
        module = object.__getattribute__(self, "_module")
        if module is None:
            import importlib

            name = object.__getattribute__(self, "_name")
            module = importlib.import_module(name)
            object.__setattr__(self, "_module", module)
        return module

    def __getattr__(self, item):
        return getattr(self._load(), item)


np = _LazyModule("numpy")
fitz = _LazyModule("pymupdf")

cv2 = _LazyModule("cv2")


def _cv2_available() -> bool:
    try:
        cv2._load()
        return True
    except Exception:  # pragma: no cover
        return False


# =====================================================================
# Pra-pemrosesan gambar untuk deteksi
# =====================================================================

def preprocess_image_for_detection(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """
    Pra-pemrosesan citra sebelum deteksi polyline.

    Langkah-langkah:
    1. Konversi ke grayscale jika masih RGB.
    2. Terapkan CLAHE (Contrast Limited Adaptive Histogram Equalization)
       untuk meningkatkan kontras lokal — sangat membantu gambar scan
       yang gelap/ pencahayaan tidak merata.
    3. Gaussian blur ringan untuk mengurangi noise sebelum thresholding.

    Args:
        image: Array gambar RGB atau grayscale dari PDF.
        clip_limit: Batas klip CLAHE (semakin tinggi = semakin kontras).
        tile_grid_size: Ukuran grid untuk CLAHE (lebar, tinggi).

    Returns:
        Grayscale array yang sudah diproses siap thresholding.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # CLAHE: tingkatkan kontras lokal
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    enhanced = clahe.apply(gray)

    # Blur ringan untuk menghilangkan noise salt-&-pepper setelah CLAHE
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    return blurred

from config import (
    DETECTION_DPI,
    DETECTION_MAX_AREA_RATIO,
    DETECTION_MAX_CANDIDATES,
    DETECTION_MIN_AREA_RATIO,
    DETECTION_MIN_CONFIDENCE,
    DETECTION_EPS_FACTOR,
)


# =====================================================================
# Fungsi geometri dasar
# =====================================================================

def polygon_area(points: List[Tuple[float, float]]) -> float:
    """Luas poligon dengan rumus shoelace (nilai absolut)."""
    if len(points) < 3:
        return 0.0
    total = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_points(points: List[Tuple[float, float]], width: int, height: int) -> List[Tuple[float, float]]:
    if width <= 0 or height <= 0:
        return []
    return [(_clamp(x / width), _clamp(y / height)) for x, y in points]


def _denormalize_points(points: List[Tuple[float, float]], width: int, height: int) -> List[Tuple[float, float]]:
    return [(round(_clamp(x) * width, 2), round(_clamp(y) * height, 2)) for x, y in points]


def _crop_box_from_points(
    points: List[Tuple[float, float]],
    image_width: int,
    image_height: int,
    padding_ratio: float = 0.06,
) -> Tuple[float, float, float, float]:
    """Membuat kotak crop ternormalisasi di sekitar poligon dengan padding."""
    if not points:
        return (0.0, 0.0, 1.0, 1.0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = max(4.0, (max_x - min_x) * padding_ratio)
    pad_y = max(4.0, (max_y - min_y) * padding_ratio)
    return (
        round(_clamp((min_x - pad_x) / image_width), 6),
        round(_clamp((min_y - pad_y) / image_height), 6),
        round(_clamp((max_x + pad_x) / image_width), 6),
        round(_clamp((max_y + pad_y) / image_height), 6),
    )


# =====================================================================
# Render PDF & pemilihan halaman denah
# =====================================================================

_PAGE_ARRAY_CACHE: "OrderedDict[Tuple[str, int, int], Tuple[np.ndarray, str]]" = OrderedDict()


def _page_array_cache_get(key):
    cached = _PAGE_ARRAY_CACHE.get(key)
    if cached is not None:
        # Bawa ke depan agar isi cache tetap panas selama penggunaan berturut-turut.
        _PAGE_ARRAY_CACHE.move_to_end(key)
    return cached


def _page_array_cache_put(key, value):
    _PAGE_ARRAY_CACHE[key] = value
    _PAGE_ARRAY_CACHE.move_to_end(key)
    while len(_PAGE_ARRAY_CACHE) > 4:
        _PAGE_ARRAY_CACHE.popitem(last=False)


def clear_page_array_cache():
    _PAGE_ARRAY_CACHE.clear()


def render_page_array(pdf_path: str, page_number: int, dpi: int = DETECTION_DPI) -> Tuple[Optional[np.ndarray], str]:
    """
    Merender satu halaman PDF menjadi array RGB numpy.
    Mengembalikan (array, pesan_error). Hasil direuse selama sesi agar
    deteksi ulang pada halaman sama tidak merender ulang pixmap.
    """
    key = (os.path.abspath(pdf_path), int(page_number), int(dpi))
    cached = _page_array_cache_get(key)
    if cached is not None:
        return cached
    try:
        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > doc.page_count:
            result = (None, f"Nomor halaman {page_number} di luar rentang (1-{doc.page_count}).")
            doc.close()
            return result
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=int(dpi), alpha=False)
        channels = pix.n
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, channels)
        if channels == 4:
            image = image[:, :, :3]
        elif channels == 1:
            image = np.repeat(image, 3, axis=2)
        result = (np.ascontiguousarray(image), "")
        doc.close()
        _page_array_cache_put(key, result)
        return result
    except Exception as exc:
        return None, f"Gagal merender halaman PDF: {exc}"


def suggest_denah_page(pdf_path: str) -> Dict[str, Any]:
    """
    Menebak halaman yang paling mungkin berisi gambar denah.
    Heuristik: kata kunci 'gambar situasi/denah/skala', jumlah gambar raster,
    dan jumlah path vektor. untux PDF scan tetap mengandalkan teks OCR + posisi halaman.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return {"success": False, "page": 1, "message": str(exc), "details": []}

    keywords = {
        "gambar situasi": 6,
        "gambar skituasi": 6,
        "pendjelasan": 5,
        "penjelasan": 5,
        "batas tanah": 5,
        "perbandingan": 3,
        "denah": 4,
        "situasi": 1,  # kata 'SITUASI' juga sering muncul di halaman administratif
        "peta": 2,
        "bidang": 1,
        "skala": 2,
        "gambar": 1,
        # Penanda halaman administratif (diberi bobot negatif).
        "daftar isian": -4,
        "surat-ukur": -3,
        "djawatan": -2,
    }
    details: List[Dict[str, Any]] = []
    for index in range(doc.page_count):
        page = doc[index]
        text = (page.get_text() or "").lower()
        score = 0.0
        matched = []
        for word, weight in keywords.items():
            if word in text:
                score += weight
                matched.append(word)

        image_count = len(page.get_images(full=True) or [])
        drawing_count = len(page.get_drawings() or [])
        if image_count:
            score += min(3.0, image_count * 0.6)
        if drawing_count:
            score += min(3.0, drawing_count * 0.2)
        # Dokumen pertanahan umumnya meletakkan Gambar Situasi pada halaman 2.
        if index == 1:
            score += 1.5

        details.append({
            "page": index + 1,
            "score": round(score, 2),
            "keywords": matched,
            "image_count": image_count,
            "drawing_count": drawing_count,
        })

    doc.close()
    if not details:
        return {"success": False, "page": 1, "message": "PDF tidak memiliki halaman.", "details": []}

    best = max(details, key=lambda item: item["score"])
    # Jika semua skor 0, tetap pakai halaman 2 bila ada.
    page = best["page"] if best["score"] > 0 else (2 if len(details) >= 2 else 1)
    return {
        "success": True,
        "page": page,
        "message": f"Halaman {page} dipilih otomatis sebagai gambar denah.",
        "details": details,
    }


# =====================================================================
# Deteksi polyline
# =====================================================================

def _build_candidate(
    approx_points: np.ndarray,
    contour_area: float,
    contour_perimeter: float,
    scale_back: float,
    image_width: int,
    image_height: int,
    method: str,
) -> Optional[Dict[str, Any]]:
    pts = [(float(p[0][0]) * scale_back, float(p[0][1]) * scale_back) for p in approx_points]
    if len(pts) < 3:
        return None

    area_px = abs(polygon_area(pts))
    image_area = float(image_width * image_height)
    area_ratio = area_px / image_area if image_area else 0.0
    if not (DETECTION_MIN_AREA_RATIO <= area_ratio <= DETECTION_MAX_AREA_RATIO):
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bbox_w, bbox_h = max(xs) - min(xs), max(ys) - min(ys)
    # Ganti batas absolut piksel dengan relatif terhadap dimensi gambar.
    # Ini memungkinkan deteksi pada gambar berukuran apapun (kecil/gede).
    min_dim = min(image_width, image_height)
    if bbox_w < 0.02 * min_dim or bbox_h < 0.02 * min_dim:
        return None
    # Aspect ratio tetap tetap abs. 1:18 terlampaui dianggap tidak wajar untuk bidang pertanahan.
    if bbox_w / max(bbox_h, 1.0) > 18 or bbox_h / max(bbox_w, 1.0) > 18:
        return None

    # Hitung hull menggunakan pts yang sudah discale_back (coordinate original).
    # Konversi ke float32 dan format yang benar untuk cv2.convexHull.
    try:
        pts_arr = np.array(pts, dtype=np.float32).reshape(-1, 1, 2)
        hull = cv2.convexHull(pts_arr)
    except Exception:
        hull = np.array([], dtype=np.int32).reshape(0, 1, 2)
    hull_area = abs(cv2.contourArea(hull)) if hull is not None and len(hull) > 0 else 0
    solidity = _clamp(area_px / hull_area) if hull_area > 0 else 0.0
    # Rendahkan ambang solidity untuk skan yang bersih/hijau; tetap menjaga pengamanan.
    if solidity < 0.20:
        return None

    n = len(pts)
    vertex_score = _clamp(1.0 - abs(n - 8) / 22.0)
    solidity_score = _clamp(solidity / 0.80)
    area_score = _clamp(1.0 - abs(math.log(max(area_ratio, 1e-6) / 0.15)) / 2.4)
    confidence = 0.30 + 0.24 * solidity_score + 0.24 * vertex_score + 0.22 * area_score
    confidence = round(_clamp(confidence), 4)
    if confidence < DETECTION_MIN_CONFIDENCE:
        return None

    normalized = _normalize_points(pts, image_width, image_height)
    crop_box = _crop_box_from_points(pts, image_width, image_height)

    return {
        "vertices_px": [[round(x, 2), round(y, 2)] for x, y in pts],
        "vertices_normalized": [[round(x, 6), round(y, 6)] for x, y in normalized],
        "crop_box_normalized": list(crop_box),
        "area_px": round(area_px, 2),
        "perimeter_px": round(float(contour_perimeter * scale_back), 2),
        "vertex_count": n,
        "solidity": round(solidity, 4),
        "confidence": confidence,
        "method": method,
    }


def detect_polylines_from_array(
    image: np.ndarray,
    max_candidates: int = DETECTION_MAX_CANDIDATES,
) -> Dict[str, Any]:
    """
    Deteksi batas bidang dari citra RGB menggunakan adaptive threshold + contour.
    """
    if not _cv2_available():
        return {
            "success": False,
            "candidates": [],
            "message": "OpenCV belum terpasang. Jalankan: pip install -r requirements.txt",
        }
    if image is None or image.size == 0:
        return {"success": False, "candidates": [], "message": "Gambar denah kosong."}

    original_h, original_w = image.shape[:2]
    max_side = 1600
    scale = min(1.0, max_side / max(original_h, original_w))
    work = image
    if scale < 1.0:
        work = cv2.resize(image, (int(original_w * scale), int(original_h * scale)), interpolation=cv2.INTER_AREA)
    scale_back = 1.0 / scale

    # Pra-pemrosesan: grayscale + CLAHE + blur (lebih kuat dari sebelumnya)
    work = preprocess_image_for_detection(work, clip_limit=2.0, tile_grid_size=(8, 8))

    binary = cv2.adaptiveThreshold(
        work, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9
    )
    # Hubungkan garis yang terputus kecil, lalu buang noise titik.
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)

    # Ekspresi cepat: jika tak ada piksel terbentuk sama sekali, hentikan dulu.
    if cv2.countNonZero(binary) == 0:
        return {
            "success": False,
            "candidates": [],
            "message": "Tidak ada pola terdeteksi pada halaman.",
        }

    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: List[Dict[str, Any]] = []
    work_h, work_w = binary.shape[:2]
    min_work_dim = min(work_w, work_h)
    for contour in contours:
        area = abs(cv2.contourArea(contour))
        perimeter = cv2.arcLength(contour, True)
        # Gunakan threshold relatif terhadap ukuran gambar kerja (scaled).
        # Ini menggantikan batas absolut 80 dan 500 piksel.
        if perimeter < 0.02 * min_work_dim or area < 0.0001 * work_w * work_h:
            continue
        epsilon = DETECTION_EPS_FACTOR * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)
        candidate = _build_candidate(
            approx, area, perimeter, scale_back, original_w, original_h,
            "opencv-adaptive-threshold",
        )
        if candidate:
            candidates.append(candidate)

    # Hilangkan kandidat yang saling tumpang tindih (hampir sama).
    candidates.sort(key=lambda c: (c["confidence"], c["area_px"]), reverse=True)
    unique: List[Dict[str, Any]] = []
    for cand in candidates:
        box_a = cand["crop_box_normalized"]
        duplicated = False
        for kept in unique:
            box_b = kept["crop_box_normalized"]
            ix = max(0.0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]))
            iy = max(0.0, min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]))
            inter = ix * iy
            area_a = max(1e-6, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
            area_b = max(1e-6, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
            if inter / min(area_a, area_b) > 0.75:
                duplicated = True
                break
        if not duplicated:
            unique.append(cand)
        if len(unique) >= max_candidates:
            break

    message = (
        f"Ditemukan {len(unique)} kandidat polyline otomatis."
        if unique else
        "Tidak ada polyline yang memenuhi kriteria. Coba pilih halaman lain atau sesuaikan area crop manual."
    )
    return {"success": bool(unique), "candidates": unique, "message": message}


def extract_vector_candidates(pdf_path: str, page_number: int) -> List[Dict[str, Any]]:
    """
    Mengambil poligon tertutup dari PDF born-digital (bukan scan).
    Dikembalikan dalam format kandidat yang sama dengan deteksi raster.
    """
    candidates: List[Dict[str, Any]] = []
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number - 1]
        width, height = page.rect.width, page.rect.height
        for drawing in page.get_drawings():
            items = drawing.get("items") or []
            points: List[Tuple[float, float]] = []
            for item in items:
                # item bentuknya ('l', p1, p2) atau ('c', p1, p2, p3, p4)
                for value in item[1:]:
                    if hasattr(value, "x") and hasattr(value, "y"):
                        points.append((float(value.x), float(value.y)))
            if len(points) < 3:
                continue
            # Hilangkan titik duplikat berurutan.
            cleaned = [points[0]]
            for pt in points[1:]:
                if math.dist(pt, cleaned[-1]) > 1.0:
                    cleaned.append(pt)
            if len(cleaned) > 3 and math.dist(cleaned[0], cleaned[-1]) < 1.0:
                cleaned.pop()
            area_px = polygon_area(cleaned)
            if area_px < 1000:
                continue
            normalized = _normalize_points(cleaned, width, height)
            candidates.append({
                "vertices_px": [[round(x, 2), round(y, 2)] for x, y in cleaned],
                "vertices_normalized": [[round(x, 6), round(y, 6)] for x, y in normalized],
                "crop_box_normalized": list(_crop_box_from_points(cleaned, width, height)),
                "area_px": round(area_px, 2),
                "perimeter_px": 0.0,
                "vertex_count": len(cleaned),
                "solidity": 1.0,
                "confidence": 0.82,
                "method": "pdf-vector",
            })
        doc.close()
    except Exception:
        return []
    return candidates[:DETECTION_MAX_CANDIDATES]


def detect_on_page(
    pdf_path: str,
    page_number: int,
    dpi: int = DETECTION_DPI,
    use_vector_first: bool = True,
    image: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Alur lengkap: render halaman -> coba vektor -> deteksi raster -> susun kandidat.
    Parameter `image` memungkinkan panggilan ulang memakai pixmap yang sudah
    dirender (mis. sebelumnya oleh render_page_array) tanpa merender ulang.
    """
    if image is None:
        image, err = render_page_array(pdf_path, page_number, dpi=dpi)
        if image is None:
            return {"success": False, "candidates": [], "message": err, "page": page_number}

    result: Dict[str, Any]
    if use_vector_first:
        vector_candidates = extract_vector_candidates(pdf_path, page_number)
        result = {
            "success": bool(vector_candidates),
            "candidates": vector_candidates,
            "message": "Polyline diambil langsung dari vektor PDF." if vector_candidates else "",
        }
    else:
        result = {"success": False, "candidates": [], "message": ""}

    if not result["success"]:
        result = detect_polylines_from_array(image)

    result.update({
        "page": page_number,
        "image_width": int(image.shape[1]),
        "image_height": int(image.shape[0]),
        "dpi": int(dpi),
    })
    return result


# =====================================================================
# Petunjuk identitas & ekspor koordinat
# =====================================================================

def guess_document_hints(pdf_path: str) -> Dict[str, str]:
    """Menebak nomor GS, tahun, dan luas dari nama file/teks PDF (tetap wajib dicek operator)."""
    hints = {"nomor_gs": "", "tahun": "", "luas_dokumen": ""}
    name = os.path.basename(pdf_path or "")
    match = re.search(r"GS[_ ]?(\d{1,6})[_ ]?(\d{4})", name, re.IGNORECASE)
    if match:
        hints["nomor_gs"] = match.group(1)
        hints["tahun"] = match.group(2)
    else:
        year_match = re.search(r"(19|20)\d{2}", name)
        if year_match:
            hints["tahun"] = year_match.group(0)

    try:
        doc = fitz.open(pdf_path)
        text = " ".join((p.get_text() or "") for p in doc)
        doc.close()
        area_match = re.search(r"(?:luas|Luas|LUAS)[^0-9]{0,30}([0-9][0-9.,]{1,12})\s*(?:m2|m²|M2)", text)
        if area_match:
            raw = area_match.group(1).replace(".", "").replace(",", ".")
            hints["luas_dokumen"] = raw
    except Exception:
        pass
    return hints


def write_coordinate_files(
    output_dir: str | os.PathLike,
    identity: str,
    vertices_px: List[Tuple[float, float]],
    image_width: int,
    image_height: int,
    luas_dokumen: float,
    area_px: float,
    crop_path: str = "",
    method: str = "",
    confidence: float = 0.0,
) -> Dict[str, str]:
    """
    Menulis koordinat polyline ke CSV dan JSON.
    X/Y meter dihitung dari skala m_per_px = sqrt(luas_dokumen / luas_polyline_px²).
    """
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", identity or "denah").strip("_") or "denah"

    scale_m_per_px = math.sqrt(float(luas_dokumen) / area_px) if area_px > 0 and luas_dokumen > 0 else 0.0
    points = []
    for index, (x, y) in enumerate(vertices_px, start=1):
        points.append({
            "no": index,
            "x_px": round(float(x), 3),
            "y_px": round(float(y), 3),
            "x_normalized": round(float(x) / image_width, 6) if image_width else 0.0,
            "y_normalized": round(float(y) / image_height, 6) if image_height else 0.0,
            "x_model": round(float(x) * scale_m_per_px, 4),
            "y_model": round((image_height - float(y)) * scale_m_per_px, 4),
        })

    json_path = folder / f"Koordinat_{safe}.json"
    csv_path = folder / f"Koordinat_{safe}.csv"

    payload = {
        "identitas_dokumen": identity,
        "metode_deteksi": method,
        "keyakinan_deteksi": confidence,
        "lebar_gambar_px": image_width,
        "tinggi_gambar_px": image_height,
        "luas_dokumen_m2": luas_dokumen,
        "luas_polyline_px2": area_px,
        "meter_per_piksel": scale_m_per_px,
        "path_crop": crop_path,
        "titik": points,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([
            "No", "X_piksel", "Y_piksel", "X_ternormalisasi", "Y_ternormalisasi",
            "X_model_m", "Y_model_m",
        ])
        for point in points:
            writer.writerow([
                point["no"], point["x_px"], point["y_px"],
                point["x_normalized"], point["y_normalized"],
                point["x_model"], point["y_model"],
            ])

    return {"csv": str(csv_path), "json": str(json_path), "scale_m_per_px": scale_m_per_px}
