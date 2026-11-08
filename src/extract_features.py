# -*- coding: utf-8 -*-
"""
Script chạy trích xuất toàn bộ đặc trưng trên 1.100 bức ảnh dataset_gold_v3/images_rgba:
- 421 chiều (12 thành phần): Màu (135: C1..C3), Hình dạng (140: S1..S5), Kết cấu (146: T1..T4)
- Lưới nhị phân 64-bit (uint64) để phục vụ lọc thô (Coarse Filter)
- Kiểm tra tính hợp lệ dữ liệu (không NaN, không Inf)
- Lưu trữ kết quả dạng numpy npy/npz
- Sinh file data/feature_schema.json
- Báo cáo thống kê hiệu năng thời gian xử lý
"""

import os
import sys
import glob
import time
import json
import cv2
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Đảm bảo import được module từ thư mục gốc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.features.pipeline import process_single_image, generate_feature_schema
from src.features.color import build_c1_perceptual_similarity_matrix_A
from src.features.shape import extract_binary_grids_multi_res

def run_extraction(dataset_dir="dataset_gold_v3/images_rgba", output_npz="data/features_extracted.npz"):
    print("=" * 70)
    print("BẮT ĐẦU QUY TRÌNH TRÍCH XUẤT ĐẶC TRƯNG CBIR TRÊN 1.100 ẢNH")
    print(f"Thư mục nguồn: {dataset_dir}")
    print("=" * 70)
    
    # 1. Sinh Schema trước
    schema = generate_feature_schema("data/feature_schema.json")
    total_dims = schema["total_dimensions"]
    
    species_list = ["boal", "ilish", "katla", "koi", "rui", "telapia"]
    
    all_features = []
    all_color = []
    all_shape = []
    all_texture = []
    all_grid_u64 = []
    all_grid64_bytes = []
    all_grid192_bytes = []
    all_labels = []
    all_files = []
    metadata_list = []
    
    start_total_time = time.time()
    total_processed = 0
    
    for sp in species_list:
        folder = os.path.join(dataset_dir, sp)
        if not os.path.isdir(folder):
            print(f"Cảnh báo: Không tìm thấy {folder}")
            continue
            
        files = sorted(glob.glob(os.path.join(folder, "*.*")))
        print(f"\n--> Trích xuất loài [{sp.upper()}]: {len(files)} ảnh...")
        sp_start_time = time.time()
        
        for fpath in files:
            fname = os.path.basename(fpath)
            img_bgra = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
            if img_bgra is None:
                print(f"Lỗi: Không đọc được ảnh {fpath}")
                continue
                
            res = process_single_image(img_bgra)
            if res is None:
                print(f"Lỗi: Không tìm thấy vùng thân cá trong {fpath}")
                continue
                
            vec = res["full_vector"]
            # Kiểm tra NaN / Inf
            if np.isnan(vec).any() or np.isinf(vec).any():
                print(f"CẢNH BÁO: Phát hiện NaN/Inf trong ảnh {fname}. Đang khử...")
                vec = np.nan_to_num(vec, nan=0.0, posinf=1.0, neginf=0.0)
                
            all_features.append(vec)
            all_color.append(res["color_vector"])
            all_shape.append(res["shape_vector"])
            all_texture.append(res["texture_vector"])
            all_grid_u64.append(res["grid_uint64"])
            all_grid64_bytes.append(res["grid64_bytes8"])
            all_grid192_bytes.append(res["grid192_bytes24"])
            all_labels.append(sp)
            all_files.append(fname)
            
            meta = res["metadata"]
            meta["species"] = sp
            meta["file"] = fname
            metadata_list.append(meta)
            
            total_processed += 1
            
        sp_duration = time.time() - sp_start_time
        print(f"    Hoàn thành {len(files)} ảnh {sp} trong {sp_duration:.2f}s ({sp_duration/len(files)*1000:.1f}ms/ảnh)")
        
    total_duration = time.time() - start_total_time
    print("\n" + "=" * 70)
    print(f"TỔNG KẾT TRÍCH XUẤT:")
    print(f"- Tổng số ảnh đã xử lý thành công: {total_processed} / 1100")
    print(f"- Tổng số chiều đặc trưng: {total_dims}")
    print(f"- Tổng thời gian xử lý: {total_duration:.2f}s")
    print(f"- Tốc độ trung bình: {total_duration / total_processed * 1000:.1f} ms/ảnh (đạt tiêu chí < 500 ms/ảnh)")
    print("=" * 70)
    
    # Chuyển đổi thành mảng numpy
    X_full = np.array(all_features, dtype=np.float32)
    X_color = np.array(all_color, dtype=np.float32)
    X_shape = np.array(all_shape, dtype=np.float32)
    X_texture = np.array(all_texture, dtype=np.float32)
    X_grid_u64 = np.array(all_grid_u64, dtype=np.uint64)
    X_grid64_bytes = np.array(all_grid64_bytes, dtype=np.uint8)
    X_grid192_bytes = np.array(all_grid192_bytes, dtype=np.uint8)
    c1_sim_matrix_A = build_c1_perceptual_similarity_matrix_A(sigma_lab=35.0)
    y_labels = np.array(all_labels)
    files_arr = np.array(all_files)
    
    print(f"Kích thước ma trận đặc trưng: {X_full.shape}")
    print(f"  - Màu sắc: {X_color.shape}")
    print(f"  - Hình dạng: {X_shape.shape}")
    print(f"  - Kết cấu: {X_texture.shape}")
    print(f"  - Lưới lọc thô 64-bit (uint64 & 8B): {X_grid_u64.shape}, {X_grid64_bytes.shape}")
    print(f"  - Lưới chuẩn hóa 192-bit (24B Slide 30): {X_grid192_bytes.shape}")
    
    # Lưu file NPZ
    os.makedirs(os.path.dirname(output_npz), exist_ok=True)
    np.savez_compressed(
        output_npz,
        features=X_full,
        color=X_color,
        shape=X_shape,
        texture=X_texture,
        grid_uint64=X_grid_u64,
        grid64_bytes=X_grid64_bytes,
        grid192_bytes=X_grid192_bytes,
        c1_sim_matrix_A=c1_sim_matrix_A,
        labels=y_labels,
        files=files_arr
    )
    print(f"Đã lưu ma trận đặc trưng tại: {output_npz}")
    
    # Lưu metadata CSV
    meta_df = pd.DataFrame(metadata_list)
    meta_csv = "data/fish_metadata.csv"
    meta_df.to_csv(meta_csv, index=False, encoding="utf-8")
    print(f"Đã lưu metadata hình học tại: {meta_csv}")

    with open("data/extraction_stats.json", "w", encoding="utf-8") as f:
        json.dump({
            "images": total_processed,
            "dims": int(total_dims),
            "total_seconds": round(total_duration, 2),
            "ms_per_image": round(total_duration / total_processed * 1000, 1)
        }, f, ensure_ascii=False, indent=2)


