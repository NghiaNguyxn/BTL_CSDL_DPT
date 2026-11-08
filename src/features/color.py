# -*- coding: utf-8 -*-
"""
Module trích xuất đặc trưng Màu sắc (Color Features) cho ảnh cá (135 chiều):
1. C1: Global HSV Histogram có ô vô sắc (Achromatic/Chromatic): 78 chiều
   - 6 ô vô sắc (S < 0.15) theo độ sáng V (chia đều trên [0, 1])
   - 72 ô có màu (S >= 0.15): 12 Hue (30 độ/ô) x 3 Saturation x 2 Value
2. C2: Mô-men màu (Color Moments) trên CIE Lab: 9 chiều
   - 3 bậc moment (Mean, Std, Skewness) trên 3 kênh L, a, b
3. C3: Bố cục màu theo vùng giải phẫu (Spatial Block Color Layout): 48 chiều
   - 3 cột (Đầu, Thân, Đuôi) x 2 hàng (Lưng, Bụng) = 6 vùng
   - Mỗi vùng: 8 bin (2 ô vô sắc + 6 ô Hue có màu)
Tổng số chiều Màu sắc: 78 + 9 + 48 = 135 chiều.
"""

import numpy as np
import cv2
from scipy.stats import skew

def extract_adaptive_hsv_hist(hsv_fg):
    """
    C1: Biểu đồ màu thích nghi có Ô vô sắc (Achromatic Bins) - 78 chiều:
    - Nếu S < 0.15: pixel không có sắc độ rõ, phân vào 6 ô xám đều theo V trên [0, 1].
    - Nếu S >= 0.15: phân vào 72 ô có màu:
      + Hue: 12 bin (mỗi bin 30 độ)
      + Sat: 3 bin ([0.15, 0.35), [0.35, 0.60), [0.60, 1.0])
      + Val: 2 bin ([0.0, 0.50), [0.50, 1.0])
    Tổng cộng: 6 + 72 = 78 chiều. Chuẩn hóa L1 (tổng = 1.0).
    """
    total_pixels = len(hsv_fg)
    if total_pixels == 0:
        return np.zeros(78, dtype=np.float32)
    
    h = hsv_fg[:, 0].astype(np.float32) * 2.0   # OpenCV H in [0, 180] -> [0, 360] độ
    s = hsv_fg[:, 1].astype(np.float32) / 255.0 # [0, 1.0]
    v = hsv_fg[:, 2].astype(np.float32) / 255.0 # [0, 1.0]
    
    hist = np.zeros(78, dtype=np.float32)
    
    achromatic_mask = s < 0.15
    chromatic_mask = ~achromatic_mask
    
    # 1. Achromatic (6 bins: index 0 -> 5)
    if np.any(achromatic_mask):
        v_achr = v[achromatic_mask]
        v_bins = np.clip((v_achr * 6.0).astype(int), 0, 5)
        hist[:6] = np.bincount(v_bins, minlength=6).astype(np.float32)
            
    # 2. Chromatic (72 bins: index 6 -> 77)
    if np.any(chromatic_mask):
        h_chr = h[chromatic_mask]
        s_chr = s[chromatic_mask]
        v_chr = v[chromatic_mask]
        
        # 12 bin Hue: [0, 30), [30, 60), ..., [330, 360)
        h_bin = np.clip((h_chr / 30.0).astype(int), 0, 11)
        
        # 3 bin Sat: [0.15, 0.35) -> 0, [0.35, 0.60) -> 1, [0.60, 1.0] -> 2
        s_bin = np.zeros(len(s_chr), dtype=int)
        s_bin[(s_chr >= 0.35) & (s_chr < 0.60)] = 1
        s_bin[s_chr >= 0.60] = 2
        
        # 2 bin Val: [0, 0.50) -> 0, [0.50, 1.0] -> 1
        v_bin = np.where(v_chr < 0.50, 0, 1)
        
        # Offset 6 + h_bin * 6 + s_bin * 2 + v_bin
        chr_sub_idx = h_bin * 6 + s_bin * 2 + v_bin
        hist[6:] = np.bincount(chr_sub_idx, minlength=72).astype(np.float32)
            
    # Chuẩn hóa L1
    hist = hist / float(total_pixels)
    return hist

