# -*- coding: utf-8 -*-
"""
Module Quản trị Cơ sở dữ liệu Đa phương tiện SQLite (MMDB) và Chỉ mục Không gian:
- Tạo lược đồ bảng chuẩn SQLite (xuất DDL ra data/sql_mmdb_schema.sql):
  1. Fish_Metadata: Lưu siêu dữ liệu cấu trúc, hộp bao MBB và góc trục chính
  2. Shape_Binary_Index: Lưu chữ ký lưới nhị phân S5_bin64 (8B BLOB + 16 Hex) & S5_bin192 (24B BLOB + 48 Hex)
     chuẩn Lecture 11 Slide 30 & 34, chống tràn số nguyên có dấu int64 trên SQLite
  3. Fish_Feature_Vector: Lưu trữ kép (Dual Representation) gồm cả 3 Bộ đặc trưng riêng biệt
     (color_vector 135D, shape_vector 140D, texture_vector 146D) và vector tổng hợp (full_vector 421D)
  4. Feature_Schema: Lưu thứ tự chiều, tên đặc trưng, bộ đặc trưng, thành phần (C1..T4) và độ đo chuẩn
  5. Normalization_Stats: Lưu thống kê Z-score (mean_val, std_val), trung vị chuẩn hóa 2 cấp
     (component_median_d, group_median_d) và 5 thước đo Giá trị thông tin (CV, Fisher J, F_ANOVA, Eta^2, MI bits)
  6. CBIR_System_Config: Lưu trọng số tối ưu mặc định, ngưỡng phát hiện loài mới và Ma trận tương đồng màu A_78x78
- Nạp 1.100 bản ghi dữ liệu thật từ data/features_extracted.npz và data/fish_metadata.csv
- Xây dựng và lưu trữ chỉ mục Ball-Tree + gói tham số chuẩn hóa 2 cấp (data/ball_tree_index.pkl)
"""