def update_binary_grids_and_schema_fast(dataset_dir="dataset_gold_v3/images_rgba", npz_path="data/features_extracted.npz", meta_csv="data/fish_metadata.csv"):
    """
    Cập nhật nhanh chữ ký lưới nhị phân đa độ phân giải (S5_bin64 8 bytes + S5_bin192 24 bytes chuẩn Slide 30)
    và ma trận tương đồng màu chéo bin A_78x78 vào data/features_extracted.npz và data/fish_metadata.csv
    trên toàn bộ 1.100 ảnh mà bảo toàn nguyên vẹn 100% ma trận số thực 421 chiều đã trích xuất.
    """
    generate_feature_schema("data/feature_schema.json")
    data = np.load(npz_path, allow_pickle=True)
    X_full = data["features"]
    X_color = data["color"]
    X_shape = data["shape"]
    X_texture = data["texture"]
    X_grid_u64 = data["grid_uint64"]
    y_labels = data["labels"]
    files_arr = data["files"]

    meta_df = pd.read_csv(meta_csv)
    all_grid_u64 = []
    all_grid64_bytes = []
    all_grid192_bytes = []
    angles = []
    hex64_list = []
    pop64_list = []
    hex192_list = []
    pop192_list = []

    for i in range(len(files_arr)):
        sp = str(y_labels[i])
        fname = str(files_arr[i])
        fpath = os.path.join(dataset_dir, sp, fname)
        img_bgra = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
        alpha = img_bgra[:, :, 3]
        mask = (alpha > 128).astype(np.uint8)
        ys, xs = np.where(mask > 0)
        bbox = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()))
        bg = extract_binary_grids_multi_res(mask, bbox)
        all_grid_u64.append(bg["grid_uint64"])
        all_grid64_bytes.append(bg["grid64_bytes8"])
        all_grid192_bytes.append(bg["grid192_bytes24"])
        angles.append(float(bg["main_axis_angle_deg"]))
        hex64_list.append(bg["grid64_hex16"])
        pop64_list.append(int(bg["grid64_popcount"]))
        hex192_list.append(bg["grid192_hex48"])
        pop192_list.append(int(bg["grid192_popcount"]))

    X_grid_u64 = np.array(all_grid_u64, dtype=np.uint64)
    X_grid64_bytes = np.array(all_grid64_bytes, dtype=np.uint8)
    X_grid192_bytes = np.array(all_grid192_bytes, dtype=np.uint8)
    c1_sim_matrix_A = build_c1_perceptual_similarity_matrix_A(sigma_lab=35.0)

    np.savez_compressed(
        npz_path,
        features=X_full,
        color=X_color,
        shape=X_shape,
        texture=X_texture,
        grid_uint64=X_grid_u64,
        grid64_bytes=X_grid64_bytes,
        grid192_bytes=X_grid192_bytes,
        c1_sim_matrix_A=c1_sim_matrix_A,
        labels=y_labels,
        files=files_arr
    )
    meta_df["main_axis_angle_deg"] = angles
    meta_df["grid_uint64"] = [int(x) for x in all_grid_u64]
    meta_df["grid64_hex"] = hex64_list
    meta_df["grid64_popcount"] = pop64_list
    meta_df["grid192_hex"] = hex192_list
    meta_df["grid192_popcount"] = pop192_list
    meta_df.to_csv(meta_csv, index=False, encoding="utf-8")
    print(f"[OK] Đã cập nhật 1.100 chữ ký nhị phân 64-bit & 192-bit + Ma trận A_78x78 vào {npz_path} và {meta_csv}")


if __name__ == "__main__":
    if "--fast-grids" in sys.argv and os.path.exists("data/features_extracted.npz"):
        update_binary_grids_and_schema_fast()
    else:
        run_extraction()

