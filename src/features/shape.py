# -*- coding: utf-8 -*-
"""
Module trích xuất đặc trưng Hình dạng (Shape Features) cho ảnh cá (140 chiều):
1. S1: 8 Chỉ số hình thái học kinh điển (Geometric Morphometrics): 8 chiều
   - Aspect Ratio, Circularity, Solidity, Extent, Eccentricity, Convexity, Rectangularity, Eq Diameter Ratio
   - Loại bỏ relative_area (lỗi E7) để đảm bảo bất biến tỉ lệ tuyệt đối
2. S2: Đường cong lưng và bụng (Dorsal & Ventral Profile): 32 chiều
   - 16 lát cắt cách đều dọc trục chính thân cá
   - Đo khoảng cách từ trục tâm tới mép lưng (16 chiều) và mép bụng (16 chiều) chia cho chiều dài cá
3. S3: 7 Mô-men Hu bất biến (log-scale): 7 chiều
4. S4: Fourier elip (EFD - 8 harmonics, chuẩn hóa Kuhl-Giardina): 29 chiều
   - Chuẩn hóa đầy đủ kích thước, điểm bắt đầu và hướng trục (đầu cá quay sang trái); loại 3 hệ số hằng của hài bậc 1
5. S5: Lưới không gian 8x8 trên hộp bao (Spatial Grid Occupancy): 64 chiều
   - Tỷ lệ lấp đầy diện tích cá trong 64 ô lưới (8 hàng x 8 cột) trên [0, 1]
   - Đồng thời sinh chữ ký nhị phân 64-bit (ngưỡng lấp đầy 15% theo Lecture 11 Slide 30) cho bộ lọc thô Hamming
Tổng số chiều Hình dạng: 8 + 32 + 7 + 29 + 64 = 140 chiều.
"""

import numpy as np
import cv2