import os
import sys
import json
import sqlite3
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DDL_SCRIPT = """-- =================================================================================
-- LƯỢC ĐỒ CƠ SỞ DỮ LIỆU ĐA PHƯƠNG TIỆN (MMDB SCHEMA - PHẦN 2 & PHẦN 3)
-- Hệ thống: Lưu trữ và Tìm kiếm Ảnh Cá Dựa trên Nội dung (Fish CBIR System)
-- Cấu trúc: 3 Bộ Đặc trưng Thị giác (Màu sắc 135D + Hình dạng 140D + Kết cấu 146D = 421D)
--           kèm Chữ ký Lưới Nhị phân Đa độ phân giải (S5_bin64 64-bit & S5_bin192 192-bit)
-- =================================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Fish_Metadata (
    image_id            TEXT PRIMARY KEY,
    species             TEXT NOT NULL,
    file_name           TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    xlb                 INTEGER NOT NULL,
    xub                 INTEGER NOT NULL,
    ylb                 INTEGER NOT NULL,
    yub                 INTEGER NOT NULL,
    width               INTEGER NOT NULL,
    height              INTEGER NOT NULL,
    aspect_ratio        REAL NOT NULL,
    fg_area             INTEGER NOT NULL,
    main_axis_angle_deg REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS Shape_Binary_Index (
    image_id            TEXT PRIMARY KEY,
    species             TEXT NOT NULL,
    grid64_blob         BLOB NOT NULL,      -- 8 bytes (lưới thô 8x8 = 64 bits, ngưỡng 15%)
    grid64_hex          TEXT NOT NULL,      -- Chuỗi 16 ký tự Hex (chống tràn int64 có dấu)
    grid64_popcount     INTEGER NOT NULL,   -- Số ô bit 1 trong lưới 64-bit
    grid192_blob        BLOB NOT NULL,      -- 24 bytes (lưới chuẩn hóa trục chính 192: 12x16 = 192 bits, Slide 30)
    grid192_hex         TEXT NOT NULL,      -- Chuỗi 48 ký tự Hex
    grid192_popcount    INTEGER NOT NULL,   -- Số ô bit 1 trong lưới 192-bit
    FOREIGN KEY (image_id) REFERENCES Fish_Metadata (image_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Fish_Feature_Vector (
    image_id            TEXT PRIMARY KEY,
    species             TEXT NOT NULL,
    color_vector        BLOB NOT NULL,      -- Bộ 1 (Màu sắc): 135 x float32 (540 bytes: C1 78D + C2 9D + C3 48D)
    shape_vector        BLOB NOT NULL,      -- Bộ 2 (Hình dạng): 140 x float32 (560 bytes: S1 8D + S2 32D + S3 7D + S4 29D + S5 64D)
    texture_vector      BLOB NOT NULL,      -- Bộ 3 (Kết cấu): 146 x float32 (584 bytes: T1 60D + T2 59D + T3 3D + T4 24D)
    full_vector         BLOB NOT NULL,      -- Vector tổng hợp: 421 x float32 (1.684 bytes)
    FOREIGN KEY (image_id) REFERENCES Fish_Metadata (image_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Feature_Schema (
    dim_index           INTEGER PRIMARY KEY,
    feature_name        TEXT NOT NULL UNIQUE,
    feature_group       TEXT NOT NULL,      -- 'color' | 'shape' | 'texture'
    component_code      TEXT NOT NULL,      -- 'C1'..'C3', 'S1'..'S5', 'T1'..'T4'
    distance_metric     TEXT NOT NULL       -- 'L1_CITYBLOCK' | 'ZSCORE_L2'
);

CREATE TABLE IF NOT EXISTS Normalization_Stats (
    dim_index           INTEGER PRIMARY KEY,
    mean_val            REAL NOT NULL,      -- Kỳ vọng Z-score trên 1.100 ảnh
    std_val             REAL NOT NULL,      -- Độ lệch chuẩn Z-score trên 1.100 ảnh
    component_median_d  REAL NOT NULL,      -- Trung vị khoảng cách cấp thành phần (med_m)
    group_median_d      REAL NOT NULL,      -- Trung vị khoảng cách cấp bộ/nhóm (med_G)
    cv_within           REAL,               -- Hệ số biến thiên nội loài CV_{within}
    fisher_j            REAL NOT NULL,      -- Tỷ số phương sai Fisher J = S_B / S_W
    f_anova             REAL NOT NULL,      -- Thống kê kiểm định F_ANOVA(5, 1094)
    eta_squared         REAL NOT NULL,      -- Tỷ lệ phương sai giải thích bởi loài eta^2 = J / (1 + J)
    mutual_info_bits    REAL NOT NULL,      -- Thông tin tương hỗ Shannon I(F_d; Y) (bits)
    primary_role        TEXT NOT NULL,      -- 'DUAL_PURPOSE' | 'DISCRIMINATION' | 'SIMILARITY' | 'COMPLEMENTARY' | 'GLOBAL_FISH_INVARIANT' | 'RESERVED_NEW_SPECIES'
    FOREIGN KEY (dim_index) REFERENCES Feature_Schema (dim_index) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS CBIR_System_Config (
    config_key          TEXT PRIMARY KEY,
    config_value_json   TEXT NOT NULL,
    matrix_blob         BLOB
);

CREATE INDEX IF NOT EXISTS idx_fish_species ON Fish_Metadata(species);
CREATE INDEX IF NOT EXISTS idx_shape_popcount ON Shape_Binary_Index(grid64_popcount, grid192_popcount);
CREATE INDEX IF NOT EXISTS idx_norm_role ON Normalization_Stats(primary_role);
"""


