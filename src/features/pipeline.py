# -*- coding: utf-8 -*-
"""
Pipeline trích xuất và quản lý toàn bộ không gian đặc trưng đa phương tiện (MMDB):
- Nhóm 1: Màu sắc (Color) - 135 chiều (C1: 78 HSV thích nghi, C2: 9 Lab Moments, C3: 48 Spatial Block Color)
- Nhóm 2: Hình dạng (Shape) - 140 chiều (S1: 8 Morphometrics, S2: 32 Dorsal/Ventral Profile, S3: 7 Hu, S4: 29 EFD, S5: 64 Grid 8x8)
- Nhóm 3: Kết cấu (Texture) - 146 chiều (T1: 60 Foreground-Only GLCM, T2: 59 NRI-Uniform LBP, T3: 3 Tamura, T4: 24 Gabor)
Tổng số chiều Vector xếp hạng: 421 chiều (12 thành phần).
Kèm theo: Lưới nhị phân 64-bit (uint64, ngưỡng 15%) phục vụ lọc thô (Coarse Filter) bằng khoảng cách Hamming.
"""

import os
import sys
import json
import cv2
import numpy as np

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.features.color import extract_all_color_features, build_c1_perceptual_similarity_matrix_A
from src.features.shape import extract_all_shape_features, extract_binary_grids_multi_res
from src.features.texture import extract_all_texture_features

def process_single_image(img_bgra):
    """
    Xử lý một bức ảnh BGRA:
    1. Tách BGR và kênh Alpha
    2. Xác định mặt nạ cá (Alpha > 128)
    3. Tính hộp bao Bounding Box [xlb, xub, ylb, yub]
    4. Trích xuất 3 Bộ Đặc trưng Thị giác:
       - Bộ 1: Màu sắc (Color) - 135 chiều (C1: 78D, C2: 9D, C3: 48D)
       - Bộ 2: Hình dạng (Shape) - 140 chiều thực (S1..S5) + Chữ ký lưới nhị phân đa độ phân giải (S5_bin64 & S5_bin192)
       - Bộ 3: Kết cấu (Texture) - 146 chiều (T1: 60D, T2: 59D, T3: 3D, T4: 24D)
       -> Tổng hợp thành full_vector 421 chiều (12 thành phần).
    """
    if img_bgra.shape[2] == 4:
        bgr = img_bgra[:, :, :3]
        alpha = img_bgra[:, :, 3]
    else:
        bgr = img_bgra
        alpha = (cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) > 10).astype(np.uint8) * 255
        
    mask = (alpha > 128).astype(np.uint8)
    area = int(np.sum(mask > 0))
    if area < 50:
        return None
        
    ys, xs = np.where(mask > 0)
    xlb, xub = int(xs.min()), int(xs.max())
    ylb, yub = int(ys.min()), int(ys.max())
    bbox = (xlb, xub, ylb, yub)
    
    # 1. Bộ Đặc trưng Màu sắc (135 chiều: C1..C3)
    c_vec, c_names = extract_all_color_features(bgr, mask, bbox)
    
    # 2. Bộ Đặc trưng Hình dạng (140 chiều: S1..S5 + Lưới nhị phân S5_bin64 & S5_bin192)
    s_vec, s_names, grid_uint64 = extract_all_shape_features(mask, bbox)
    bin_grids = extract_binary_grids_multi_res(mask, bbox, grid_8x8=(s_vec[-64:], grid_uint64))
    
    # 3. Bộ Đặc trưng Kết cấu (146 chiều: T1..T4)
    t_vec, t_names = extract_all_texture_features(bgr, mask, bbox)
    
    full_vec = np.concatenate([c_vec, s_vec, t_vec])
    
    meta = {
        "xlb": xlb, "xub": xub, "ylb": ylb, "yub": yub,
        "width": int(xub - xlb + 1), "height": int(yub - ylb + 1),
        "aspect_ratio": float(xub - xlb + 1) / float(yub - ylb + 1),
        "fg_area": area,
        "main_axis_angle_deg": float(bin_grids["main_axis_angle_deg"]),
        "grid_uint64": int(grid_uint64),
        "grid64_hex": bin_grids["grid64_hex16"],
        "grid64_popcount": int(bin_grids["grid64_popcount"]),
        "grid192_hex": bin_grids["grid192_hex48"],
        "grid192_popcount": int(bin_grids["grid192_popcount"]),
    }
    
    return {
        "full_vector": full_vec.astype(np.float32),
        "color_vector": c_vec.astype(np.float32),
        "shape_vector": s_vec.astype(np.float32),
        "texture_vector": t_vec.astype(np.float32),
        "grid_uint64": grid_uint64,
        "grid64_bytes8": bin_grids["grid64_bytes8"],
        "grid192_bytes24": bin_grids["grid192_bytes24"],
        "metadata": meta,
        "feature_names": {
            "color": c_names,
            "shape": s_names,
            "texture": t_names,
            "all": c_names + s_names + t_names
        }
    }

