# -*- coding: utf-8 -*-
"""
Module trích xuất đặc trưng Kết cấu bề mặt (Texture Features) cho ảnh cá (146 chiều):
1. T1: Ma trận đồng xuất hiện mức xám đa hướng đa khoảng cách (Foreground-Only GLCM): 60 chiều
   - Lượng tử hóa 16 mức xám thuộc thân cá (1..16), gán nền bằng 0 và cắt ma trận con [1:, 1:]
     để chỉ đếm các cặp pixel mà CẢ HAI điểm đều nằm trong vùng thân cá (đã co mặt nạ 2px).
   - 3 khoảng cách d = [1, 3, 5] (tránh trùng lặp làm tròn bước nhảy ở góc 45, 135 độ)
   - 4 hướng độc lập theta = [0, 45, 90, 135] độ
   - 5 chỉ số Haralick: Contrast, Dissimilarity, Homogeneity, Energy, Correlation (5 x 3 x 4 = 60 chiều)
2. T2: Mẫu nhị phân cục bộ LBP đồng nhất có hướng (NRI-Uniform LBP): 59 chiều
   - method='nri_uniform' (P=8, R=1) -> 58 mẫu đồng nhất + 1 mẫu non-uniform
   - Sửa triệt để lỗi E1 (bản cũ 49 cột bằng 0 do nhầm uniform riu2)
3. T3: Đặc trưng Tamura (Độ thô vảy cá theo đề 2.3 và slide L11): 3 chiều
   - Coarseness (F_crs - độ thô vảy qua các thang cửa sổ đa tỷ lệ)
   - Contrast (F_con - độ tương phản mức xám dựa trên độ lệch chuẩn và kurtosis)
   - Directionality (F_dir - độ định hướng dựa trên biểu đồ góc gradient Sobel)
4. T4: Năng lượng lọc Gabor đa hướng đa tần số (MPEG-7 Homogeneous Texture): 24 chiều
   - 3 bước sóng lambda = [4, 8, 16] x 4 hướng theta = [0, 45, 90, 135] độ = 12 bộ lọc
   - Mỗi bộ lọc tính Mean và Std năng lượng trên vùng thân cá: 12 x 2 = 24 chiều
Tổng số chiều Texture: 60 + 59 + 3 + 24 = 146 chiều.
"""

import numpy as np
import cv2
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

