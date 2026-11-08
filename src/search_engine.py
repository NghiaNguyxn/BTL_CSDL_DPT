# -*- coding: utf-8 -*-
"""
Module Bộ máy Tìm kiếm Ảnh cá التương đồng Dựa trên Nội dung (Fish CBIR Search Engine - Phần 3 & Phần 4):
- Kết nối trực tiếp với Hệ CSDL Đa phương tiện SQLite (data/fish_multimedia.db - 6 bảng)
  và Chỉ mục Không gian Ball-Tree (data/ball_tree_index.pkl).
- Hỗ trợ tiền xử lý tự động cho cả ảnh BGRA (đã tách nền) và ảnh RGB/JPG mới bất kỳ (tự động phân đoạn vùng thân cá).
- Hỗ trợ lọc thô đa độ phân giải bằng Chữ ký Lưới Nhị phân S5_bin64 (64-bit) & S5_bin192 (192-bit chuẩn Slide 30 & 34)
  theo khoảng cách Hamming (XOR + popcount) hoặc lọc bằng cây Ball-Tree.
- Hỗ trợ 4 chế độ độ đo:
  1. hybrid_2level (Mặc định): L1 cho Histogram (C1, C3, T2) + Z-score L2 cho đặc trưng liên tục, chuẩn hóa 2 cấp (med_m, med_G).
  2. l1_manhattan: Khoảng cách Manhattan (L1) chuẩn hóa theo bộ trọng số.
  3. l2_euclidean: Khoảng cách Euclidean (L2) trên không gian Z-score theo bộ trọng số.
  4. cosine: Độ tương đồng / khoảng cách Cosine trên không gian Z-score theo bộ trọng số.
  (Kèm tùy chọn bật Ma trận tương đồng màu tri giác chéo bin A_78x78 Quadratic Form Z^T A Z cho C1).
- Xuất đầy đủ các Kết quả Trung gian (Intermediate Results) phục vụ minh họa Phần 4b và Giao diện Demo Phần 5.
"""

import os
import sys
import time
import json
import base64
import pickle
import sqlite3
import cv2
import numpy as np

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.features.pipeline import process_single_image

SPECIES_INFO = {
    "boal": {
        "vi_name": "Cá leo",
        "latin_name": "Wallago attu",
        "desc": "Thân rất thuôn dài (AR ~ 4.1), da trơn ánh bạc xám, không vảy, miệng rộng.",
    },
    "ilish": {
        "vi_name": "Cá cháy (Cá mòi đường)",
        "latin_name": "Tenualosa ilisha",
        "desc": "Thân hình thoi bụng võng sâu như lưỡi dao, vảy bạc lấp lánh, đuôi xẻ chữ V sâu.",
    },
    "katla": {
        "vi_name": "Cá chép Ấn Độ (Mè vinh)",
        "latin_name": "Gibelion catla",
        "desc": "Đầu to, sống lưng gù cao vọt ngay sau đầu, thân dày, phiến vảy rất to và sẫm.",
    },
    "koi": {
        "vi_name": "Cá rô đồng",
        "latin_name": "Anabas testudineus",
        "desc": "Thân bầu dục ngắn chắc (AR ~ 2.1), màu vàng đồng/xám lục nhạt, vây đuôi tròn liền khối.",
    },
    "rui": {
        "vi_name": "Cá trôi Ấn Độ (Rohu)",
        "latin_name": "Labeo rohita",
        "desc": "Thân thoi cân đối, lưng-bụng đối xứng, vảy mắt cáo ửng hồng/đỏ cam, vây bụng và đuôi đỏ.",
    },
    "telapia": {
        "vi_name": "Cá rô phi",
        "latin_name": "Oreochromis niloticus",
        "desc": "Thân bầu cao dẹt bên, ngực ửng hồng, có các dải sọc vằn thẳng đứng trên vây đuôi.",
    },
}

COMPONENTS = {
    "C1": (0, 78, "hist", "color", "Biểu đồ màu HSV thích nghi có ô vô sắc (78D)"),
    "C2": (78, 87, "scalar", "color", "Mô-men màu không gian CIE Lab (9D)"),
    "C3": (87, 135, "hist", "color", "Bố cục màu 6 vùng giải phẫu 3x2 (48D)"),
    "S1": (135, 143, "scalar", "shape", "8 chỉ số hình thái học cơ thể (8D)"),
    "S2": (143, 175, "scalar", "shape", "Biên dạng sống lưng – lườn bụng 16 lát cắt (32D)"),
    "S3": (175, 182, "scalar", "shape", "Hệ 7 mô-men bất biến Hu logarit (7D)"),
    "S4": (182, 211, "scalar", "shape", "Hệ số Fourier đường viền elip EFD (29D)"),
    "S5": (211, 275, "scalar", "shape", "Lưới không gian 8x8 trên hộp bao MBB (64D)"),
    "T1": (275, 335, "scalar", "texture", "Ma trận đồng xuất mức xám GLCM vùng thân cá (60D)"),
    "T2": (335, 394, "hist", "texture", "Mẫu nhị phân cục bộ đồng nhất NRI-Uniform LBP (59D)"),
    "T3": (394, 397, "scalar", "texture", "Đặc trưng kết cấu tri giác Tamura (3D)"),
    "T4": (397, 421, "scalar", "texture", "Năng lượng ngân hàng 12 bộ lọc sóng Gabor (24D)"),
}

GROUPS = {
    "color": ["C1", "C2", "C3"],
    "shape": ["S1", "S2", "S3", "S4", "S5"],
    "texture": ["T1", "T2", "T3", "T4"],
}


_U2NETP_ORT_SESSION = None