def extract_color_moments_lab(lab_fg):
    """
    C2: Tính 3 moments bậc 1, 2, 3 (Mean, Std, Skewness) trên 3 kênh CIE Lab:
    Tránh vấn đề đại lượng vòng tròn của Hue trong HSV.
    Tổng: 9 chiều.
    """
    if len(lab_fg) == 0:
        return np.zeros(9, dtype=np.float32)
    
    # Chuẩn hóa về [0, 1]
    l = lab_fg[:, 0].astype(np.float32) / 255.0
    a = lab_fg[:, 1].astype(np.float32) / 255.0
    b = lab_fg[:, 2].astype(np.float32) / 255.0
    
    moments = []
    for channel in [l, a, b]:
        m_mean = float(np.mean(channel))
        m_std = float(np.std(channel))
        if m_std < 1e-6 or len(channel) <= 2:
            m_skew = 0.0
        else:
            m_skew = float(skew(channel))
        if np.isnan(m_skew) or np.isinf(m_skew):
            m_skew = 0.0
        # Giới hạn skewness trong khoảng ổn định [-1, 1]
        m_skew = np.clip(m_skew / 5.0, -1.0, 1.0)
        moments.extend([m_mean, m_std, m_skew])
        
    return np.array(moments, dtype=np.float32)

def extract_spatial_block_color(bgr_img, mask, bbox):
    """
    C3: Bố cục màu theo 6 vùng giải phẫu học:
    3 cột (Đầu 25%, Thân 50%, Đuôi 25%) x 2 hàng (Lưng 50%, Bụng 50%) = 6 vùng con.
    Mỗi vùng trích 8 bin (2 bin vô sắc + 6 bin Hue có màu).
    Tổng: 6 x 8 = 48 chiều.
    """
    xlb, xub, ylb, yub = bbox
    w = max(1, xub - xlb + 1)
    h = max(1, yub - ylb + 1)
    
    # Ranh giới cột và hàng
    x_splits = [xlb, int(xlb + 0.25 * w), int(xlb + 0.75 * w), xub + 1]
    y_splits = [ylb, int(ylb + 0.50 * h), yub + 1]
    
    # 6 vùng con: (col_idx, row_idx) -> [head_dorsal, head_ventral, mid_dorsal, mid_ventral, tail_dorsal, tail_ventral]
    blocks = [
        (x_splits[0], x_splits[1], y_splits[0], y_splits[1]), # Head Dorsal
        (x_splits[0], x_splits[1], y_splits[1], y_splits[2]), # Head Ventral
        (x_splits[1], x_splits[2], y_splits[0], y_splits[1]), # Mid Dorsal
        (x_splits[1], x_splits[2], y_splits[1], y_splits[2]), # Mid Ventral
        (x_splits[2], x_splits[3], y_splits[0], y_splits[1]), # Tail Dorsal
        (x_splits[2], x_splits[3], y_splits[1], y_splits[2]), # Tail Ventral
    ]
    
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    feature_vec = []
    
    for (x1, x2, y1, y2) in blocks:
        sub_mask = np.zeros_like(mask)
        x1_c, x2_c = max(0, x1), min(mask.shape[1], max(x1 + 1, x2))
        y1_c, y2_c = max(0, y1), min(mask.shape[0], max(y1 + 1, y2))
        sub_mask[y1_c:y2_c, x1_c:x2_c] = mask[y1_c:y2_c, x1_c:x2_c]
        
        block_fg = hsv[sub_mask > 0]
        hist8 = np.zeros(8, dtype=np.float32)
        if len(block_fg) > 0:
            h_p = block_fg[:, 0].astype(np.float32) * 2.0
            s_p = block_fg[:, 1].astype(np.float32) / 255.0
            v_p = block_fg[:, 2].astype(np.float32) / 255.0
            
            achr = s_p < 0.15
            # Vô sắc: bin 0 (tối V < 0.5), bin 1 (sáng V >= 0.5)
            if np.any(achr):
                hist8[0] += np.sum(v_p[achr] < 0.5)
                hist8[1] += np.sum(v_p[achr] >= 0.5)
            # Có màu: 6 bin Hue (mỗi bin 60 độ: bin 2 -> 7)
            if np.any(~achr):
                h_b = np.clip((h_p[~achr] / 60.0).astype(int), 0, 5)
                hist8[2:] = np.bincount(h_b, minlength=6).astype(np.float32)
            hist8 = hist8 / float(len(block_fg))
            
        feature_vec.extend(hist8)
        
    return np.array(feature_vec, dtype=np.float32)