def extract_morphometrics(mask, bbox, contour):
    """
    S1: Trích xuất 8 chỉ số hình thái học hình học (Geometric Morphometrics).
    Đảm bảo hoàn toàn bất biến tịnh tiến và tỉ lệ kích thước (Scale-Invariant).
    """
    xlb, xub, ylb, yub = bbox
    w = max(1.0, float(xub - xlb + 1))
    h = max(1.0, float(yub - ylb + 1))
    
    area = float(np.sum(mask > 0))
    if area == 0 or contour is None or len(contour) < 5:
        return np.zeros(8, dtype=np.float32)
    
    # 1. Aspect Ratio (Tỉ lệ khung bao ngang/dọc)
    aspect_ratio = w / h
    
    # Chu vi và bao lồi
    perimeter = float(cv2.arcLength(contour, True))
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull))
    hull_perimeter = float(cv2.arcLength(hull, True))
    
    # 2. Circularity / Compactness (Độ tròn)
    circularity = (4.0 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0
    
    # 3. Solidity (Độ đặc)
    solidity = area / hull_area if hull_area > 0 else 0.0
    
    # 4. Extent (Tỷ lệ lấp đầy hộp bao trục)
    extent = area / (w * h)
    
    # 5. Convexity (Độ lồi chu vi)
    convexity = hull_perimeter / perimeter if perimeter > 0 else 0.0
    
    # Khớp Elip tương đương (cần tối thiểu 5 điểm)
    try:
        ellipse = cv2.fitEllipse(contour)
        (center, (d1, d2), angle) = ellipse
        major_axis = max(d1, d2)
        minor_axis = min(d1, d2)
    except Exception:
        major_axis = max(w, h)
        minor_axis = min(w, h)
        
    major_axis = max(1.0, float(major_axis))
    minor_axis = max(1.0, float(minor_axis))
    
    # 6. Eccentricity (Độ lệch tâm elip)
    ecc_sq = max(0.0, 1.0 - (minor_axis / major_axis) ** 2)
    eccentricity = float(np.sqrt(ecc_sq))
    
    # 7. Rectangularity (Diện tích / Diện tích hộp bao xoay tối thiểu)
    rect = cv2.minAreaRect(contour)
    box_area = max(1.0, float(rect[1][0] * rect[1][1]))
    rectangularity = area / box_area
    
    # 8. Equivalent Diameter Ratio (Đường kính tương đương / đường chéo bbox)
    eq_diameter = np.sqrt(4.0 * area / np.pi)
    eq_diameter_ratio = eq_diameter / np.sqrt(w**2 + h**2)
    
    return np.array([
        aspect_ratio, circularity, solidity, extent,
        eccentricity, convexity, rectangularity, eq_diameter_ratio
    ], dtype=np.float32)

def extract_dorsal_ventral_profile(mask, bbox, num_points=16):
    """
    S2: Đường cong lưng và bụng (Dorsal & Ventral Profile) - 32 chiều:
    - 16 vị trí dọc trục thân cá từ đầu tới đuôi.
    - Đo khoảng cách từ trục tâm centroid tới mép trên (lưng) và mép dưới (bụng), chia cho chiều dài cá.
    - Định lượng chính xác cá lưng gù (Katla), cá mình thon (Boal, Rui), độ sâu bụng.
    """
    xlb, xub, ylb, yub = bbox
    w = max(1.0, float(xub - xlb + 1))
    
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return np.zeros(num_points * 2, dtype=np.float32)
    
    cy = float(np.mean(ys))
    
    dorsal = []
    ventral = []
    
    for i in range(num_points):
        x1 = int(round(xlb + i * w / float(num_points)))
        x2 = int(round(xlb + (i + 1) * w / float(num_points)))
        x2 = max(x1 + 1, x2)
        x2 = min(x2, mask.shape[1])
        x1 = max(0, x1)
        
        slice_mask = mask[:, x1:x2]
        slice_ys, _ = np.where(slice_mask > 0)
        
        if len(slice_ys) > 0:
            y_top = float(np.min(slice_ys))
            y_bot = float(np.max(slice_ys))
            d_d = max(0.0, cy - y_top) / w
            d_v = max(0.0, y_bot - cy) / w
        else:
            d_d = 0.0
            d_v = 0.0
            
        dorsal.append(d_d)
        ventral.append(d_v)
        
    return np.array(dorsal + ventral, dtype=np.float32)

def extract_hu_moments(mask):
    """
    S3: Trích xuất 7 Hu Moments bất biến với tịnh tiến, tỷ lệ và xoay.
    Biến đổi thang đo log: -sign(h) * log10(|h| + eps)
    Tổng: 7 chiều.
    """
    moments = cv2.moments((mask > 0).astype(np.uint8))
    hu = cv2.HuMoments(moments).flatten()
    
    log_hu = np.zeros(7, dtype=np.float32)
    for i in range(7):
        val = hu[i]
        if np.isnan(val) or np.isinf(val):
            log_hu[i] = 0.0
        else:
            sign = np.sign(val)
            abs_v = np.abs(val)
            log_hu[i] = -sign * np.log10(abs_v + 1e-30) if abs_v > 0 else 0.0
            
    # Chuẩn hóa về dải xấp xỉ [-1, 1] cho ổn định số học
    log_hu = np.clip(log_hu / 20.0, -1.0, 1.0)
    return log_hu

def extract_elliptic_fourier_descriptors_kuhl(contour, order=8):
    """
    S4: Elliptic Fourier Descriptors (EFD) với 8 harmonics.
    Chuẩn hóa hoàn toàn theo Kuhl & Giardina (1982):
    - Bất biến tịnh tiến (loại a0, c0)
    - Bất biến kích thước (chia cho bán trục lớn E của hài bậc 1)
    - Bất biến điểm bắt đầu (dịch pha theta1, cố định về phía đầu cá bên trái)
    - Bất biến hướng xoay trục (xoay không gian psi1)
    Sau chuẩn hóa, hài bậc 1 có an_norm[0] = 1, bn_norm[0] = 0, cn_norm[0] = 0 (hằng số).
    Giữ lại dn_norm[0] và toàn bộ 4 hệ số (an, bn, cn, dn) cho n = 2..8:
    1 + 7 * 4 = 29 chiều (sửa triệt để lỗi E3 và L1).
    """
    if contour is None or len(contour) < 5:
        return np.zeros(order * 4 - 3, dtype=np.float32)
        
    pts = contour.squeeze().astype(np.float64)
    if pts.ndim != 2 or len(pts) < 5:
        return np.zeros(order * 4 - 3, dtype=np.float32)
        
    # Khép kín đường bao nếu chưa khép
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
        
    dxy = np.diff(pts, axis=0)
    dt = np.sqrt(np.sum(dxy ** 2, axis=1))
    
    valid = dt > 1e-7
    if not np.any(valid):
        return np.zeros(order * 4 - 3, dtype=np.float32)
        
    dxy = dxy[valid]
    dt = dt[valid]
    t = np.concatenate([[0.0], np.cumsum(dt)])
    T = t[-1]
    if T < 1e-7:
        return np.zeros(order * 4 - 3, dtype=np.float32)
        
    an = np.zeros(order, dtype=np.float64)
    bn = np.zeros(order, dtype=np.float64)
    cn = np.zeros(order, dtype=np.float64)
    dn = np.zeros(order, dtype=np.float64)
    
    for i in range(order):
        n = i + 1
        two_n_pi = 2.0 * n * np.pi
        c_diff = np.cos(two_n_pi * t[1:] / T) - np.cos(two_n_pi * t[:-1] / T)
        s_diff = np.sin(two_n_pi * t[1:] / T) - np.sin(two_n_pi * t[:-1] / T)
        
        factor = T / (2.0 * ((n * np.pi) ** 2))
        an[i] = factor * np.sum((dxy[:, 0] / dt) * c_diff)
        bn[i] = factor * np.sum((dxy[:, 0] / dt) * s_diff)
        cn[i] = factor * np.sum((dxy[:, 1] / dt) * c_diff)
        dn[i] = factor * np.sum((dxy[:, 1] / dt) * s_diff)
        
    # 1. Bất biến điểm bắt đầu: tìm pha theta1 của hài bậc 1
    denom = an[0]**2 + cn[0]**2 - bn[0]**2 - dn[0]**2
    num = 2.0 * (an[0] * bn[0] + cn[0] * dn[0])
    theta1 = 0.5 * np.arctan2(num, denom)
    
    def _phase_shift(th):
        a_s = np.zeros(order, dtype=np.float64)
        b_s = np.zeros(order, dtype=np.float64)
        c_s = np.zeros(order, dtype=np.float64)
        d_s = np.zeros(order, dtype=np.float64)
        for i in range(order):
            n = i + 1
            cos_nt = np.cos(n * th)
            sin_nt = np.sin(n * th)
            a_s[i] = cos_nt * an[i] + sin_nt * bn[i]
            b_s[i] = -sin_nt * an[i] + cos_nt * bn[i]
            c_s[i] = cos_nt * cn[i] + sin_nt * dn[i]
            d_s[i] = -sin_nt * cn[i] + cos_nt * dn[i]
        return a_s, b_s, c_s, d_s
    
    an_star, bn_star, cn_star, dn_star = _phase_shift(theta1)
    
    # Trục chính có 2 đầu (theta1 và theta1 + pi) -> các hài bậc chẵn bị đổi dấu tùy điểm bắt đầu.
    # Cố định: điểm bắt đầu là đầu trục phía ĐẦU CÁ. Dataset chuẩn hóa đầu cá quay sang trái,
    # nên chọn đầu trục có hoành độ nhỏ hơn (an_star[0] < 0).
    if an_star[0] > 0:
        theta1 = theta1 + np.pi
        an_star, bn_star, cn_star, dn_star = _phase_shift(theta1)
        
    # 2. Bất biến xoay không gian: tìm góc nghiêng psi1 của hài bậc 1
    psi1 = np.arctan2(cn_star[0], an_star[0])
    cos_psi = np.cos(psi1)
    sin_psi = np.sin(psi1)
    
    an_rot = cos_psi * an_star + sin_psi * cn_star
    bn_rot = cos_psi * bn_star + sin_psi * dn_star
    cn_rot = -sin_psi * an_star + cos_psi * cn_star
    dn_rot = -sin_psi * bn_star + cos_psi * dn_star
    
    # 3. Bất biến kích thước: chuẩn hóa theo bán trục lớn E = an_rot[0]
    E = an_rot[0]
    if np.abs(E) > 1e-7:
        an_norm = an_rot / E
        bn_norm = bn_rot / E
        cn_norm = cn_rot / E
        dn_norm = dn_rot / E
    else:
        an_norm, bn_norm, cn_norm, dn_norm = an_rot, bn_rot, cn_rot, dn_rot
        
    # Hệ số bậc 1: an_norm[0] = 1, bn_norm[0] = 0, cn_norm[0] = 0.
    # Lấy dn_norm[0] và 4 hệ số cho các hài từ bậc 2 đến 8:
    coeffs = [float(dn_norm[0])]
    for i in range(1, order):
        coeffs.extend([float(an_norm[i]), float(bn_norm[i]), float(cn_norm[i]), float(dn_norm[i])])
        
    coeffs = np.clip(np.array(coeffs, dtype=np.float32), -5.0, 5.0)
    return coeffs

def extract_binary_grid_8x8(mask, bbox):
    """
    S5: Lưới 8x8 (64 ô) trên vùng bounding box của thân cá.
    Trả về:
    1. grid_continuous: tỷ lệ lấp đầy 64 ô trong [0, 1] (64 chiều đưa vào vector xếp hạng S5)
    2. grid_uint64: số nguyên 64-bit (MSB-first đồng bộ với packbits/hex16) với ngưỡng lấp đầy 15%
       (theo Lecture 11 Slide 30) cho lọc thô
    """
    xlb, xub, ylb, yub = bbox
    crop = mask[ylb:yub+1, xlb:xub+1]
    
    if crop.size == 0:
        return np.zeros(64, dtype=np.float32), np.uint64(0)
        
    # Chuẩn hóa mặt nạ nhị phân về {0.0, 1.0} dạng float64 trước khi nội suy INTER_AREA
    crop_f = (crop > 0).astype(np.float64)
    grid = cv2.resize(crop_f, (8, 8), interpolation=cv2.INTER_AREA)
    grid_continuous = np.clip(grid.flatten(), 0.0, 1.0)
    grid_continuous = np.where(grid_continuous > 1.0 - 1e-5, 1.0, grid_continuous).astype(np.float32)
    
    # Tạo số nguyên 64-bit nhị phân MSB-first (đồng bộ thứ tự bit với np.packbits) với ngưỡng 15%
    bits64 = (grid_continuous >= 0.15).astype(np.uint8)
    bytes64 = np.packbits(bits64)
    grid_uint64 = np.uint64(bytes64.view(">u8")[0])
            
    return grid_continuous, grid_uint64


def extract_binary_grids_multi_res(mask, bbox, grid_8x8=None):
    """
    Trích xuất chữ ký lưới nhị phân đa độ phân giải thuộc nhóm Hình dạng S5
    (Lecture 11 Slide 30 & Slide 34 - TS. Nguyễn Đình Hóa):
    - S5_bin64 (8x8 = 64-bit, ngưỡng 15%): Lưu dạng uint64, mảng 8 bytes (BLOB) và chuỗi Hex 16 ký tự.
    - S5_bin192 (12x16 = 192-bit chuẩn hóa trục chính = 192 đơn vị, xoay 0 độ, ngưỡng 15%):
      Lưu dạng mảng 24 bytes (BLOB) và chuỗi Hex 48 ký tự (chống tràn số int64 trên SQLite).
    """
    if grid_8x8 is not None:
        grid_continuous, grid_uint64 = grid_8x8
    else:
        grid_continuous, grid_uint64 = extract_binary_grid_8x8(mask, bbox)
    bits64 = (grid_continuous >= 0.15).astype(np.uint8)
    bytes64 = np.packbits(bits64)  # 8 bytes uint8
    hex64 = bytes64.tobytes().hex()
    pop64 = int(bits64.sum())

    # Chuẩn hóa xoay trục chính 0 độ & chuẩn hóa chiều dài trục chính = 192 đơn vị (Slide 30)
    mask_bin = (mask > 0).astype(np.uint8)
    mask_f = mask_bin.astype(np.float32)
    moments = cv2.moments(mask_bin)
    if moments["m00"] > 0:
        xc = moments["m10"] / moments["m00"]
        yc = moments["m01"] / moments["m00"]
        angle_rad = 0.5 * np.arctan2(2.0 * moments["mu11"], moments["mu20"] - moments["mu02"])
        angle_deg = float(np.rad2deg(angle_rad))
    else:
        xc, yc, angle_deg = mask.shape[1] / 2.0, mask.shape[0] / 2.0, 0.0

    rot_mat = cv2.getRotationMatrix2D((xc, yc), angle_deg, 1.0)
    rotated = cv2.warpAffine(mask_f, rot_mat, (mask.shape[1], mask.shape[0]), flags=cv2.INTER_NEAREST)

    ys, xs = np.where(rotated > 0.5)
    if len(xs) > 0:
        rx1, rx2 = int(xs.min()), int(xs.max())
        ry1, ry2 = int(ys.min()), int(ys.max())
        rw = max(1, rx2 - rx1 + 1)
        rh = max(1, ry2 - ry1 + 1)
        scale = 192.0 / float(rw)
        new_h = min(144, max(1, int(round(rh * scale))))
        norm_fish = cv2.resize(rotated[ry1:ry2 + 1, rx1:rx2 + 1], (192, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((144, 192), dtype=np.float32)
        y_off = (144 - new_h) // 2
        canvas[y_off:y_off + new_h, :] = norm_fish
    else:
        canvas = np.zeros((144, 192), dtype=np.float32)

    # Phủ lưới 12 hàng x 16 cột = 192 ô vuông (mỗi ô 12x12 px), ngưỡng diện tích 15%
    cell_occupancies = canvas.reshape(12, 12, 16, 12).mean(axis=(1, 3)).flatten()
    bits192 = (cell_occupancies >= 0.15).astype(np.uint8)
    bytes192 = np.packbits(bits192)  # 24 bytes uint8
    hex192 = bytes192.tobytes().hex()
    pop192 = int(bits192.sum())

    return {
        "grid_continuous": grid_continuous,
        "grid_uint64": grid_uint64,
        "grid64_bits": bits64,
        "grid64_bytes8": bytes64,
        "grid64_hex16": hex64,
        "grid64_popcount": pop64,
        "grid192_bits": bits192,
        "grid192_bytes24": bytes192,
        "grid192_hex48": hex192,
        "grid192_popcount": pop192,
        "main_axis_angle_deg": angle_deg,
    }


def extract_all_shape_features(mask, bbox):
    """
    Trích toàn bộ 140 chiều đặc trưng Hình dạng:
    - S1: Morphometrics 8 chiều (bỏ relative_area)
    - S2: Dorsal & Ventral profile 32 chiều (16 lưng + 16 bụng)
    - S3: Hu Invariant Moments 7 chiều
    - S4: EFD chuẩn hóa Kuhl-Giardina 29 chiều (8 harmonics)
    - S5: Spatial Grid Occupancy 8x8 64 chiều + chữ ký 64-bit (grid_uint64)
    Trả về: (shape_vector, feature_names, grid_uint64)
    """
    mask_bin = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c_max = max(contours, key=cv2.contourArea) if contours else None
    
    # S1: 8 chiều
    morph_vec = extract_morphometrics(mask_bin, bbox, c_max)
    morph_names = [
        "shape_s1_aspect_ratio", "shape_s1_circularity", "shape_s1_solidity",
        "shape_s1_extent", "shape_s1_eccentricity", "shape_s1_convexity",
        "shape_s1_rectangularity", "shape_s1_eq_diam_ratio"
    ]
    
    # S2: 32 chiều
    profile_vec = extract_dorsal_ventral_profile(mask_bin, bbox, num_points=16)
    profile_names = [f"shape_s2_dorsal_p{i+1}" for i in range(16)] + [
        f"shape_s2_ventral_p{i+1}" for i in range(16)
    ]
    
    # S3: 7 chiều
    hu_vec = extract_hu_moments(mask_bin)
    hu_names = [f"shape_s3_hu_{i+1}" for i in range(7)]
    
    # S4: 29 chiều
    efd_vec = extract_elliptic_fourier_descriptors_kuhl(c_max, order=8)
    efd_names = ["shape_s4_efd_h1_d"] + [
        f"shape_s4_efd_h{h}_{c}"
        for h in range(2, 9)
        for c in ["a", "b", "c", "d"]
    ]
    
    # S5: 64 chiều + mã lưới 64-bit cho lọc thô
    grid_vec, grid_uint64 = extract_binary_grid_8x8(mask_bin, bbox)
    grid_names = [
        f"shape_s5_grid_r{r}_c{c}"
        for r in range(8)
        for c in range(8)
    ]
    
    full_shape_vec = np.concatenate([morph_vec, profile_vec, hu_vec, efd_vec, grid_vec])
    full_shape_names = morph_names + profile_names + hu_names + efd_names + grid_names
    
    return full_shape_vec, full_shape_names, grid_uint64