def _run_u2netp_mask(bgr: np.ndarray) -> np.ndarray:
    """
    Chạy trực tiếp mô hình tách nền chủ thể U2-NetP (u2netp.onnx, 4.7 MB) qua ONNXRuntime
    mà không nạp các thư viện nặng (numba/pymatting) để tiết kiệm bộ nhớ tối đa và tốc độ < 120ms.
    """
    global _U2NETP_ORT_SESSION
    h0, w0 = bgr.shape[:2]
    cand_paths = [
        os.path.expanduser("~/.rembg/models/u2netp/u2netp.onnx"),
        os.path.expanduser("~/.u2net/u2netp.onnx"),
    ]
    onnx_path = next((p for p in cand_paths if os.path.exists(p)), None)
    if _U2NETP_ORT_SESSION is None:
        if onnx_path is not None:
            try:
                import onnxruntime as ort
                sess_opts = ort.SessionOptions()
                sess_opts.intra_op_num_threads = 2
                _U2NETP_ORT_SESSION = ort.InferenceSession(
                    onnx_path, sess_options=sess_opts, providers=["CPUExecutionProvider"]
                )
            except Exception:
                _U2NETP_ORT_SESSION = False
        else:
            _U2NETP_ORT_SESSION = False

    if _U2NETP_ORT_SESSION is not False and _U2NETP_ORT_SESSION is not None:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        im_res = cv2.resize(rgb, (320, 320), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        im_norm = (im_res - mean) / std
        inp = np.transpose(im_norm, (2, 0, 1))[None, :, :, :]
        inp_name = _U2NETP_ORT_SESSION.get_inputs()[0].name
        pred = _U2NETP_ORT_SESSION.run(None, {inp_name: inp})[0][0, 0]
        p_min, p_max = float(pred.min()), float(pred.max())
        if p_max - p_min > 1e-6:
            pred = (pred - p_min) / (p_max - p_min)
        mask_u8 = (cv2.resize(pred, (w0, h0), interpolation=cv2.INTER_LINEAR) * 255.0).astype(np.uint8)
        return mask_u8
    return None


def segment_and_standardize_any_image(img: np.ndarray, target_size: int = 500) -> np.ndarray:
    """
    Chuẩn hóa mọi ảnh cá đầu vào (từ CSDL hoặc ảnh mới chụp bên ngoài) về định dạng chuẩn BGRA 500x500:
    - Nếu ảnh đã có 4 kênh (BGRA) 500x500 và có mặt nạ Alpha hợp lệ: giữ nguyên tuyệt đối 100% giá trị pixel.
    - Nếu ảnh có 3 kênh (BGR) hoặc ảnh chụp tự do bên ngoài (nền trắng studio, nền dưới nước, nền phức tạp):
      + Tự động tách nền bằng mô hình học sâu U2-Net (`rembg` u2netp) kết hợp lọc thành phần liên thông lớn nhất
        và lấp kín lỗ thủng nội bộ.
      + Khử viền sáng (de-haloing 1px) nếu ảnh gốc chụp trên phông trắng và tự động cân bằng trắng nhẹ nếu ảnh
        chụp dưới môi trường nước bị ám xanh lam đậm.
      + Xoay chuẩn hóa trục chính PCA về phương ngang và co giãn tỉ lệ về 440px đặt chính giữa khung 500x500.
    """
    if img is None:
        return None

    h0, w0 = img.shape[:2]
    if img.ndim == 3 and img.shape[2] == 4 and h0 == target_size and w0 == target_size:
        alpha_ch = img[:, :, 3]
        fg_ratio = float(np.mean(alpha_ch > 128))
        if 0.01 < fg_ratio < 0.96:
            # Ảnh BGRA 500x500 đã có sẵn kênh Alpha chuẩn: giữ nguyên tuyệt đối để bảo toàn 100% giá trị pixel
            return img.copy()

    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        alpha = (img > 12).astype(np.uint8) * 255
    elif img.shape[2] == 4:
        bgr = img[:, :, :3].copy()
        alpha = img[:, :, 3].copy()
        if np.mean(alpha > 128) >= 0.96 or np.mean(alpha > 128) <= 0.01:
            alpha = None
    else:
        bgr = img[:, :, :3].copy()
        alpha = None

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    border_mask = np.zeros((h0, w0), dtype=bool)
    bw = max(4, min(16, min(h0, w0) // 20))
    border_mask[:bw, :] = True
    border_mask[-bw:, :] = True
    border_mask[:, :bw] = True
    border_mask[:, -bw:] = True
    border_gray_mean = float(np.mean(gray[border_mask]))
    border_gray_std = float(np.std(gray[border_mask]))

    if alpha is None:
        if border_gray_mean < 18.0 and border_gray_std < 20.0:
            # Ảnh nền đen chuẩn (từ thư mục images_black): nếu đã đúng khung 500x500 chuẩn thì giữ nguyên bố cục
            raw_mask = (gray > 10).astype(np.uint8)
            k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            raw_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, k_close, iterations=1)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(raw_mask, connectivity=8)
            if num_labels > 1:
                largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                clean_mask = (labels == largest_label).astype(np.uint8)
                contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                filled = np.zeros_like(clean_mask)
                cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
            else:
                filled = raw_mask
            if h0 == target_size and w0 == target_size and 0.01 < float(np.mean(filled > 0)) < 0.96:
                bgr_clean = np.zeros_like(bgr)
                bgr_clean[filled > 0] = bgr[filled > 0]
                return np.dstack([bgr_clean, (filled * 255).astype(np.uint8)])
            raw_mask = filled
        else:
            # Ảnh thực tế bên ngoài: ưu tiên dùng mô hình Salient Object Segmentation U2-NetP (ONNX)
            ai_alpha = _run_u2netp_mask(bgr)
            raw_mask = None
            if ai_alpha is not None and np.mean(ai_alpha > 110) > 0.015:
                raw_mask = (ai_alpha > 110).astype(np.uint8)

            if raw_mask is None:
                # Dự phòng nếu không có rembg: khoảng cách CIE Lab so với viền
                lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
                bg_med = np.median(lab[border_mask], axis=0)
                dist_bg = np.sqrt(np.sum((lab - bg_med) ** 2, axis=2))
                raw_mask = (dist_bg > 15.0).astype(np.uint8)

        # Làm mịn biên, giữ thành phần liên thông lớn nhất và lấp kín lỗ thủng bên trong thân cá
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        raw_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
        raw_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(raw_mask, connectivity=8)
        if num_labels > 1:
            largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            clean_mask = (labels == largest_label).astype(np.uint8)
            contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filled = np.zeros_like(clean_mask)
            cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
        else:
            filled = raw_mask

        # Nếu ảnh gốc có nền trắng sáng (như fish_1.jpg), co nhẹ mặt nạ 1px để khử viền sáng (de-haloing)
        if border_gray_mean > 220.0:
            k_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            filled = cv2.erode(filled, k_erode, iterations=1)

        alpha = (filled * 255).astype(np.uint8)

    fg_bool = alpha > 128
    bgr_clean = np.zeros_like(bgr)
    if np.any(fg_bool):
        # Tự động cân bằng trắng nhẹ nếu ảnh chụp dưới nước bị ám màu xanh lam mạnh (như fish_2.jpg)
        b_mean = float(np.mean(bgr[:, :, 0][fg_bool]))
        g_mean = float(np.mean(bgr[:, :, 1][fg_bool]))
        r_mean = float(np.mean(bgr[:, :, 2][fg_bool]))
        if b_mean > 1.25 * r_mean and g_mean > 1.15 * r_mean:
            avg_c = (b_mean + g_mean + r_mean) / 3.0
            bgr_wb = bgr.astype(np.float32)
            bgr_wb[:, :, 0] *= (0.75 * avg_c / max(1.0, b_mean) + 0.25)
            bgr_wb[:, :, 1] *= (0.75 * avg_c / max(1.0, g_mean) + 0.25)
            bgr_wb[:, :, 2] *= (0.75 * avg_c / max(1.0, r_mean) + 0.25)
            bgr = np.clip(bgr_wb, 0, 255).astype(np.uint8)
        bgr_clean[fg_bool] = bgr[fg_bool]

    bgra = np.dstack([bgr_clean, alpha])

    # Xoay căn phẳng trục chính PCA nếu thân cá bị nghiêng (> 3.5 độ) và đưa về kích thước chuẩn 440px trên khung 500x500
    ys, xs = np.where(fg_bool)
    if len(xs) > 25:
        m = cv2.moments((alpha > 128).astype(np.uint8))
        if abs(m["mu20"] - m["mu02"]) > 1e-3:
            angle_rad = 0.5 * np.arctan2(2.0 * m["mu11"], m["mu20"] - m["mu02"])
            angle_deg = float(np.degrees(angle_rad))
            if 3.5 < abs(angle_deg) < 42.0:
                cx = float(m["m10"] / max(1.0, m["m00"]))
                cy = float(m["m01"] / max(1.0, m["m00"]))
                rot_mat = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
                bgra = cv2.warpAffine(
                    bgra,
                    rot_mat,
                    (w0, h0),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=(0, 0, 0, 0),
                )
                bgra[:, :, 3] = np.where(bgra[:, :, 3] > 128, 255, 0).astype(np.uint8)
                fg_bool = bgra[:, :, 3] > 128
                bgra[:, :, :3][~fg_bool] = 0
                ys, xs = np.where(fg_bool)

    if len(xs) > 10:
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        crop = bgra[y1 : y2 + 1, x1 : x2 + 1]
        ch, cw = crop.shape[:2]
        max_span = int(target_size * 0.88)  # Chuẩn 440px trên canvas 500x500 của dataset_gold_v3
        scale = float(max_span) / float(max(ch, cw))
        nw = max(1, int(round(cw * scale)))
        nh = max(1, int(round(ch * scale)))
        resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
        resized[:, :, 3] = np.where(resized[:, :, 3] > 128, 255, 0).astype(np.uint8)
        resized[:, :, :3][resized[:, :, 3] <= 128] = 0
        canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)
        x_off = (target_size - nw) // 2
        y_off = (target_size - nh) // 2
        canvas[y_off : y_off + nh, x_off : x_off + nw] = resized
        bgra = canvas
    elif h0 != target_size or w0 != target_size:
        bgra = cv2.resize(bgra, (target_size, target_size), interpolation=cv2.INTER_AREA)

    return bgra


def render_query_preview_base64(img_bgra: np.ndarray, bbox: tuple, main_axis_angle_deg: float = 0.0) -> str:
    """
    Vẽ ảnh minh họa trực quan cho ảnh truy vấn:
    - Nền đen sạch, đường viền contour xanh lá quanh thân cá
    - Hộp giới hạn tối thiểu MBB [XLB, XUB, YLB, YUB] màu vàng cam
    - Đường chia 6 vùng giải phẫu (3 cột Đầu/Thân/Đuôi x 2 hàng Lưng/Bụng) nét đứt mảnh
    Trả về chuỗi data URI base64 PNG để hiển thị trực tiếp trên giao diện Web.
    """
    vis = img_bgra[:, :, :3].copy()
    mask = (img_bgra[:, :, 3] > 128).astype(np.uint8)
    xlb, xub, ylb, yub = bbox

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, contours, -1, (80, 230, 100), 1)

    # Đường chia 6 vùng giải phẫu C3
    w = max(1, xub - xlb + 1)
    h = max(1, yub - ylb + 1)
    x_head = int(xlb + 0.25 * w)
    x_tail = int(xlb + 0.75 * w)
    y_mid = int(ylb + 0.50 * h)

    cv2.line(vis, (x_head, ylb), (x_head, yub), (180, 180, 70), 1, cv2.LINE_AA)
    cv2.line(vis, (x_tail, ylb), (x_tail, yub), (180, 180, 70), 1, cv2.LINE_AA)
    cv2.line(vis, (xlb, y_mid), (xub, y_mid), (180, 180, 70), 1, cv2.LINE_AA)

    # Hộp bao MBB
    cv2.rectangle(vis, (xlb, ylb), (xub, yub), (0, 200, 255), 2)
    cv2.putText(
        vis,
        f"MBB [{xlb}..{xub}, {ylb}..{yub}] ({w}x{h}px)",
        (max(8, xlb), max(22, ylb - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (0, 215, 255),
        1,
        cv2.LINE_AA,
    )

    ok, buf = cv2.imencode(".png", vis)
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


class FishCBIRSearchEngine:
    """
    Bộ máy Tìm kiếm Ảnh cá Tương đồng (CBIR Engine):
    Nạp trực tiếp dữ liệu từ 6 bảng trong data/fish_multimedia.db và chỉ mục data/ball_tree_index.pkl.
    """

    def __init__(self, db_path: str = "data/fish_multimedia.db", index_path: str = "data/ball_tree_index.pkl"):
        self.db_path = db_path
        self.index_path = index_path
        self._load_database_and_index()

    def _load_database_and_index(self):
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Không tìm thấy CSDL tại {self.db_path}. Hãy chạy `python src/db.py` trước.")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Nạp Feature_Schema (421 chiều)
        schema_rows = cur.execute("SELECT * FROM Feature_Schema ORDER BY dim_index ASC").fetchall()
        self.feature_schema = [dict(r) for r in schema_rows]
        self.feature_names = [r["feature_name"] for r in self.feature_schema]
        self.dims = len(self.feature_schema)

        # 2. Nạp Normalization_Stats (421 chiều)
        # Đồng bộ quy tắc xử lý độ lệch chuẩn với evaluate.py & db.py:
        # sd < 1e-6 -> 1.0 (chiều bất biến có Z = 0), các chiều gần hằng số đặt sàn 2e-3 (0.002).
        norm_rows = cur.execute("SELECT * FROM Normalization_Stats ORDER BY dim_index ASC").fetchall()
        self.norm_stats = [dict(r) for r in norm_rows]
        self.mean_vec = np.array([r["mean_val"] for r in self.norm_stats], dtype=np.float64)
        raw_sd = np.array([float(r["std_val"]) for r in self.norm_stats], dtype=np.float64)
        self.std_vec = np.where(raw_sd < 1e-6, 1.0, np.maximum(raw_sd, 2e-3))

        self.component_medians = {}
        self.group_medians = {}
        for r in self.norm_stats:
            d_idx = int(r["dim_index"])
            comp_code = self.feature_schema[d_idx]["component_code"]
            grp_code = self.feature_schema[d_idx]["feature_group"]
            self.component_medians[comp_code] = float(r["component_median_d"])
            self.group_medians[grp_code] = float(r["group_median_d"])

        # 3. Nạp CBIR_System_Config (5 bản ghi cấu hình + Ma trận A_78x78)
        cfg_rows = cur.execute("SELECT * FROM CBIR_System_Config").fetchall()
        self.system_config = {}
        self.c1_sim_matrix_A = None
        for r in cfg_rows:
            k = r["config_key"]
            self.system_config[k] = json.loads(r["config_value_json"])
            if k == "c1_perceptual_matrix_A" and r["matrix_blob"] is not None:
                self.c1_sim_matrix_A = np.frombuffer(r["matrix_blob"], dtype=np.float32).reshape(78, 78).astype(np.float64)

        dw = self.system_config.get("default_weights", {"color": 0.4, "shape": 0.5, "texture": 0.1})
        self.default_weights = (float(dw["color"]), float(dw["shape"]), float(dw["texture"]))
        self.novelty_threshold = float(
            self.system_config.get("novelty_detection", {}).get("youden_threshold", 0.500)
        )

        # 4. Nạp JOIN 3 bảng thực thể: Fish_Metadata + Shape_Binary_Index + Fish_Feature_Vector (1.100 bản ghi)
        rows = cur.execute(
            """
            SELECT m.image_id, m.species, m.file_name, m.file_path,
                   m.xlb, m.xub, m.ylb, m.yub, m.width, m.height,
                   m.aspect_ratio, m.fg_area, m.main_axis_angle_deg,
                   b.grid64_blob, b.grid64_hex, b.grid64_popcount,
                   b.grid192_blob, b.grid192_hex, b.grid192_popcount,
                   v.color_vector, v.shape_vector, v.texture_vector, v.full_vector
            FROM Fish_Metadata m
            JOIN Shape_Binary_Index b ON m.image_id = b.image_id
            JOIN Fish_Feature_Vector v ON m.image_id = v.image_id
            ORDER BY m.image_id ASC
            """
        ).fetchall()
        conn.close()

        self.n_images = len(rows)
        self.records = []
        self.image_id_to_idx = {}
        self.file_to_idx = {}

        X_full_list = []
        bits64_list = []
        bits192_list = []

        for idx, r in enumerate(rows):
            img_id = r["image_id"]
            sp = r["species"]
            fname = r["file_name"]
            fpath = r["file_path"]
            # Đường dẫn ảnh nền đen tương ứng trong dataset_gold_v3
            base_no_ext = os.path.splitext(fname)[0]
            black_v3 = f"dataset_gold_v3/images_black/{sp}/{base_no_ext}.jpg"
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            black_exists = os.path.exists(black_v3) or os.path.exists(os.path.join(root_dir, black_v3))
            black_path = black_v3 if black_exists else fpath

            full_vec = np.frombuffer(r["full_vector"], dtype=np.float32)
            b64_arr = np.frombuffer(r["grid64_blob"], dtype=np.uint8)
            b192_arr = np.frombuffer(r["grid192_blob"], dtype=np.uint8)

            X_full_list.append(full_vec)
            bits64_list.append(np.unpackbits(b64_arr))
            bits192_list.append(np.unpackbits(b192_arr))

            self.image_id_to_idx[img_id] = idx
            self.file_to_idx[fname] = idx

            self.records.append(
                {
                    "index": idx,
                    "image_id": img_id,
                    "species": sp,
                    "species_vi": SPECIES_INFO.get(sp, {}).get("vi_name", sp),
                    "species_latin": SPECIES_INFO.get(sp, {}).get("latin_name", ""),
                    "file_name": fname,
                    "file_path": fpath,
                    "black_file_path": black_path,
                    "xlb": int(r["xlb"]),
                    "xub": int(r["xub"]),
                    "ylb": int(r["ylb"]),
                    "yub": int(r["yub"]),
                    "width": int(r["width"]),
                    "height": int(r["height"]),
                    "aspect_ratio": round(float(r["aspect_ratio"]), 4),
                    "fg_area": int(r["fg_area"]),
                    "main_axis_angle_deg": round(float(r["main_axis_angle_deg"]), 2),
                    "grid64_hex": r["grid64_hex"],
                    "grid64_popcount": int(r["grid64_popcount"]),
                    "grid192_hex": r["grid192_hex"],
                    "grid192_popcount": int(r["grid192_popcount"]),
                }
            )

        self.X_raw = np.array(X_full_list, dtype=np.float64)
        self.X_zscore = (self.X_raw - self.mean_vec) / self.std_vec
        z_norms = np.maximum(1e-9, np.linalg.norm(self.X_zscore, axis=1, keepdims=True))
        self.X_zscore_unit = self.X_zscore / z_norms
        self.bits64 = np.array(bits64_list, dtype=np.int16)    # (1100, 64)
        self.bits192 = np.array(bits192_list, dtype=np.int16)  # (1100, 192)
        self.species_arr = np.array([r["species"] for r in self.records])
        self._mode_medians_cache = {
            ("hybrid_2level", False): (self.component_medians.copy(), self.group_medians.copy())
        }

        # Nạp Ball-Tree Index
        self.ball_tree = None
        if os.path.exists(self.index_path):
            with open(self.index_path, "rb") as f:
                bundle = pickle.load(f)
                self.ball_tree = bundle.get("ball_tree", None)

        # Nạp danh sách cặp ảnh gần trùng (near_duplicates.json)
        self.near_duplicates = {}
        nd_path = "data/near_duplicates.json"
        if not os.path.exists(nd_path):
            nd_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), nd_path)
        if os.path.exists(nd_path):
            with open(nd_path, "r", encoding="utf-8") as f:
                nd = json.load(f)
                self.near_duplicates = {int(k): set(v) for k, v in nd.items() if str(k).isdigit()}

    def get_db_summary(self) -> dict:
        """Trả về thông tin tổng quan 6 bảng CSDL SQLite để hiển thị và kiểm tra."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        tables = ["Fish_Metadata", "Shape_Binary_Index", "Fish_Feature_Vector", "Feature_Schema", "Normalization_Stats", "CBIR_System_Config"]
        table_counts = {}
        for t in tables:
            table_counts[t] = int(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

        species_counts = {}
        for sp, cnt in cur.execute("SELECT species, COUNT(*) FROM Fish_Metadata GROUP BY species ORDER BY species").fetchall():
            species_counts[sp] = int(cnt)
        conn.close()

        return {
            "db_path": self.db_path,
            "db_size_mb": round(os.path.getsize(self.db_path) / (1024 * 1024), 2),
            "index_path": self.index_path,
            "index_size_mb": round(os.path.getsize(self.index_path) / (1024 * 1024), 2) if os.path.exists(self.index_path) else 0.0,
            "total_images": self.n_images,
            "total_dimensions": self.dims,
            "table_counts": table_counts,
            "species_counts": species_counts,
            "species_info": SPECIES_INFO,
            "default_weights": {
                "color": self.default_weights[0],
                "shape": self.default_weights[1],
                "texture": self.default_weights[2],
            },
            "novelty_threshold": self.novelty_threshold,
            "component_medians": {k: round(v, 4) for k, v in self.component_medians.items()},
            "group_medians": {k: round(v, 4) for k, v in self.group_medians.items()},
        }

    def get_table_preview(self, table_name: str = "Fish_Metadata", limit: int = 15, species_filter: str = None) -> list:
        """Lấy các bản ghi mẫu từ 1 trong 6 bảng của SQLite để minh họa quản trị CSDL Phần 3."""
        valid_tables = {
            "Fish_Metadata",
            "Shape_Binary_Index",
            "Fish_Feature_Vector",
            "Feature_Schema",
            "Normalization_Stats",
            "CBIR_System_Config",
        }
        if table_name not in valid_tables:
            raise ValueError(f"Bảng không hợp lệ: {table_name}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if table_name in ("Fish_Metadata", "Shape_Binary_Index", "Fish_Feature_Vector") and species_filter:
            rows = cur.execute(f"SELECT * FROM {table_name} WHERE species = ? LIMIT ?", (species_filter, limit)).fetchall()
        elif table_name == "Normalization_Stats":
            rows = cur.execute(
                """
                SELECT s.dim_index, f.feature_name, f.feature_group, f.component_code, f.distance_metric,
                       ROUND(s.mean_val, 4) AS mean_val, ROUND(s.std_val, 4) AS std_val,
                       ROUND(s.component_median_d, 4) AS component_median_d,
                       ROUND(s.group_median_d, 4) AS group_median_d,
                       ROUND(s.cv_within, 4) AS cv_within, ROUND(s.fisher_j, 4) AS fisher_j,
                       ROUND(s.f_anova, 2) AS f_anova, ROUND(s.eta_squared, 4) AS eta_squared,
                       ROUND(s.mutual_info_bits, 4) AS mutual_info_bits, s.primary_role
                FROM Normalization_Stats s
                JOIN Feature_Schema f ON s.dim_index = f.dim_index
                ORDER BY s.fisher_j DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = cur.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,)).fetchall()
        conn.close()

        out = []
        for r in rows:
            d = {}
            for k in r.keys():
                val = r[k]
                if isinstance(val, (bytes, bytearray)):
                    arr = np.frombuffer(val, dtype=np.float32) if len(val) >= 32 else np.frombuffer(val, dtype=np.uint8)
                    if arr.dtype == np.float32:
                        preview_vals = ", ".join(f"{x:.3f}" for x in arr[:4])
                        d[k] = f"<BLOB {len(val)}B | {len(arr)}xfloat32: [{preview_vals}, ...]>"
                    else:
                        d[k] = f"<BLOB {len(val)}B: 0x{val.hex()[:16]}...>"
                elif isinstance(val, float):
                    d[k] = round(val, 4)
                else:
                    d[k] = val
            out.append(d)
        return out

    def _get_mode_medians(self, metric_mode: str = "hybrid_2level", use_quadratic_color: bool = False) -> tuple:
        """
        Trả về bộ trung vị thành phần (comp_meds) và trung vị nhóm (group_meds) tương ứng
        chính xác với chế độ độ đo (metric_mode) và tùy chọn ma trận màu chéo bin (use_quadratic_color),
        đảm bảo khoảng cách hợp nhất D_total luôn nằm trên cùng một thang đo chuẩn hóa.
        """
        key = (metric_mode, bool(use_quadratic_color))
        if key in self._mode_medians_cache:
            return self._mode_medians_cache[key]

        from scipy.spatial.distance import cdist

        n = self.n_images
        off_diag = ~np.eye(n, dtype=bool)
        comp_meds = {}
        norm_comp_mats = {}

        for comp, (st, en, kind, _, _) in COMPONENTS.items():
            sub_raw = self.X_raw[:, st:en]
            sub_z = self.X_zscore[:, st:en]

            if comp == "C1" and use_quadratic_color and self.c1_sim_matrix_A is not None:
                XA = sub_raw @ self.c1_sim_matrix_A
                q_diag = np.sum(XA * sub_raw, axis=1)
                quad_sq = np.maximum(0.0, q_diag[:, None] + q_diag[None, :] - 2.0 * (XA @ sub_raw.T))
                D_m = np.sqrt(quad_sq)
            elif metric_mode == "hybrid_2level":
                D_m = cdist(sub_raw, sub_raw, metric="cityblock") if kind == "hist" else cdist(sub_z, sub_z, metric="euclidean")
            elif metric_mode == "l1_manhattan":
                D_m = cdist(sub_raw, sub_raw, metric="cityblock") if kind == "hist" else cdist(sub_z, sub_z, metric="cityblock")
            elif metric_mode == "l2_euclidean":
                D_m = cdist(sub_raw, sub_raw, metric="euclidean") if kind == "hist" else cdist(sub_z, sub_z, metric="euclidean")
            elif metric_mode == "cosine":
                use_mat = sub_raw if kind == "hist" else sub_z
                norms = np.maximum(1e-9, np.linalg.norm(use_mat, axis=1, keepdims=True))
                unit_mat = use_mat / norms
                D_m = np.clip(1.0 - (unit_mat @ unit_mat.T), 0.0, 2.0)
            else:
                raise ValueError(f"Chế độ độ đo không hợp lệ: {metric_mode}")

            med_val = float(np.median(D_m[off_diag]))
            med_val = med_val if med_val > 1e-9 else 1.0
            comp_meds[comp] = med_val
            if metric_mode == "cosine" and not (comp == "C1" and use_quadratic_color and self.c1_sim_matrix_A is not None):
                # Chuyển khoảng cách Cosine bậc hai (1 - cos(theta) ~ theta^2 / 2) về thang đo dây cung bậc nhất
                # sqrt((1 - cos(theta)) / med_m) để đồng nhất tuyến tính với L1, L2 và ngưỡng phát hiện loài mới
                norm_comp_mats[comp] = np.sqrt(D_m / med_val)
            else:
                norm_comp_mats[comp] = D_m / med_val

        group_meds = {}
        for grp, members in GROUPS.items():
            D_grp = sum(norm_comp_mats[m] for m in members)
            med_g = float(np.median(D_grp[off_diag]))
            group_meds[grp] = med_g if med_g > 1e-9 else 1.0

        self._mode_medians_cache[key] = (comp_meds, group_meds)
        return comp_meds, group_meds

    def _compute_component_distances_for_query(
        self,
        q_raw: np.ndarray,
        q_zscore: np.ndarray,
        cand_indices: np.ndarray,
        metric_mode: str = "hybrid_2level",
        use_quadratic_color: bool = False,
    ) -> dict:
        """
        Tính khoảng cách của từng thành phần trong 12 thành phần (C1..T4) giữa vector truy vấn Q
        và tập ứng viên cand_indices trong CSDL.
        Trả về dict: {comp_code: mảng khoảng cách đã chia trung vị thành phần med_m}
        và raw_comp_dists: {comp_code: mảng khoảng cách trước khi chia med_m}.
        """
        norm_comp_dists = {}
        raw_comp_dists = {}
        active_comp_meds, _ = self._get_mode_medians(metric_mode, use_quadratic_color)

        X_cand_raw = self.X_raw[cand_indices]
        X_cand_z = self.X_zscore[cand_indices]

        for comp, (st, en, kind, _, _) in COMPONENTS.items():
            q_sub_raw = q_raw[st:en]
            q_sub_z = q_zscore[st:en]
            c_sub_raw = X_cand_raw[:, st:en]
            c_sub_z = X_cand_z[:, st:en]

            if comp == "C1" and use_quadratic_color and self.c1_sim_matrix_A is not None:
                # Khoảng cách toàn phương chéo bin (Quadratic Form Distance - Lecture 11 Slide 19):
                # D_quad(q, c) = sqrt((q - c)^T * A * (q - c))
                diff = c_sub_raw - q_sub_raw[None, :]  # (M, 78)
                quad = np.einsum("mi,ij,mj->m", diff, self.c1_sim_matrix_A, diff)
                d_vec = np.sqrt(np.maximum(0.0, quad))
            elif metric_mode == "hybrid_2level":
                if kind == "hist":
                    d_vec = np.abs(c_sub_raw - q_sub_raw[None, :]).sum(axis=1)
                else:
                    z_diff = np.clip(c_sub_z - q_sub_z[None, :], -6.0, 6.0)
                    d_vec = np.sqrt((z_diff ** 2).sum(axis=1))
            elif metric_mode == "l1_manhattan":
                if kind == "hist":
                    d_vec = np.abs(c_sub_raw - q_sub_raw[None, :]).sum(axis=1)
                else:
                    z_diff = np.clip(c_sub_z - q_sub_z[None, :], -6.0, 6.0)
                    d_vec = np.abs(z_diff).sum(axis=1)
            elif metric_mode == "l2_euclidean":
                if kind == "hist":
                    d_vec = np.sqrt(((c_sub_raw - q_sub_raw[None, :]) ** 2).sum(axis=1))
                else:
                    z_diff = np.clip(c_sub_z - q_sub_z[None, :], -6.0, 6.0)
                    d_vec = np.sqrt((z_diff ** 2).sum(axis=1))
            elif metric_mode == "cosine":
                # Khoảng cách Cosine = 1 - CosineSimilarity
                use_mat = c_sub_raw if kind == "hist" else c_sub_z
                use_q = q_sub_raw if kind == "hist" else q_sub_z
                q_norm = float(np.linalg.norm(use_q))
                c_norms = np.linalg.norm(use_mat, axis=1)
                denom = np.maximum(1e-9, q_norm * c_norms)
                cos_sim = (use_mat @ use_q) / denom
                d_vec = np.clip(1.0 - cos_sim, 0.0, 2.0)
            else:
                raise ValueError(f"Chế độ độ đo không hợp lệ: {metric_mode}")

            raw_comp_dists[comp] = d_vec
            med_m = active_comp_meds.get(comp, 1.0)
            if metric_mode == "cosine" and not (comp == "C1" and use_quadratic_color and self.c1_sim_matrix_A is not None):
                norm_comp_dists[comp] = np.sqrt(d_vec / max(1e-9, med_m))
            else:
                norm_comp_dists[comp] = d_vec / max(1e-9, med_m)

        return norm_comp_dists, raw_comp_dists

    def _build_intermediate_feature_breakdown(
        self,
        res: dict,
        q_zscore: np.ndarray,
        metric_mode: str = "hybrid_2level",
        use_quadratic_color: bool = False,
    ) -> dict:
        """
        Trích xuất bảng kết quả trung gian cực kỳ trực quan của ảnh truy vấn Q (Phục vụ Yêu cầu 4b):
        - Giá trị thực tế của 12 thành phần
        - Biểu đồ 6 bin vô sắc + 12 bin Hue của C1
        - 9 mô-men màu CIE Lab (C2)
        - 8 chỉ số hình thái học cơ thể (S1)
        - 16 lát cắt sống lưng & 16 lát cắt lườn bụng (S2)
        - 7 mô-men bất biến Hu (S3)
        - Ma trận lưới 8x8 liên tục và nhị phân 64-bit (S5)
        - 3 chỉ số độ thô Tamura (T3) & Năng lượng Gabor (T4)
        """
        vec = res["full_vector"].astype(np.float64)
        active_comp_meds, _ = self._get_mode_medians(metric_mode, use_quadratic_color)

        # 1. Tóm tắt 12 thành phần
        component_summaries = []
        for comp, (st, en, kind, grp, desc) in COMPONENTS.items():
            sub_raw = vec[st:en]
            sub_z = q_zscore[st:en]
            if comp == "C1" and use_quadratic_color:
                m_type = "Quadratic A (78x78)"
            elif metric_mode == "hybrid_2level":
                m_type = "L1 (Histogram)" if kind == "hist" else "Z-Score + L2"
            elif metric_mode == "l1_manhattan":
                m_type = "L1 (Histogram)" if kind == "hist" else "Z-Score + L1"
            elif metric_mode == "l2_euclidean":
                m_type = "L2 (Histogram)" if kind == "hist" else "Z-Score + L2"
            else:
                m_type = "Cosine (Histogram)" if kind == "hist" else "Z-Score + Cosine"
            component_summaries.append(
                {
                    "code": comp,
                    "group": grp,
                    "description": desc,
                    "dims": int(en - st),
                    "range": f"[{st}..{en-1}]",
                    "metric_type": m_type,
                    "component_median": round(active_comp_meds.get(comp, 1.0), 4),
                    "raw_min": round(float(np.min(sub_raw)), 4),
                    "raw_max": round(float(np.max(sub_raw)), 4),
                    "raw_mean": round(float(np.mean(sub_raw)), 4),
                    "raw_l2_norm": round(float(np.linalg.norm(sub_raw)), 4),
                    "sample_raw_values": [round(float(x), 4) for x in sub_raw[:6]],
                    "sample_z_values": [round(float(x), 4) for x in sub_z[:6]],
                }
            )

        # 2. C1: Tóm tắt 6 bin vô sắc + 12 góc màu Hue (mỗi góc gộp 3 Sat x 2 Val = 6 bin)
        c1_vec = vec[0:78]
        achromatic_6 = [round(float(x), 4) for x in c1_vec[:6]]
        chromatic_72 = c1_vec[6:78].reshape(12, 6)
        hue_12_bins = [round(float(x), 4) for x in chromatic_72.sum(axis=1)]
        hue_labels = [f"{i*30}°-{(i+1)*30}°" for i in range(12)]

        # 3. C2: 9 mô-men CIE Lab
        c2_vec = vec[78:87]
        c2_dict = {
            "L_mean": round(float(c2_vec[0]), 4),
            "L_std": round(float(c2_vec[1]), 4),
            "L_skew": round(float(c2_vec[2]), 4),
            "a_mean": round(float(c2_vec[3]), 4),
            "a_std": round(float(c2_vec[4]), 4),
            "a_skew": round(float(c2_vec[5]), 4),
            "b_mean": round(float(c2_vec[6]), 4),
            "b_std": round(float(c2_vec[7]), 4),
            "b_skew": round(float(c2_vec[8]), 4),
        }

        # 4. S1: 8 chỉ số hình thái học
        s1_vec = vec[135:143]
        s1_names = [
            ("aspect_ratio", "Tỷ lệ khung bao (AR = W/H)"),
            ("circularity", "Độ tròn (4πA/P²)"),
            ("solidity", "Độ đặc bao lồi (A/A_hull)"),
            ("extent", "Độ lấp đầy hộp bao (A/(W·H))"),
            ("eccentricity", "Tâm sai elip (Eccentricity)"),
            ("convexity", "Độ lồi chu vi (P_hull/P)"),
            ("rectangularity", "Độ chữ nhật xoay (A/A_rect)"),
            ("eq_diam_ratio", "Tỷ lệ đường kính tương đương"),
        ]
        s1_list = [
            {"key": k, "label": lbl, "value": round(float(s1_vec[i]), 4), "z_value": round(float(q_zscore[135 + i]), 4)}
            for i, (k, lbl) in enumerate(s1_names)
        ]

        # 5. S2: 16 lát cắt sống lưng & 16 lát cắt lườn bụng
        s2_vec = vec[143:175]
        dorsal_16 = [round(float(x), 4) for x in s2_vec[:16]]
        ventral_16 = [round(float(x), 4) for x in s2_vec[16:32]]

        # 6. S3: 7 mô-men bất biến Hu
        s3_vec = [round(float(x), 4) for x in vec[175:182]]

        # 7. S5: Ma trận 8x8 liên tục và nhị phân ngưỡng 15%
        s5_vec = vec[211:275].reshape(8, 8)
        s5_continuous_grid = [[round(float(val), 3) for val in row] for row in s5_vec]
        s5_binary_grid = [[1 if val >= 0.15 else 0 for val in row] for row in s5_vec]

        # 8. T3: 3 chỉ số độ thô Tamura (kèm Z-score)
        t3_vec = vec[394:397]
        t3_z = q_zscore[394:397]
        t3_dict = {
            "coarseness": round(float(t3_vec[0]), 4),
            "contrast": round(float(t3_vec[1]), 4),
            "directionality": round(float(t3_vec[2]), 4),
            "coarseness_z": round(float(t3_z[0]), 4),
            "contrast_z": round(float(t3_z[1]), 4),
            "directionality_z": round(float(t3_z[2]), 4),
        }

        return {
            "component_summaries": component_summaries,
            "c1_distribution": {
                "achromatic_ratio": round(float(np.sum(c1_vec[:6])), 4),
                "chromatic_ratio": round(float(np.sum(c1_vec[6:])), 4),
                "achromatic_6_bins": achromatic_6,
                "hue_12_bins": hue_12_bins,
                "hue_labels": hue_labels,
            },
            "c2_lab_moments": c2_dict,
            "s1_morphometrics": s1_list,
            "s2_profile": {
                "slice_labels": [f"Lát {i+1}" for i in range(16)],
                "dorsal_16": dorsal_16,
                "ventral_16": ventral_16,
            },
            "s3_hu_moments": s3_vec,
            "s5_grids": {
                "continuous_8x8": s5_continuous_grid,
                "binary_8x8_15pct": s5_binary_grid,
            },
            "t3_tamura": t3_dict,
        }

    def search(
        self,
        img_bgra_or_bgr: np.ndarray,
        query_label_name: str = "query_image.png",
        top_k: int = 5,
        metric_mode: str = "hybrid_2level",
        weights: tuple = None,
        coarse_filter_mode: str = "none",
        coarse_candidates: int = 200,
        use_quadratic_color: bool = False,
        exclude_exact_self: bool = False,
        exclude_near_duplicates_of_idx: int = None,
        simulate_unknown_species: str = None,
        diversify_top_k: bool = True,
        is_in_dataset_sample: bool = False,
    ) -> dict:
        """
        Thực hiện toàn bộ Pipeline Truy vấn CBIR cho 1 bức ảnh đầu vào và trả về Top-K kèm kết quả trung gian.
        """
        t_start = time.perf_counter()

        # Bước 1: Tiền xử lý chuẩn hóa mặt nạ thân cá (500x500 BGRA)
        img_bgra = segment_and_standardize_any_image(img_bgra_or_bgr, target_size=500)
        if img_bgra is None:
            raise ValueError("Không đọc được ảnh đầu vào.")

        res = process_single_image(img_bgra)
        if res is None:
            raise ValueError("Không phát hiện được vùng thân cá hợp lệ (diện tích < 50 pixel) trong ảnh đầu vào.")

        q_raw = res["full_vector"].astype(np.float64)
        q_raw = np.nan_to_num(q_raw, nan=0.0, posinf=1.0, neginf=0.0)
        q_zscore = (q_raw - self.mean_vec) / self.std_vec

        q_bits64 = np.unpackbits(res["grid64_bytes8"]).astype(np.int16)
        q_bits192 = np.unpackbits(res["grid192_bytes24"]).astype(np.int16)

        t_extract_ms = (time.perf_counter() - t_start) * 1000.0
        t_search_start = time.perf_counter()

        # Chuẩn hóa bộ trọng số (w_color, w_shape, w_texture)
        if weights is None:
            w_c, w_s, w_t = self.default_weights
        else:
            w_c, w_s, w_t = float(weights[0]), float(weights[1]), float(weights[2])
        w_sum = w_c + w_s + w_t
        if w_sum <= 1e-9:
            w_c, w_s, w_t = self.default_weights
        else:
            w_c, w_s, w_t = w_c / w_sum, w_s / w_sum, w_t / w_sum

        # Tính khoảng cách Hamming trên toàn bộ 1.100 bản ghi trong Shape_Binary_Index
        hamming_64_all = (self.bits64 != q_bits64[None, :]).sum(axis=1)
        hamming_192_all = (self.bits192 != q_bits192[None, :]).sum(axis=1)

        # Nhận diện tự động nếu ảnh tải lên là một bản ghi thuộc bộ dữ liệu chuẩn (dù là .png, .jpg hay đã đổi tên file)
        matched_db_idx = None
        base_qname = os.path.basename(query_label_name) if query_label_name else ""
        stem_png = os.path.splitext(base_qname)[0] + ".png" if base_qname else ""
        if base_qname in self.file_to_idx:
            matched_db_idx = self.file_to_idx[base_qname]
        elif stem_png in self.file_to_idx:
            matched_db_idx = self.file_to_idx[stem_png]
        else:
            mean_abs_diffs = np.mean(np.abs(self.X_raw - q_raw[None, :]), axis=1)
            min_diff_idx = int(np.argmin(mean_abs_diffs))
            if float(mean_abs_diffs[min_diff_idx]) < 0.003:
                matched_db_idx = min_diff_idx

        if matched_db_idx is not None or simulate_unknown_species:
            is_in_dataset_sample = True
        if exclude_exact_self and exclude_near_duplicates_of_idx is None and matched_db_idx is not None:
            exclude_near_duplicates_of_idx = matched_db_idx

        # Bước 2: Lọc ứng viên (Coarse Filtering / Candidate Selection)
        valid_mask = np.ones(self.n_images, dtype=bool)
        if simulate_unknown_species:
            valid_mask &= (self.species_arr != simulate_unknown_species)

        if exclude_near_duplicates_of_idx is not None and 0 <= exclude_near_duplicates_of_idx < self.n_images:
            valid_mask[exclude_near_duplicates_of_idx] = False
            for dup_i in self.near_duplicates.get(exclude_near_duplicates_of_idx, set()):
                valid_mask[dup_i] = False

        valid_indices = np.where(valid_mask)[0]
        n_cand = min(len(valid_indices), max(top_k * 3, int(coarse_candidates)))

        if coarse_filter_mode == "grid64" and n_cand < len(valid_indices):
            h_sub = hamming_64_all[valid_indices]
            part = np.argpartition(h_sub, n_cand)[:n_cand]
            cand_indices = valid_indices[part]
        elif coarse_filter_mode == "grid192" and n_cand < len(valid_indices):
            h_sub = hamming_192_all[valid_indices]
            part = np.argpartition(h_sub, n_cand)[:n_cand]
            cand_indices = valid_indices[part]
        elif coarse_filter_mode == "ball_tree" and self.ball_tree is not None and n_cand < len(valid_indices):
            n_fetch = min(self.n_images, n_cand + int(np.sum(~valid_mask)) + 20)
            _, bt_idx = self.ball_tree.kneighbors(q_zscore.reshape(1, -1), n_neighbors=n_fetch)
            bt_cand = [int(i) for i in bt_idx[0] if valid_mask[int(i)]][:n_cand]
            cand_indices = np.array(bt_cand, dtype=int)
        else:
            cand_indices = valid_indices

        # Bước 3: Tính khoảng cách từng thành phần (C1..T4) và hợp nhất 2 cấp theo 3 Bộ (Color, Shape, Texture)
        norm_comp_dists, raw_comp_dists = self._compute_component_distances_for_query(
            q_raw=q_raw,
            q_zscore=q_zscore,
            cand_indices=cand_indices,
            metric_mode=metric_mode,
            use_quadratic_color=use_quadratic_color,
        )

        _, active_group_meds = self._get_mode_medians(metric_mode, use_quadratic_color)
        group_dists = {}
        for grp, members in GROUPS.items():
            d_grp_sum = sum(norm_comp_dists[m] for m in members)
            med_g = active_group_meds.get(grp, 1.0)
            group_dists[grp] = d_grp_sum / max(1e-9, med_g)

        total_dists = (
            w_c * group_dists["color"]
            + w_s * group_dists["shape"]
            + w_t * group_dists["texture"]
        )

        # Nếu người dùng bật exclude_exact_self (loại bỏ chính ảnh đó nếu khoảng cách ~ 0)
        if exclude_exact_self:
            exact_mask = total_dists < 1e-6
            total_dists = np.where(exact_mask, np.inf, total_dists)

        # Bước 4: Xếp hạng và trích xuất Top-K (hỗ trợ khử ảnh chụp liên tiếp cùng 1 cá thể diversify_top_k)
        k_actual = min(top_k, len(cand_indices))
        sorted_all_local = np.argsort(total_dists)

        # Khoảng cách gần nhất tới ảnh khác (d > 1e-6) trước khi khử trùng lặp cá thể để kiểm tra loài cá mới
        non_zero_raw = [float(total_dists[idx_l]) for idx_l in sorted_all_local[:15] if 1e-6 < total_dists[idx_l] < np.inf]
        d_min_effective = non_zero_raw[0] if non_zero_raw else (float(total_dists[sorted_all_local[0]]) if len(sorted_all_local) > 0 else 999.0)

        order_local = []
        picked_db_indices = []
        for local_i in sorted_all_local:
            if total_dists[local_i] == np.inf:
                break
            db_idx = int(cand_indices[local_i])
            if diversify_top_k and len(picked_db_indices) > 0:
                is_burst_clone = False
                u_cand = self.X_zscore_unit[db_idx]
                for prev_db_idx in picked_db_indices:
                    if db_idx in self.near_duplicates.get(prev_db_idx, set()):
                        is_burst_clone = True
                        break
                    # Nếu hai ảnh trong DB có độ tương đồng Cosine trên không gian Z-score >= 0.70,
                    # chúng là các khung hình chụp liên tiếp (burst-shot) của cùng một cá thể cá ngoài thực tế
                    if float(np.dot(u_cand, self.X_zscore_unit[prev_db_idx])) >= 0.70:
                        is_burst_clone = True
                        break
                if is_burst_clone:
                    continue
            order_local.append(local_i)
            picked_db_indices.append(db_idx)
            if len(order_local) >= k_actual:
                break

        if len(order_local) < k_actual:
            for local_i in sorted_all_local:
                if local_i not in order_local and total_dists[local_i] < np.inf:
                    order_local.append(local_i)
                    if len(order_local) >= k_actual:
                        break

        top_results = []
        for rank_idx, local_i in enumerate(order_local, start=1):
            db_idx = int(cand_indices[local_i])
            rec = self.records[db_idx]
            d_tot = float(total_dists[local_i])
            d_col = float(group_dists["color"][local_i])
            d_shp = float(group_dists["shape"][local_i])
            d_tex = float(group_dists["texture"][local_i])

            # Quy đổi khoảng cách đã chuẩn hóa trung vị về % độ tương đồng trực quan (0% -> 100%)
            # Với d_tot = 0 -> 100%; d_tot = 0.25 (cùng loài điển hình) -> ~80-90%
            sim_pct = float(100.0 / (1.0 + d_tot * 0.65))
            sim_color_pct = float(100.0 / (1.0 + d_col * 0.65))
            sim_shape_pct = float(100.0 / (1.0 + d_shp * 0.65))
            sim_tex_pct = float(100.0 / (1.0 + d_tex * 0.65))

            comp_breakdown = {}
            for comp in COMPONENTS:
                comp_breakdown[comp] = {
                    "raw_distance": round(float(raw_comp_dists[comp][local_i]), 4),
                    "normalized_distance": round(float(norm_comp_dists[comp][local_i]), 4),
                }

            cand_vec = self.X_raw[db_idx]
            top_results.append(
                {
                    "rank": rank_idx,
                    "image_id": rec["image_id"],
                    "species": rec["species"],
                    "species_vi": rec["species_vi"],
                    "species_latin": rec["species_latin"],
                    "file_name": rec["file_name"],
                    "file_path": rec["file_path"],
                    "black_file_path": rec["black_file_path"],
                    "total_distance": round(d_tot, 4),
                    "similarity_pct": round(sim_pct, 2),
                    "group_distances": {
                        "color": round(d_col, 4),
                        "shape": round(d_shp, 4),
                        "texture": round(d_tex, 4),
                    },
                    "group_similarities_pct": {
                        "color": round(sim_color_pct, 2),
                        "shape": round(sim_shape_pct, 2),
                        "texture": round(sim_tex_pct, 2),
                    },
                    "weighted_contributions": {
                        "color": round(w_c * d_col, 4),
                        "shape": round(w_s * d_shp, 4),
                        "texture": round(w_t * d_tex, 4),
                    },
                    "component_distances": comp_breakdown,
                    "hamming_64": int(hamming_64_all[db_idx]),
                    "hamming_192": int(hamming_192_all[db_idx]),
                    "grid64_hex": rec["grid64_hex"],
                    "grid192_hex": rec["grid192_hex"],
                    "bbox": [rec["xlb"], rec["xub"], rec["ylb"], rec["yub"]],
                    "aspect_ratio": rec["aspect_ratio"],
                    "fg_area": rec["fg_area"],
                    "morphometrics": {
                        "aspect_ratio": round(float(cand_vec[135]), 3),
                        "circularity": round(float(cand_vec[136]), 3),
                        "solidity": round(float(cand_vec[137]), 3),
                        "extent": round(float(cand_vec[138]), 3),
                        "eccentricity": round(float(cand_vec[139]), 3),
                        "convexity": round(float(cand_vec[140]), 3),
                        "rectangularity": round(float(cand_vec[141]), 3),
                        "eq_diam_ratio": round(float(cand_vec[142]), 3),
                    },
                }
            )

        t_search_ms = (time.perf_counter() - t_search_start) * 1000.0

        # Bước 5: Phân tích nhận dạng loài & Kiểm tra ngưỡng loài cá mới (Novelty Detection)
        # - Với ảnh mẫu nội bộ trong CSDL (cùng máy ảnh/ánh sáng phòng chụp): ngưỡng Youden nội bộ = 0.5417.
        # - Với ảnh chụp thực tế tải lên từ bên ngoài (khác máy ảnh, khác môi trường sáng - Domain Shift):
        #   ngưỡng phát hiện loài cá mới thực tế là 0.750 (hoặc +0.15 với độ đo Cosine trên mặt cầu đơn vị).
        if is_in_dataset_sample:
            effective_threshold = self.novelty_threshold
        elif metric_mode == "cosine":
            effective_threshold = self.novelty_threshold + 0.15
        else:
            effective_threshold = max(0.750, self.novelty_threshold + 0.20)
        is_novel = bool(d_min_effective > effective_threshold)

        # Bỏ phiếu đa số có trọng số nghịch đảo khoảng cách trong Top-5
        sp_votes = {}
        for r in top_results:
            sp = r["species"]
            vote_w = 1.0 / (0.1 + r["total_distance"])
            sp_votes[sp] = sp_votes.get(sp, 0.0) + vote_w
        predicted_sp = max(sp_votes.items(), key=lambda kv: kv[1])[0] if sp_votes else "unknown"
        top5_same_sp_count = sum(1 for r in top_results if r["species"] == predicted_sp)

        meta = res["metadata"]
        bbox_tuple = (meta["xlb"], meta["xub"], meta["ylb"], meta["yub"])
        preview_b64 = render_query_preview_base64(img_bgra, bbox_tuple, meta["main_axis_angle_deg"])

        return {
            "query_info": {
                "query_name": query_label_name,
                "xlb": meta["xlb"],
                "xub": meta["xub"],
                "ylb": meta["ylb"],
                "yub": meta["yub"],
                "width": meta["width"],
                "height": meta["height"],
                "aspect_ratio": round(float(meta["aspect_ratio"]), 4),
                "fg_area": meta["fg_area"],
                "main_axis_angle_deg": round(float(meta["main_axis_angle_deg"]), 2),
                "grid64_hex": meta["grid64_hex"],
                "grid64_popcount": meta["grid64_popcount"],
                "grid192_hex": meta["grid192_hex"],
                "grid192_popcount": meta["grid192_popcount"],
                "preview_image_base64": preview_b64,
            },
            "search_params": {
                "metric_mode": metric_mode,
                "use_quadratic_color": use_quadratic_color,
                "coarse_filter_mode": coarse_filter_mode,
                "weights": {"color": round(w_c, 3), "shape": round(w_s, 3), "texture": round(w_t, 3)},
                "exclude_exact_self": exclude_exact_self,
                "simulate_unknown_species": simulate_unknown_species,
            },
            "filtering_stats": {
                "total_db_records": self.n_images,
                "candidates_evaluated": len(cand_indices),
                "feature_extraction_ms": round(t_extract_ms, 2),
                "db_matching_ms": round(t_search_ms, 2),
                "total_latency_ms": round(t_extract_ms + t_search_ms, 2),
            },
            "novelty_analysis": {
                "nearest_non_identical_distance": round(float(d_min_effective), 4),
                "youden_threshold": round(float(effective_threshold), 4),
                "is_novel_species": is_novel,
                "status_label": (
                    "CẢNH BÁO: Có dấu hiệu thuộc LOÀI CÁ MỚI chưa có trong CSDL (Khoảng cách vượt ngưỡng)"
                    if is_novel
                    else f"Nhận diện tương đồng với loài trong CSDL: {SPECIES_INFO.get(predicted_sp, {}).get('vi_name', predicted_sp)} ({predicted_sp.upper()})"
                ),
                "predicted_species": predicted_sp,
                "predicted_species_vi": SPECIES_INFO.get(predicted_sp, {}).get("vi_name", predicted_sp),
                "predicted_species_latin": SPECIES_INFO.get(predicted_sp, {}).get("latin_name", ""),
                "top5_consensus_count": top5_same_sp_count,
            },
            "intermediate_features": self._build_intermediate_feature_breakdown(
                res, q_zscore, metric_mode=metric_mode, use_quadratic_color=use_quadratic_color
            ),
            "top_k_results": top_results,
        }

    def query_by_id(self, image_id: str, **kwargs) -> dict:
        if image_id not in self.image_id_to_idx:
            raise ValueError(f"Không tìm thấy image_id={image_id} trong CSDL.")
        idx = self.image_id_to_idx[image_id]
        rec = self.records[idx]
        fpath = rec["file_path"]
        if not os.path.exists(fpath):
            fpath = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), fpath)
        img = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
        kwargs.setdefault("is_in_dataset_sample", True)
        if kwargs.get("exclude_exact_self", False):
            kwargs.setdefault("exclude_near_duplicates_of_idx", idx)
        return self.search(img, query_label_name=f"{image_id} ({rec['file_name']})", **kwargs)

    def query_by_path(self, file_path: str, **kwargs) -> dict:
        fpath = file_path
        if not os.path.exists(fpath):
            fpath = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), fpath)
        img = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Không đọc được file ảnh tại: {file_path}")
        return self.search(img, query_label_name=os.path.basename(file_path), **kwargs)