def extract_all_color_features(bgr_img, mask, bbox):
    """
    Trích toàn bộ 135 chiều đặc trưng Màu sắc:
    - C1: HSV Histogram 78 chiều (6 vô sắc + 72 có màu)
    - C2: Color Moments CIE Lab 9 chiều
    - C3: Spatial Block Color 48 chiều (6 vùng x 8 bin)
    Trả về: (color_vector, feature_names)
    """
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2Lab)
    
    hsv_fg = hsv[mask > 0]
    lab_fg = lab[mask > 0]
    
    # C1: 78 chiều
    hist_vec = extract_adaptive_hsv_hist(hsv_fg)
    hist_names = [f"color_c1_achr_v{i}" for i in range(6)] + [
        f"color_c1_chr_h{h_b}_s{s_b}_v{v_b}"
        for h_b in range(12)
        for s_b in range(3)
        for v_b in range(2)
    ]
    
    # C2: 9 chiều
    mom_vec = extract_color_moments_lab(lab_fg)
    mom_names = [
        f"color_c2_mom_{ch}_{m}"
        for ch in ["L", "a", "b"]
        for m in ["mean", "std", "skew"]
    ]
    
    # C3: 48 chiều
    spatial_vec = extract_spatial_block_color(bgr_img, mask, bbox)
    block_names = ["head_dorsal", "head_ventral", "mid_dorsal", "mid_ventral", "tail_dorsal", "tail_ventral"]
    comp_names = ["achr_dark", "achr_bright", "hue_0_60", "hue_60_120", "hue_120_180", "hue_180_240", "hue_240_300", "hue_300_360"]
    spatial_names = [
        f"color_c3_spatial_{b}_{comp}"
        for b in block_names
        for comp in comp_names
    ]
    
    full_color_vec = np.concatenate([hist_vec, mom_vec, spatial_vec])
    full_color_names = hist_names + mom_names + spatial_names
    
    return full_color_vec, full_color_names


def build_c1_perceptual_similarity_matrix_A(sigma_lab: float = 35.0) -> np.ndarray:
    """
    Xây dựng ma trận tương đồng màu sắc tri giác chéo bin A (78 x 78) trên không gian CIE Lab
    (Lecture 11 Slide 19 & 22 - TS. Nguyễn Đình Hóa):
        D_quad(Q, I) = sqrt((Q - I)^T * A * (Q - I))
    Mỗi bin trong 78 bin của C1 (6 bin vô sắc + 72 bin hữu sắc) được ánh xạ sang tâm màu
    HSV chuẩn, chuyển đổi sang không gian đều màu CIE Lab, sau đó tính độ tương đồng:
        a_{ij} = exp(- ||Lab_i - Lab_j||_2 / sigma_lab)
    """
    from scipy.spatial.distance import cdist
    hsv_centers = np.zeros((78, 1, 3), dtype=np.uint8)

    # 6 bin vô sắc (S = 0, V chia đều 6 mức)
    for i in range(6):
        v_center = (i + 0.5) / 6.0
        hsv_centers[i, 0, :] = [0, 0, int(round(v_center * 255.0))]

    # 72 bin hữu sắc (12 Hue x 3 Sat x 2 Val)
    s_centers = [0.25, 0.475, 0.80]
    v_centers = [0.25, 0.75]
    idx = 6
    for h_b in range(12):
        h_deg = (h_b + 0.5) * 30.0
        h_cv = int(round(h_deg / 2.0)) % 180
        for s_c in s_centers:
            for v_c in v_centers:
                hsv_centers[idx, 0, :] = [h_cv, int(round(s_c * 255.0)), int(round(v_c * 255.0))]
                idx += 1

    bgr_centers = cv2.cvtColor(hsv_centers, cv2.COLOR_HSV2BGR)
    lab_centers = cv2.cvtColor(bgr_centers, cv2.COLOR_BGR2Lab).reshape(78, 3).astype(np.float64)

    dist_lab = cdist(lab_centers, lab_centers, metric="euclidean")
    A = np.exp(-dist_lab / float(sigma_lab))
    return A.astype(np.float32)


def rocchio_relevance_feedback(
    q_vec: np.ndarray,
    rel_vecs: np.ndarray = None,
    non_rel_vecs: np.ndarray = None,
    alpha: float = 1.0,
    beta: float = 0.75,
    gamma: float = 0.25,
) -> np.ndarray:
    """
    Cập nhật vector truy vấn Q theo thuật toán phản hồi liên quan Rocchio
    (Lecture 7 & Lecture 11 Slide 35 - TS. Nguyễn Đình Hóa):
        Q^{(t+1)} = alpha * Q^{(t)} + beta * mean(R_r) - gamma * mean(R_{nr})
    """
    q_new = alpha * q_vec.astype(np.float64)
    if rel_vecs is not None and len(rel_vecs) > 0:
        q_new = q_new + beta * np.mean(rel_vecs, axis=0)
    if non_rel_vecs is not None and len(non_rel_vecs) > 0:
        q_new = q_new - gamma * np.mean(non_rel_vecs, axis=0)
    return q_new.astype(np.float32)