def _infer_component_and_metric(fname: str):
    comp = fname.split("_")[1].upper() if "_" in fname else "OTHER"
    if comp in ("C1", "C3", "T2"):
        metric = "L1_CITYBLOCK"
    else:
        metric = "ZSCORE_L2"
    return comp, metric

def generate_feature_schema(output_path="data/feature_schema.json"):
    """
    Sinh file mô tả cấu trúc chi tiết từng chiều (Feature Schema - 421 chiều thực + 2 chữ ký nhị phân lọc thô)
    thuộc 3 Bộ Đặc trưng Thị giác (Màu sắc - Hình dạng - Kết cấu).
    """
    dummy_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    dummy_mask = np.zeros((100, 100), dtype=np.uint8)
    dummy_mask[20:80, 20:80] = 1
    dummy_bbox = (20, 80, 20, 80)
    
    c_vec, c_names = extract_all_color_features(dummy_bgr, dummy_mask, dummy_bbox)
    s_vec, s_names, _ = extract_all_shape_features(dummy_mask, dummy_bbox)
    t_vec, t_names = extract_all_texture_features(dummy_bgr, dummy_mask, dummy_bbox)
    
    schema = {
        "dataset": "dataset_gold_v3",
        "total_dimensions": len(c_names) + len(s_names) + len(t_names),
        "groups": {
            "color": {
                "set_name": "Bộ 1: Bộ Đặc trưng Màu sắc Tri giác & Bố cục Giải phẫu (Color Feature Set)",
                "dimensions": len(c_names),
                "range": [0, len(c_names) - 1],
                "subgroups": {
                    "c1_adaptive_hsv_hist": {"count": 78, "metric": "L1_CITYBLOCK / QUADRATIC_A", "desc": "6 ô vô sắc theo V + 72 ô có màu (12 Hue x 3 Sat x 2 Val) kèm Ma trận tương đồng A_78x78"},
                    "c2_color_moments_lab": {"count": 9, "metric": "ZSCORE_L2", "desc": "3 bậc moment (Mean, Std, Skewness) x 3 kênh L, a, b trên CIE Lab"},
                    "c3_spatial_blocks": {"count": 48, "metric": "L1_CITYBLOCK", "desc": "6 vùng giải phẫu (3 cột Đầu/Thân/Đuôi x 2 hàng Lưng/Bụng) x 8 bin"}
                }
            },
            "shape": {
                "set_name": "Bộ 2: Bộ Đặc trưng Hình thái học, Đường bao & Lưới Không gian (Shape Feature Set)",
                "dimensions": len(s_names),
                "range": [len(c_names), len(c_names) + len(s_names) - 1],
                "subgroups": {
                    "s1_morphometrics": {"count": 8, "metric": "ZSCORE_L2", "desc": "8 chỉ số hình học bất biến tịnh tiến & tỉ lệ (đã bỏ relative_area)"},
                    "s2_dorsal_ventral_profile": {"count": 32, "metric": "ZSCORE_L2", "desc": "Đường cong lưng (16 vị trí) và bụng (16 vị trí) dọc trục thân cá"},
                    "s3_hu_moments": {"count": 7, "metric": "ZSCORE_L2", "desc": "7 Hu Invariant Moments (log-scale giữ dấu)"},
                    "s4_elliptic_fourier": {"count": 29, "metric": "ZSCORE_L2", "desc": "8 Fourier Harmonics chuẩn hóa Kuhl-Giardina (cố định đầu cá bên trái)"},
                    "s5_grid_occupancy_8x8": {"count": 64, "metric": "ZSCORE_L2", "desc": "Tỷ lệ lấp đầy diện tích liên tục trong 64 ô lưới 8x8 + 2 chữ ký nhị phân lọc thô (S5_bin64 & S5_bin192)"}
                },
                "binary_grid_signatures": {
                    "s5_bin64_8x8": {"bits": 64, "bytes": 8, "threshold": 0.15, "metric": "HAMMING_XOR", "desc": "Lưới nhị phân lọc thô 8x8 trên hộp bao MBB (ngưỡng diện tích 15%)"},
                    "s5_bin192_12x16": {"bits": 192, "bytes": 24, "threshold": 0.15, "metric": "HAMMING_XOR", "desc": "Lưới nhị phân chuẩn hóa trục chính 192 đơn vị, xoay 0 độ, 12x16 = 192 bit (Lecture 11 Slide 30 & 34)"}
                }
            },
            "texture": {
                "set_name": "Bộ 3: Bộ Đặc trưng Kết cấu Bề mặt Vảy & Miền Tần số (Texture Feature Set)",
                "dimensions": len(t_names),
                "range": [len(c_names) + len(s_names), len(c_names) + len(s_names) + len(t_names) - 1],
                "subgroups": {
                    "t1_glcm_directional": {"count": 60, "metric": "ZSCORE_L2", "desc": "5 chỉ số Haralick x 3 khoảng cách (1,3,5) x 4 hướng (0,45,90,135) chỉ đếm cặp pixel nội thân cá"},
                    "t2_lbp_nri_uniform": {"count": 59, "metric": "L1_CITYBLOCK", "desc": "58 mẫu uniform có hướng + 1 mẫu non-uniform (P=8, R=1)"},
                    "t3_tamura": {"count": 3, "metric": "ZSCORE_L2", "desc": "Độ thô vảy Tamura: Coarseness, Contrast, Directionality"},
                    "t4_gabor_energy": {"count": 24, "metric": "ZSCORE_L2", "desc": "12 bộ lọc Gabor (3 bước sóng x 4 hướng) x [Mean, Std]"}
                }
            }
        },
        "coarse_filter": {
            "binary_grid_64bit": "Chữ ký nhị phân 64-bit (8 bytes BLOB + 16 Hex) ngưỡng 15% diện tích ô (Hamming distance)",
            "binary_grid_192bit": "Chữ ký nhị phân 192-bit (24 bytes BLOB + 48 Hex) chuẩn hóa trục chính 192 đơn vị (Lecture 11 Slide 30 & 34)"
        },
        "dimensions": []
    }
    
    idx = 0
    for name in c_names:
        comp, metric = _infer_component_and_metric(name)
        schema["dimensions"].append({"index": idx, "name": name, "group": "color", "component": comp, "metric": metric})
        idx += 1
    for name in s_names:
        comp, metric = _infer_component_and_metric(name)
        schema["dimensions"].append({"index": idx, "name": name, "group": "shape", "component": comp, "metric": metric})
        idx += 1
    for name in t_names:
        comp, metric = _infer_component_and_metric(name)
        schema["dimensions"].append({"index": idx, "name": name, "group": "texture", "component": comp, "metric": metric})
        idx += 1
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"Đã xuất Feature Schema tại: {output_path} (Tổng số chiều: {schema['total_dimensions']})")
    return schema