def generate_sample_intermediate_report():
    """
    Chạy thử nghiệm 2 kịch bản truy vấn mẫu (1 ảnh thuộc loài đã có trong CSDL + 1 kịch bản loài cá mới chưa có trong CSDL)
    và xuất kết quả trung gian chi tiết ra data/sample_query_intermediate_results.json & data/sample_query_report.md
    để minh họa trực tiếp cho Phần 4b của Báo cáo.
    """
    engine = FishCBIRSearchEngine()
    print("=" * 80)
    print("KIỂM CHỨNG BỘ MÁY TÌM KIẾM CBIR & XUẤT KẾT QUẢ TRUNG GIAN (PHẦN 4B)")
    print("=" * 80)

    summary = engine.get_db_summary()
    print(f"- Đã kết nối CSDL: {summary['db_path']} ({summary['db_size_mb']} MB)")
    print(f"- Tổng số bản ghi ảnh cá: {summary['total_images']} | Số chiều đặc trưng: {summary['total_dimensions']}")
    print(f"- Số dòng trong 6 bảng: {summary['table_counts']}")

    # Kịch bản 1: Truy vấn ảnh cá thuộc loài đã có trong CSDL (rui_0651 - Cá trôi Ấn Độ)
    res_known = engine.query_by_id("rui_0651", top_k=5, exclude_exact_self=False)

    # Kịch bản 2: Truy vấn ảnh cá thuộc loài mới chưa có trong CSDL (Giả lập ẩn loài 'boal' khỏi CSDL khi truy vấn boal_0001)
    res_novel = engine.query_by_id(
        "boal_0001",
        top_k=5,
        exclude_exact_self=True,
        simulate_unknown_species="boal",
    )

    # Xuất JSON(bỏ chuỗi ảnh base64 dài để file JSON gọn đẹp)
    res_known_clean = json.loads(json.dumps(res_known))
    res_known_clean["query_info"].pop("preview_image_base64", None)
    res_novel_clean = json.loads(json.dumps(res_novel))
    res_novel_clean["query_info"].pop("preview_image_base64", None)

    out_json = "data/sample_query_intermediate_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "db_summary": summary,
                "scenario_1_known_species": res_known_clean,
                "scenario_2_novel_species": res_novel_clean,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # In bảng kết quả trung gian Kịch bản 1 ra console
    q1 = res_known["query_info"]
    print(f"\n[KỊCH BẢN 1] Ảnh truy vấn: {q1['query_name']}")
    print(f"  + Hộp bao MBB: [{q1['xlb']}..{q1['xub']}, {q1['ylb']}..{q1['yub']}] ({q1['width']}x{q1['height']} px), AR={q1['aspect_ratio']}, Diện tích={q1['fg_area']} px")
    print(f"  + Chữ ký nhị phân 64-bit (8x8):   0x{q1['grid64_hex']} (popcount={q1['grid64_popcount']}/64)")
    print(f"  + Chữ ký nhị phân 192-bit (12x16): 0x{q1['grid192_hex']} (popcount={q1['grid192_popcount']}/192)")
    print(f"  + Thời gian xử lý: Trích đặc trưng = {res_known['filtering_stats']['feature_extraction_ms']} ms | Tìm kiếm CSDL = {res_known['filtering_stats']['db_matching_ms']} ms")
    print(f"  + Kết luận: {res_known['novelty_analysis']['status_label']} (d_min = {res_known['novelty_analysis']['nearest_non_identical_distance']} <= ngưỡng {res_known['novelty_analysis']['youden_threshold']})")
    print("\n  Bảng Top-5 ảnh cá tương đồng nhất (Kịch bản 1):")
    print("  Hạng | Mã ảnh     | Loài    | D_color | D_shape | D_texture | D_total | Độ tương đồng | Hamming64")
    print("  " + "-" * 92)
    for r in res_known["top_k_results"]:
        gd = r["group_distances"]
        print(
            f"   #{r['rank']}  | {r['image_id']:10s} | {r['species']:7s} | "
            f"{gd['color']:7.4f} | {gd['shape']:7.4f} | {gd['texture']:9.4f} | "
            f"{r['total_distance']:7.4f} | {r['similarity_pct']:11.2f}% | {r['hamming_64']:9d}"
        )

    q2 = res_novel["query_info"]
    print(f"\n[KỊCH BẢN 2 - LOÀI CÁ MỚI CHƯA CÓ TRONG CSDL] Ảnh truy vấn: {q2['query_name']} (Đã ẩn loài 'boal' khỏi CSDL)")
    print(f"  + Kết luận: {res_novel['novelty_analysis']['status_label']} (d_min = {res_novel['novelty_analysis']['nearest_non_identical_distance']} > ngưỡng {res_novel['novelty_analysis']['youden_threshold']})")
    print("  Bảng Top-5 ảnh cá có đặc điểm gần nhất trong CSDL (Kịch bản 2):")
    for r in res_novel["top_k_results"]:
        gd = r["group_distances"]
        print(
            f"   #{r['rank']}  | {r['image_id']:10s} | {r['species']:7s} | "
            f"D_color={gd['color']:.4f}, D_shape={gd['shape']:.4f}, D_tex={gd['texture']:.4f} -> D_total={r['total_distance']:.4f} ({r['similarity_pct']:.2f}%)"
        )

    print(f"\n-> Đã lưu trọn bộ kết quả trung gian mẫu tại: {out_json}")
    print("=" * 80)


if __name__ == "__main__":
    generate_sample_intermediate_report()