def init_database(
    db_path="data/fish_multimedia.db",
    npz_path="data/features_extracted.npz",
    meta_csv="data/fish_metadata.csv",
    schema_json="data/feature_schema.json",
    eval_json="data/evaluation_results.json",
    info_csv="data/feature_information_value_table.csv",
    sql_out="data/sql_mmdb_schema.sql",
):
    print("=" * 70)
    print("KHỞI TẠO CƠ SỞ DỮ LIỆU ĐA PHƯƠNG TIỆN SQLITE VÀ CHỈ MỤC KHÔNG GIAN")
    print(f"Đường dẫn DB: {db_path}")
    print("=" * 70)

    os.makedirs(os.path.dirname(sql_out), exist_ok=True)
    with open(sql_out, "w", encoding="utf-8") as f:
        f.write(DDL_SCRIPT)
    print(f"-> Đã xuất lược đồ SQL DDL chuẩn tại: {sql_out}")

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(DDL_SCRIPT)

    # 1. Nạp Feature_Schema
    with open(schema_json, "r", encoding="utf-8") as f:
        schema_data = json.load(f)

    schema_records = []
    for d in schema_data["dimensions"]:
        comp = d.get("component", d["name"].split("_")[1].upper())
        metric = d.get("metric", "L1_CITYBLOCK" if comp in ("C1", "C3", "T2") else "ZSCORE_L2")
        schema_records.append((int(d["index"]), d["name"], d["group"], comp, metric))

    cursor.executemany("INSERT INTO Feature_Schema VALUES (?, ?, ?, ?, ?)", schema_records)
    print(f"-> Đã nạp {len(schema_records)} định nghĩa chiều vào Feature_Schema.")

    # 2. Đọc thông số trung vị 2 cấp từ evaluation_results.json và Giá trị thông tin từ feature_information_value_table.csv
    comp_meds = {}
    group_meds = {"color": 1.0, "shape": 1.0, "texture": 1.0}
    default_weights = [0.5, 0.3, 0.2]
    novelty_threshold = 0.500
    novelty_auroc = 0.985
    if os.path.exists(eval_json):
        with open(eval_json, "r", encoding="utf-8") as f:
            ev = json.load(f)
        nm = ev.get("normalization_medians", {})
        comp_meds = nm.get("component_medians", {})
        group_meds = nm.get("group_medians", group_meds)
        default_weights = ev.get("default_weights", default_weights)
        novelty_threshold = ev.get("novelty", {}).get("threshold_median", ev.get("novelty", {}).get("threshold_mean", novelty_threshold))
        novelty_auroc = ev.get("novelty", {}).get("mean_auroc", novelty_auroc)

    info_map = {}
    if os.path.exists(info_csv):
        info_df = pd.read_csv(info_csv)
        for _, r in info_df.iterrows():
            info_map[int(r["dim_index"])] = r

    # 3. Nạp Dữ liệu & Tính toán Thống kê Chuẩn hóa + Giá trị thông tin
    data = np.load(npz_path, allow_pickle=True)
    X_full = data["features"]
    X_color = data["color"]
    X_shape = data["shape"]
    X_texture = data["texture"]
    X_grid64_bytes = data["grid64_bytes"] if "grid64_bytes" in data else None
    X_grid192_bytes = data["grid192_bytes"] if "grid192_bytes" in data else None
    c1_sim_matrix_A = data["c1_sim_matrix_A"] if "c1_sim_matrix_A" in data else None
    y = data["labels"]
    files = data["files"]

    scaler = StandardScaler().fit(X_full)
    raw_std = X_full.astype(np.float64).std(axis=0)
    eff_std = np.where(raw_std < 1e-6, 1.0, np.maximum(raw_std, 2e-3))
    scaler.scale_ = eff_std.copy()
    norm_records = []
    for i, (_, fname, fgroup, comp, _) in enumerate(schema_records):
        m = float(scaler.mean_[i])
        s = float(eff_std[i])
        c_med = float(comp_meds.get(comp, 1.0))
        g_med = float(group_meds.get(fgroup, 1.0))
        if i in info_map:
            ir = info_map[i]
            cv_w = None if pd.isna(ir["cv_within"]) else float(ir["cv_within"])
            jf = float(ir["fisher_j"])
            fa = float(ir["f_anova"])
            et = float(ir["eta_squared"])
            mi = float(ir["mutual_info_bits"])
            role = str(ir["primary_role"])
        else:
            cv_w, jf, fa, et, mi, role = None, 0.0, 0.0, 0.0, 0.0, "COMPLEMENTARY"
        norm_records.append((i, m, s, c_med, g_med, cv_w, jf, fa, et, mi, role))

    cursor.executemany(
        "INSERT INTO Normalization_Stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        norm_records,
    )
    print(f"-> Đã lưu thông số chuẩn hóa 2 cấp (Z-score + med_m + med_G) và 5 chỉ số Giá trị thông tin cho {len(norm_records)} chiều.")

    # 4. Nạp Fish_Metadata, Shape_Binary_Index và Fish_Feature_Vector
    meta_df = pd.read_csv(meta_csv)
    meta_records = []
    binary_records = []
    vector_records = []

    for i in range(len(files)):
        fname = str(files[i])
        sp = str(y[i])
        img_id = f"{sp}_{i+1:04d}"

        row = meta_df[(meta_df["file"] == fname) & (meta_df["species"] == sp)].iloc[0]
        fpath = f"dataset_gold_v3/images_rgba/{sp}/{fname}"
        angle_deg = float(row["main_axis_angle_deg"]) if "main_axis_angle_deg" in row else 0.0

        meta_records.append((
            img_id, sp, fname, fpath,
            int(row["xlb"]), int(row["xub"]), int(row["ylb"]), int(row["yub"]),
            int(row["width"]), int(row["height"]), float(row["aspect_ratio"]),
            int(row["fg_area"]), angle_deg
        ))

        if X_grid64_bytes is not None and X_grid192_bytes is not None:
            b64 = X_grid64_bytes[i].tobytes()
            h64 = str(row["grid64_hex"]) if "grid64_hex" in row else b64.hex()
            p64 = int(row["grid64_popcount"]) if "grid64_popcount" in row else int(np.unpackbits(X_grid64_bytes[i]).sum())
            b192 = X_grid192_bytes[i].tobytes()
            h192 = str(row["grid192_hex"]) if "grid192_hex" in row else b192.hex()
            p192 = int(row["grid192_popcount"]) if "grid192_popcount" in row else int(np.unpackbits(X_grid192_bytes[i]).sum())
        else:
            b64 = np.zeros(8, dtype=np.uint8).tobytes()
            h64, p64 = b64.hex(), 0
            b192 = np.zeros(24, dtype=np.uint8).tobytes()
            h192, p192 = b192.hex(), 0

        binary_records.append((img_id, sp, b64, h64, p64, b192, h192, p192))

        c_blob = X_color[i].tobytes()
        s_blob = X_shape[i].tobytes()
        t_blob = X_texture[i].tobytes()
        f_blob = X_full[i].tobytes()
        vector_records.append((img_id, sp, c_blob, s_blob, t_blob, f_blob))

    cursor.executemany("INSERT INTO Fish_Metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", meta_records)
    cursor.executemany("INSERT INTO Shape_Binary_Index VALUES (?, ?, ?, ?, ?, ?, ?, ?)", binary_records)
    cursor.executemany("INSERT INTO Fish_Feature_Vector VALUES (?, ?, ?, ?, ?, ?)", vector_records)

    # 5. Lưu CBIR_System_Config
    sys_configs = [
        ("default_weights", json.dumps({"color": default_weights[0], "shape": default_weights[1], "texture": default_weights[2]}), None),
        ("group_medians", json.dumps(group_meds), None),
        ("component_medians", json.dumps(comp_meds), None),
        ("novelty_detection", json.dumps({"youden_threshold": round(float(novelty_threshold), 4), "auroc": round(float(novelty_auroc), 4)}), None),
        ("c1_perceptual_matrix_A", json.dumps({"shape": [78, 78], "sigma_lab": 35.0}), c1_sim_matrix_A.tobytes() if c1_sim_matrix_A is not None else None),
    ]
    cursor.executemany("INSERT INTO CBIR_System_Config VALUES (?, ?, ?)", sys_configs)

    conn.commit()
    conn.close()
    print(f"-> Đã nạp thành công {len(meta_records)} bản ghi vào 6 bảng CSDL SQLite: {db_path}")

    # 6. Huấn luyện và lưu Chỉ mục Ball-Tree kèm tham số chuẩn hóa 2 cấp
    X_full_scaled = scaler.transform(X_full)
    ball_tree = NearestNeighbors(n_neighbors=10, algorithm="ball_tree", metric="euclidean").fit(X_full_scaled)

    index_bundle = {
        "scaler": scaler,
        "ball_tree": ball_tree,
        "component_medians": comp_meds,
        "group_medians": group_meds,
        "default_weights": default_weights,
        "novelty_threshold": novelty_threshold,
        "c1_sim_matrix_A": c1_sim_matrix_A,
        "image_ids": [r[0] for r in meta_records],
        "species": list(y),
        "files": list(files),
    }

    index_path = "data/ball_tree_index.pkl"
    with open(index_path, "wb") as f:
        pickle.dump(index_bundle, f)

    print(f"-> Đã xây dựng và lưu trữ chỉ mục không gian Ball-Tree + gói chuẩn hóa 2 cấp tại: {index_path}")
    print("=" * 70)


if __name__ == "__main__":
    init_database()