def extract_glcm_features(gray_img, mask, bbox):
    """
    T1: Trích xuất đặc trưng GLCM đa hướng trên vùng thân cá (60 chiều).
    - Co mặt nạ 2px để loại bỏ viền biên cá - nền.
    - Lượng tử hóa vùng thân cá về 16 mức (1..16), vùng nền gán bằng 0.
    - Tính GLCM 17 mức rồi trích ma trận con [1:, 1:, :, :] và chuẩn hóa tổng bằng 1,
      đảm bảo CHỈ đếm các cặp pixel mà cả 2 điểm đều thuộc thân cá (không lẫn cặp nền-nền hay cá-nền).
    - Sử dụng khoảng cách d = [1, 3, 5] để các bước nhảy chéo round(d*cos(45°)) = [1, 2, 4] hoàn toàn phân biệt.
    """
    xlb, xub, ylb, yub = bbox
    crop_gray = gray_img[ylb:yub+1, xlb:xub+1]
    crop_mask = mask[ylb:yub+1, xlb:xub+1]
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded_mask = cv2.erode(crop_mask, kernel, iterations=2)
    if np.sum(eroded_mask > 0) < 50:
        eroded_mask = crop_mask
        
    if np.sum(eroded_mask > 0) == 0:
        return np.zeros(60, dtype=np.float32)
        
    # Lượng tử hóa mức xám thân cá về 1..16, pixel ngoài mặt nạ gán bằng 0
    quantized = (np.clip(crop_gray.astype(np.int32) // 16, 0, 15).astype(np.uint8) + 1)
    quantized[eroded_mask == 0] = 0
    
    distances = [1, 3, 5]
    angles = [0.0, np.pi/4.0, np.pi/2.0, 3.0*np.pi/4.0]
    
    glcm_full = graycomatrix(
        quantized,
        distances=distances,
        angles=angles,
        levels=17,
        symmetric=True,
        normed=False
    )
    # Chỉ giữ ma trận con 16x16 của các cặp pixel cùng thuộc thân cá (mức 1..16)
    glcm_fg = glcm_full[1:, 1:, :, :].astype(np.float64)
    sums = glcm_fg.sum(axis=(0, 1), keepdims=True)
    glcm_fg = np.divide(glcm_fg, sums, out=np.zeros_like(glcm_fg), where=sums > 0)
    
    props = ["contrast", "dissimilarity", "homogeneity", "energy", "correlation"]
    dir_features = []
    for p in props:
        vals = graycoprops(glcm_fg, p)  # shape (3, 4)
        dir_features.extend(vals.flatten())
        
    dir_features = np.array(dir_features, dtype=np.float32)
    dir_features = np.nan_to_num(dir_features, nan=0.0, posinf=1.0, neginf=0.0)
    return dir_features

def extract_lbp_features(gray_img, mask, bbox):
    """
    T2: Trích xuất đặc trưng Non-Rotation-Invariant Uniform LBP (P=8, R=1): 59 bins
    Sửa triệt để lỗi E1: dùng method='nri_uniform' tạo đúng 59 mẫu (58 uniform + 1 non-uniform).
    Chỉ thống kê trên các pixel thuộc thân cá (eroded mask 1px).
    """
    xlb, xub, ylb, yub = bbox
    crop_gray = gray_img[ylb:yub+1, xlb:xub+1]
    crop_mask = mask[ylb:yub+1, xlb:xub+1]
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded_mask = cv2.erode(crop_mask, kernel, iterations=1)
    if np.sum(eroded_mask > 0) < 50:
        eroded_mask = crop_mask
        
    # method='nri_uniform' với P=8 có 59 giá trị (0..58)
    lbp_nri = local_binary_pattern(crop_gray, P=8, R=1, method='nri_uniform')
    fg_lbp = lbp_nri[eroded_mask > 0]
    
    if len(fg_lbp) == 0:
        return np.zeros(59, dtype=np.float32)
        
    hist, _ = np.histogram(fg_lbp, bins=59, range=(0, 59))
    hist = hist.astype(np.float32) / float(len(fg_lbp))
    return hist

def extract_tamura_features(gray_img, mask, bbox):
    """
    T3: Trích xuất 3 đặc trưng Tamura (Độ thô vảy cá theo Đề 2.3 và Slide L11):
    1. Coarseness (F_crs): Độ thô bề mặt qua tìm kích thước cửa sổ tối ưu 2^k (k=1..4)
    2. Contrast (F_con): Độ tương phản dựa trên độ lệch chuẩn mức xám và hệ số nhọn kurtosis
    3. Directionality (F_dir): Độ định hướng dựa trên biểu đồ hướng gradient Sobel
    Tổng: 3 chiều.
    """
    xlb, xub, ylb, yub = bbox
    crop_gray = gray_img[ylb:yub+1, xlb:xub+1]
    crop_mask = mask[ylb:yub+1, xlb:xub+1]
    
    fg_mask = crop_mask > 0
    fg_pixels = crop_gray[fg_mask].astype(np.float64)
    if len(fg_pixels) < 50:
        return np.zeros(3, dtype=np.float32)
        
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded_mask = cv2.erode(crop_mask, kernel, iterations=2)
    eroded_fg = (eroded_mask > 0) if np.sum(eroded_mask > 0) >= 50 else fg_mask
    
    # 1. Contrast: F_con = sigma / (alpha4 ** 0.25)
    fg_mean = float(np.mean(fg_pixels))
    sigma = np.std(fg_pixels)
    if sigma < 1e-5:
        f_con = 0.0
    else:
        mu4 = np.mean((fg_pixels - fg_mean) ** 4)
        alpha4 = max(1.0, mu4 / (sigma ** 4))
        f_con = float(sigma / (alpha4 ** 0.25)) / 128.0  # chuẩn hóa về dải xấp xỉ [0, 1]
        
    # Điền vùng nền ngoài mặt nạ bằng mức xám trung bình của thân cá để khử nhiễu biên đen 0
    gray_f64 = np.where(fg_mask, crop_gray.astype(np.float64), fg_mean)
    
    # 2. Coarseness: Tìm thang đo tối ưu qua 4 thang (2, 4, 8, 16) bằng cv2.boxFilter và dịch mảng không cuộn biên
    scales = [1, 2, 3, 4]
    diff_maps = []
    for k in scales:
        s = 1 << k            # 2^k: 2, 4, 8, 16
        shift = 1 << (k - 1)  # 2^(k-1): 1, 2, 4, 8
        box_avg = cv2.boxFilter(gray_f64, -1, (s, s), normalize=True, borderType=cv2.BORDER_REPLICATE)
        pad_h = np.pad(box_avg, ((0, 0), (shift, shift)), mode="edge")
        d_h = np.abs(pad_h[:, 2 * shift:] - pad_h[:, :-2 * shift])
        pad_v = np.pad(box_avg, ((shift, shift), (0, 0)), mode="edge")
        d_v = np.abs(pad_v[2 * shift:, :] - pad_v[:-2 * shift, :])
        diff_maps.append(np.maximum(d_h, d_v))
        
    diff_stack = np.stack(diff_maps, axis=0)  # (4, h, w)
    best_scale_idx = np.argmax(diff_stack, axis=0)  # 0..3
    s_opt_map = 2.0 ** (best_scale_idx + 1)
    f_crs = float(np.mean(s_opt_map[eroded_fg])) / 16.0  # chuẩn hóa theo max scale
    
    # 3. Directionality: Biểu đồ hướng gradient Sobel nội vùng thân cá (đã co biên) trong [0, pi)
    # Công thức Tamura chuẩn (Mục 2.3.3): F_dir = 1 - r * n_p * sum_{p=1}^{n_p} sum_{phi in w_p} (phi - phi_p)^2 * H_D(phi)
    gray_f32 = gray_f64.astype(np.float32)
    gx = cv2.Sobel(gray_f32, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f32, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    theta = np.mod(np.arctan2(gy, gx) + np.pi / 2.0, np.pi)  # Chuẩn hóa góc hướng cạnh về đúng [0, pi)
    
    mag_fg = mag[eroded_fg]
    theta_fg = theta[eroded_fg]
    thresh = float(np.mean(mag_fg))
    valid_dirs = theta_fg[mag_fg > thresh]
    
    if len(valid_dirs) < 20:
        f_dir = 0.0
    else:
        n_bins = 16
        hist, _ = np.histogram(valid_dirs, bins=n_bins, range=(0.0, np.pi))
        hist = hist.astype(np.float64)
        hist_sum = float(np.sum(hist))
        if hist_sum > 0:
            hd = hist / hist_sum
            max_h = float(np.max(hd))
            # Xác định các đỉnh chủ đạo phi_p trên biểu đồ tuần hoàn 16 bin [0, pi):
            # Đỉnh ứng viên phải là cực đại cục bộ vượt mức phân bố đều (1.20 / n_bins)
            cand_peaks = [
                i for i in range(n_bins)
                if hd[i] >= hd[(i - 1) % n_bins]
                and hd[i] > hd[(i + 1) % n_bins]
                and hd[i] > (1.20 / n_bins)
                and hd[i] >= 0.25 * max_h
            ]
            if not cand_peaks:
                peaks = [int(np.argmax(hd))]
            else:
                # Lọc nhiễu gợn sóng nông theo tiêu chuẩn Tamura (1978): hai đỉnh chủ đạo liền kề
                # phải ngăn cách bởi thung lũng sâu (đáy thung lũng <= 0.50 * đỉnh thấp hơn)
                peaks = list(cand_peaks)
                changed = True
                while changed and len(peaks) > 1:
                    changed = False
                    for idx_p in range(len(peaks)):
                        p1 = peaks[idx_p]
                        p2 = peaks[(idx_p + 1) % len(peaks)]
                        arc_len = (p2 - p1) % n_bins
                        arc_bins = [(p1 + step) % n_bins for step in range(1, arc_len)]
                        v_val = min(hd[b] for b in arc_bins) if arc_bins else min(hd[p1], hd[p2])
                        if v_val > 0.50 * min(hd[p1], hd[p2]):
                            drop_idx = idx_p if hd[p1] < hd[p2] else (idx_p + 1) % len(peaks)
                            peaks.pop(drop_idx)
                            changed = True
                            break
            n_p = len(peaks)
            if n_p == 1:
                p0 = peaks[0]
                c_dist = np.minimum(np.abs(np.arange(n_bins) - p0), n_bins - np.abs(np.arange(n_bins) - p0))
                second_moment = float(np.sum((c_dist ** 2) * hd))
            else:
                # Tìm chân thung lũng (valley) giữa các đỉnh liên tiếp trên vòng tròn 16 bin để phân hoạch miền w_p
                valleys = []
                for idx_p in range(n_p):
                    p_start = peaks[idx_p]
                    p_end = peaks[(idx_p + 1) % n_p]
                    arc_len = (p_end - p_start) % n_bins
                    arc_bins = [(p_start + step) % n_bins for step in range(1, arc_len)]
                    v_bin = min(arc_bins, key=lambda b: hd[b]) if arc_bins else p_start
                    valleys.append(v_bin)
                second_moment = 0.0
                for idx_p in range(n_p):
                    p_bin = peaks[idx_p]
                    v_left = valleys[(idx_p - 1) % n_p]
                    v_right = valleys[idx_p]
                    span = (v_right - v_left) % n_bins
                    w_p = [(v_left + s) % n_bins for s in range(span if span > 0 else n_bins)]
                    for phi in w_p:
                        d_phi = min(abs(phi - p_bin), n_bins - abs(phi - p_bin))
                        second_moment += (d_phi ** 2) * hd[phi]
            r_norm = 1.0 / 32.0
            f_dir = float(np.clip(1.0 - r_norm * n_p * second_moment, 0.0, 1.0))
        else:
            f_dir = 0.0
            
    return np.array([f_crs, f_con, f_dir], dtype=np.float32)

def extract_gabor_features(gray_img, mask, bbox):
    """
    T4: Năng lượng lọc Gabor đa hướng đa tần số (MPEG-7 Homogeneous Texture): 24 chiều
    - 3 bước sóng lambda = [4.0, 8.0, 16.0]
    - 4 hướng theta = [0, 45, 90, 135] độ (0, pi/4, pi/2, 3pi/4)
    - 12 bộ lọc x (Mean, Std năng lượng trên thân cá) = 24 chiều
    """
    xlb, xub, ylb, yub = bbox
    crop_gray = gray_img[ylb:yub+1, xlb:xub+1]
    crop_mask = mask[ylb:yub+1, xlb:xub+1]
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded_mask = cv2.erode(crop_mask, kernel, iterations=2)
    if np.sum(eroded_mask > 0) < 50:
        eroded_mask = crop_mask
        
    fg_mask = eroded_mask > 0
    if not np.any(fg_mask):
        return np.zeros(24, dtype=np.float32)
        
    raw_fg = crop_mask > 0
    gray_f = crop_gray.astype(np.float32) / 255.0
    fg_mean = float(np.mean(gray_f[raw_fg])) if np.any(raw_fg) else 0.0
    gray_f = np.where(raw_fg, gray_f, fg_mean).astype(np.float32)
    lambdas = [4.0, 8.0, 16.0]
    thetas = [0.0, np.pi/4.0, np.pi/2.0, 3.0*np.pi/4.0]
    
    features = []
    for lm in lambdas:
        sigma = 0.56 * lm
        ksize = int(round(3.0 * sigma)) * 2 + 1
        ksize = min(31, max(7, ksize))
        for th in thetas:
            k_real = cv2.getGaborKernel((ksize, ksize), sigma, th, lm, 0.5, 0, ktype=cv2.CV_32F)
            k_imag = cv2.getGaborKernel((ksize, ksize), sigma, th, lm, 0.5, np.pi/2.0, ktype=cv2.CV_32F)
            
            f_real = cv2.filter2D(gray_f, cv2.CV_32F, k_real, borderType=cv2.BORDER_REPLICATE)
            f_imag = cv2.filter2D(gray_f, cv2.CV_32F, k_imag, borderType=cv2.BORDER_REPLICATE)
            energy = np.sqrt(f_real**2 + f_imag**2)
            
            fg_energy = energy[fg_mask]
            m = float(np.mean(fg_energy))
            s = float(np.std(fg_energy))
            features.extend([m, s])
            
    return np.array(features, dtype=np.float32)

def extract_all_texture_features(bgr_img, mask, bbox):
    """
    Trích toàn bộ 146 chiều đặc trưng Kết cấu:
    - T1: Multi-directional Foreground-Only GLCM 60 chiều (5 props x 3 dists [1,3,5] x 4 angles)
    - T2: NRI-Uniform LBP 59 chiều (P=8, R=1)
    - T3: Tamura 3 chiều (Coarseness, Contrast, Directionality)
    - T4: Gabor Filter Energy 24 chiều (3 lambdas x 4 thetas x 2 stats)
    Trả về: (texture_vector, feature_names)
    """
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    
    # T1: 60 chiều
    glcm_vec = extract_glcm_features(gray, mask, bbox)
    glcm_names = [
        f"texture_t1_glcm_{p}_d{d}_a{a}"
        for p in ["contrast", "dissimilarity", "homogeneity", "energy", "correlation"]
        for d in [1, 3, 5]
        for a in [0, 45, 90, 135]
    ]
    
    # T2: 59 chiều
    lbp_vec = extract_lbp_features(gray, mask, bbox)
    lbp_names = [f"texture_t2_lbp_nri_bin_{i}" for i in range(59)]
    
    # T3: 3 chiều
    tamura_vec = extract_tamura_features(gray, mask, bbox)
    tamura_names = ["texture_t3_tamura_coarseness", "texture_t3_tamura_contrast", "texture_t3_tamura_directionality"]
    
    # T4: 24 chiều
    gabor_vec = extract_gabor_features(gray, mask, bbox)
    gabor_names = [
        f"texture_t4_gabor_l{int(lm)}_a{int(np.rad2deg(th))}_{stat}"
        for lm in [4.0, 8.0, 16.0]
        for th in [0.0, np.pi/4.0, np.pi/2.0, 3.0*np.pi/4.0]
        for stat in ["mean", "std"]
    ]
    
    full_texture_vec = np.concatenate([glcm_vec, lbp_vec, tamura_vec, gabor_vec])
    full_texture_names = glcm_names + lbp_names + tamura_names + gabor_names
    
    return full_texture_vec, full_texture_names
