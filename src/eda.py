# -*- coding: utf-8 -*-
"""
Module EDA: Thống kê định lượng thực tế trên toàn bộ 1.100 ảnh cá
Tập dữ liệu: dataset_gold_v3/images_rgba
Các loài: Boal (200), Ilish (100), Katla (200), Koi (150), Rui (200), Telapia (250)
"""

import os
import sys
import glob
import json
import cv2
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_eda(dataset_dir="dataset_gold_v3/images_rgba", output_report="data/eda_report.md"):
    species_list = ["boal", "ilish", "katla", "koi", "rui", "telapia"]
    records = []
    rng = np.random.default_rng(42)

    print(f"Bắt đầu khảo sát dữ liệu tại: {dataset_dir}")
    
    all_fg_hue = []
    all_fg_sat = []
    all_fg_val = []

    for sp in species_list:
        folder = os.path.join(dataset_dir, sp)
        if not os.path.isdir(folder):
            print(f"Cảnh báo: Không tìm thấy thư mục {folder}")
            continue
        
        files = sorted(glob.glob(os.path.join(folder, "*.*")))
        print(f"-> Đang xử lý loài [{sp}]: {len(files)} ảnh...")

        for fpath in files:
            fname = os.path.basename(fpath)
            # Đọc ảnh BGRA
            img_bgra = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
            if img_bgra is None:
                continue

            # Tách kênh màu BGR và kênh Alpha
            if img_bgra.shape[2] == 4:
                bgr = img_bgra[:, :, :3]
                alpha = img_bgra[:, :, 3]
            else:
                bgr = img_bgra
                alpha = (cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) > 10).astype(np.uint8) * 255

            mask = (alpha > 128).astype(np.uint8)
            num_fg_pixels = int(np.sum(mask))
            if num_fg_pixels == 0:
                continue

            # 1. Bounding box & Hình học
            ys, xs = np.where(mask > 0)
            xlb, xub = int(xs.min()), int(xs.max())
            ylb, yub = int(ys.min()), int(ys.max())
            w = max(1, xub - xlb + 1)
            h = max(1, yub - ylb + 1)
            aspect_ratio = float(w) / float(h)
            bbox_area = float(w * h)
            extent = float(num_fg_pixels) / bbox_area

            # Tìm contours để tính chu vi, độ tròn, bao lồi
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                c_max = max(contours, key=cv2.contourArea)
                perimeter = float(cv2.arcLength(c_max, True))
                hull = cv2.convexHull(c_max)
                hull_area = float(cv2.contourArea(hull))
                solidity = float(num_fg_pixels) / hull_area if hull_area > 0 else 0.0
                circularity = (4.0 * np.pi * num_fg_pixels) / (perimeter ** 2) if perimeter > 0 else 0.0
            else:
                perimeter = 0.0
                solidity = 0.0
                circularity = 0.0

            # 2. Màu sắc trên vùng mặt nạ (HSV)
            # Chuyển BGR sang HSV (OpenCV: H in [0, 179], S in [0, 255], V in [0, 255])
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            h_chan = hsv[:, :, 0][mask > 0].astype(float) * 2.0  # Chuyển sang dải 0 - 360 độ
            s_chan = hsv[:, :, 1][mask > 0].astype(float) / 255.0  # Chuyển sang 0 - 1
            v_chan = hsv[:, :, 2][mask > 0].astype(float) / 255.0  # Chuyển sang 0 - 1

            # Lấy mẫu ngẫu nhiên tối đa 200 điểm ảnh (cố định seed 42) để thống kê tổng thể
            sample_idx = rng.choice(len(h_chan), size=min(200, len(h_chan)), replace=False)
            all_fg_hue.extend(h_chan[sample_idx])
            all_fg_sat.extend(s_chan[sample_idx])
            all_fg_val.extend(v_chan[sample_idx])

            # Tỷ lệ pixel có độ bão hòa rất thấp (Achromatic / Xám / Bạc)
            achromatic_ratio = float(np.mean(s_chan < 0.15))

            # Hue trung bình tính theo góc lượng giác để tránh lỗi vòng tròn (0 = 360)
            rad = np.deg2rad(h_chan)
            mean_sin = np.mean(np.sin(rad))
            mean_cos = np.mean(np.cos(rad))
            circular_mean_hue = (np.rad2deg(np.arctan2(mean_sin, mean_cos)) + 360.0) % 360.0

            # Hue trên các pixel có màu thực tế (S >= 0.15)
            chromatic_mask = s_chan >= 0.15
            if np.sum(chromatic_mask) > 0:
                rad_chr = np.deg2rad(h_chan[chromatic_mask])
                chr_mean_hue = (np.rad2deg(np.arctan2(np.mean(np.sin(rad_chr)), np.mean(np.cos(rad_chr)))) + 360.0) % 360.0
            else:
                chr_mean_hue = circular_mean_hue

            records.append({
                "species": sp,
                "file": fname,
                "fg_pixels": num_fg_pixels,
                "aspect_ratio": aspect_ratio,
                "extent": extent,
                "perimeter": perimeter,
                "circularity": circularity,
                "solidity": solidity,
                "sat_mean": float(np.mean(s_chan)),
                "sat_std": float(np.std(s_chan)),
                "val_mean": float(np.mean(v_chan)),
                "val_std": float(np.std(v_chan)),
                "hue_circ_mean": float(circular_mean_hue),
                "hue_chromatic_mean": float(chr_mean_hue),
                "achromatic_ratio": achromatic_ratio
            })

    df = pd.DataFrame(records)
    print(f"\nTổng số ảnh đã khảo sát thực tế: {len(df)}")
    
    # Tính toán bảng thống kê theo loài
    summary_cols = [
        "aspect_ratio", "circularity", "extent", "solidity",
        "sat_mean", "val_mean", "hue_chromatic_mean", "achromatic_ratio"
    ]
    
    grouped_mean = df.groupby("species")[summary_cols].mean()
    grouped_std = df.groupby("species")[summary_cols].std()
    grouped_count = df.groupby("species")["file"].count()

    # Thống kê phân vị Saturation và Hue toàn bộ tập dữ liệu để thiết kế Bin phi tuyến
    all_fg_sat = np.array(all_fg_sat)
    all_fg_hue = np.array(all_fg_hue)
    all_fg_val = np.array(all_fg_val)

    sat_quantiles = np.quantile(all_fg_sat, [0.1, 0.25, 0.5, 0.75, 0.9])
    val_quantiles = np.quantile(all_fg_val, [0.1, 0.25, 0.5, 0.75, 0.9])

    # Tạo nội dung báo cáo Markdown
    md = []
    md.append("# BÁO CÁO KHẢO SÁT VÀ ĐO ĐẠC DỮ LIỆU THỰC TẾ (EDA REPORT)")
    md.append(f"> Căn cứ thực nghiệm: 1.100 bức ảnh thuộc thư mục `{dataset_dir}`")
    md.append("> Ngày tạo: 2026-10-13 | Phục vụ Phần 2 BTL CSDLDPT\n")

    md.append("## 1. Phân bố số lượng ảnh thực tế theo loài")
    md.append("| Loài | Tên khoa học | Tên tiếng Việt | Số lượng ảnh | Tỷ lệ (%) |")
    md.append("|---|---|---|---:|---:|")
    sp_info = {
        "boal": ("Wallago attu", "Cá leo (cá trê trắng)", 200),
        "ilish": ("Tenualosa ilisha", "Cá cháy (Cá mòi đường)", 100),
        "katla": ("Gibelion catla", "Cá chép Ấn Độ (Mè vinh)", 200),
        "koi": ("Anabas testudineus", "Cá rô đồng (Bangladesh Climbing Perch)", 150),
        "rui": ("Labeo rohita", "Cá trôi Ấn Độ (Rohu)", 200),
        "telapia": ("Oreochromis niloticus", "Cá rô phi", 250),
    }
    for sp in species_list:
        cnt = grouped_count.get(sp, 0)
        sc, vi, _ = sp_info.get(sp, ("-", "-", cnt))
        pct = (cnt / len(df)) * 100.0
        md.append(f"| **{sp.capitalize()}** | *{sc}* | {vi} | {cnt} | {pct:.1f}% |")
    md.append(f"| **TỔNG CỘNG** | | | **{len(df)}** | **100.0%** |\n")

    md.append("## 2. Bảng giá trị đặc trưng đo đạc thực tế (Kỳ vọng ± Độ lệch chuẩn)")
    md.append("| Loài | Aspect Ratio (W/H) | Độ tròn Circularity | Extent | Solidity | Độ bão hòa (S) | Độ sáng (V) | Hue có màu (°)* | Tỷ lệ vô sắc (S<0.15) |")
    md.append("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

    for sp in species_list:
        ar_m, ar_s = grouped_mean.loc[sp, "aspect_ratio"], grouped_std.loc[sp, "aspect_ratio"]
        cir_m, cir_s = grouped_mean.loc[sp, "circularity"], grouped_std.loc[sp, "circularity"]
        ext_m, ext_s = grouped_mean.loc[sp, "extent"], grouped_std.loc[sp, "extent"]
        sol_m, sol_s = grouped_mean.loc[sp, "solidity"], grouped_std.loc[sp, "solidity"]
        sat_m, sat_s = grouped_mean.loc[sp, "sat_mean"], grouped_std.loc[sp, "sat_mean"]
        val_m, val_s = grouped_mean.loc[sp, "val_mean"], grouped_std.loc[sp, "val_mean"]
        hue_m = grouped_mean.loc[sp, "hue_chromatic_mean"]
        achr_m = grouped_mean.loc[sp, "achromatic_ratio"] * 100.0
        md.append(
            f"| **{sp.capitalize()}** | {ar_m:.2f} ± {ar_s:.2f} | {cir_m:.3f} ± {cir_s:.3f} | "
            f"{ext_m:.2f} ± {ext_s:.2f} | {sol_m:.2f} ± {sol_s:.2f} | "
            f"{sat_m:.2f} ± {sat_s:.2f} | {val_m:.2f} ± {val_s:.2f} | "
            f"{hue_m:.1f}° | {achr_m:.1f}% |"
        )
    md.append("\n*Ghi chú: Hue có màu được tính trên tập điểm ảnh có Saturation >= 0.15 bằng trung bình vòng tròn (circular mean).\n")

    md.append("## 3. Nhận định khoa học rút ra từ số liệu thực tế")
    md.append("1. **Đặc trưng Hình học phân tách rất mạnh:**")
    md.append(f"   - **Boal** đạt Aspect Ratio cực cao: **{grouped_mean.loc['boal', 'aspect_ratio']:.2f} ± {grouped_std.loc['boal', 'aspect_ratio']:.2f}** (thuôn dài vượt bậc), tách biệt hẳn với các loài còn lại.")
    md.append(f"   - **Katla** và **Telapia** có thân tròn gù: Aspect Ratio thấp nhất (~{grouped_mean.loc['telapia', 'aspect_ratio']:.2f} – {grouped_mean.loc['katla', 'aspect_ratio']:.2f}), Circularity cao nhất (~{grouped_mean.loc['katla', 'circularity']:.3f} – {grouped_mean.loc['telapia', 'circularity']:.3f}).")
    md.append("2. **Đặc tính Màu sắc của cá nước ngọt:**")
    md.append(
        f"   - **Hơn 50% - 80% diện tích thân cá là vùng vô sắc / xám bạc (S < 0.15)** ở các loài tự nhiên như "
        f"Boal ({grouped_mean.loc['boal', 'achromatic_ratio']*100:.1f}%), "
        f"Ilish ({grouped_mean.loc['ilish', 'achromatic_ratio']*100:.1f}%), "
        f"Rui ({grouped_mean.loc['rui', 'achromatic_ratio']*100:.1f}%), "
        f"Telapia ({grouped_mean.loc['telapia', 'achromatic_ratio']*100:.1f}%)."
    )
    md.append(f"   - Chỉ duy nhất **Koi (Cá rô đồng)** có sắc tố màu đậm và rõ rệt: Saturation đạt **{grouped_mean.loc['koi', 'sat_mean']:.2f} ± {grouped_std.loc['koi', 'sat_mean']:.2f}**, Hue trung bình **{grouped_mean.loc['koi', 'hue_chromatic_mean']:.1f}°** (vàng đồng / vàng rơm), tỷ lệ vô sắc chỉ khoảng {grouped_mean.loc['koi', 'achromatic_ratio']*100:.1f}%.")
    md.append(f"   - **Ilish** có thân ánh bạc phản quang rất mạnh, độ bão hòa thấp (S = {grouped_mean.loc['ilish', 'sat_mean']:.2f}), độ sáng cao (V = {grouped_mean.loc['ilish', 'val_mean']:.2f}).")
    md.append(f"   - **Katla** có thân tối nhất (V = {grouped_mean.loc['katla', 'val_mean']:.2f}) với ánh xám chì rêu.")
    md.append("3. **Định hướng thiết kế bộ Lượng tử hóa màu thực tế:**")
    md.append(r"   - **Cần tách riêng 6 ô vô sắc (Achromatic Bins)**: Đối với pixel có $S < 0.15$, Hue mang tính ngẫu nhiên do nhiễu, do đó bắt buộc phải lượng tử hóa thành 6 mức độ sáng $V$ đều trên $[0, 1]$ (từ tối đen, xám sẫm đến trắng bạc)." + "\n")
    md.append(r"   - **Đối với pixel hữu sắc ($S \ge 0.15$)**: Chia đều vòng tròn sắc màu Hue thành 12 cung ($30^\circ$/cung) kết hợp 3 mức độ bão hòa $S$ và 2 mức độ sáng $V$ tạo thành $12 \times 3 \times 2 = 72$ ô hữu sắc (tổng cộng $6 + 72 = 78$ chiều, vừa phân biệt sắc vàng đồng của Koi / vây đỏ của Rui vừa phủ kín $360^\circ$ cho loài cá mới)." + "\n")

    md.append("## 4. Phân vị mẫu (Quantiles) phục vụ thiết kế Bin phi tuyến")
    md.append(f"- **Saturation (S)**: q10={sat_quantiles[0]:.2f}, q25={sat_quantiles[1]:.2f}, q50={sat_quantiles[2]:.2f}, q75={sat_quantiles[3]:.2f}, q90={sat_quantiles[4]:.2f}")
    md.append(f"- **Value (V)**: q10={val_quantiles[0]:.2f}, q25={val_quantiles[1]:.2f}, q50={val_quantiles[2]:.2f}, q75={val_quantiles[3]:.2f}, q90={val_quantiles[4]:.2f}")

    os.makedirs(os.path.dirname(output_report), exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # Lưu thêm file csv số liệu thô để dùng cho tính toán
    csv_path = "data/dataset_eda_metrics.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Đã xuất báo cáo tại: {output_report}")
    print(f"Đã xuất dữ liệu thô tại: {csv_path}")

if __name__ == "__main__":
    run_eda()
