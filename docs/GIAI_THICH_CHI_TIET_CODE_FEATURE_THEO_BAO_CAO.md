# TÀI LIỆU GIẢI THÍCH CHI TIẾT CODE TRÍCH XUẤT ĐẶC TRƯNG (`src/features/`) BÁM SÁT BÁO CÁO LẦN 1 (`docs/CSDL ĐPT.md`)

Tài liệu này giải thích chi tiết từng module, từng hàm và từng khối lệnh trong thư mục [`src/features/`](file:///D:/PTIT/CSDLDPT/src/features), đối chiếu **1-1** với các mục lý thuyết và công thức toán học trong Báo cáo lần 1 ([`docs/CSDL ĐPT.md`](file:///D:/PTIT/CSDLDPT/docs/CSDL%20%C4%90PT.md)) để phục vụ việc đọc hiểu mã nguồn và vấn đáp bảo vệ Bài tập lớn.

---

## 1. TỔNG QUAN KIẾN TRÚC PIPELINE (`src/features/pipeline.py`)

File [`src/features/pipeline.py`](file:///D:/PTIT/CSDLDPT/src/features/pipeline.py) đóng vai trò là **tầng điều phối trung tâm (Orchestrator)**: nhận đầu vào là một ảnh cá chuẩn hóa 4 kênh BGRA (`500×500` px từ `dataset_gold_v3/images_rgba/`), tách mặt nạ vùng thân cá $\Omega_{\text{fg}}$, tìm khung bao tối thiểu (Minimum Bounding Box — MBB), và gọi lần lượt 3 module trích xuất đặc trưng để ghép thành vector tổng hợp **421 chiều** ($\mathbf{f} \in \mathbb{R}^{421}$) kèm chữ ký nhị phân lọc thô **64-bit (`uint64`)**.

### 1.1. Bảng ánh xạ tổng thể giữa Báo cáo và Code

| Mục trong Báo cáo (`docs/CSDL ĐPT.md`) | Mã | Tên thuộc tính | Số chiều | Chỉ số trong vector `421D` | Hàm thực thi chính trong Code |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Mục 2.1.1** | `C1` | Biểu đồ màu HSV phân vùng thích nghi | **78** | `[0 .. 77]` | [`extract_adaptive_hsv_hist`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L19-L71) |
| **Mục 2.1.2** | `C2` | Mô-men màu trên không gian CIE Lab | **9** | `[78 .. 86]` | [`extract_color_moments_lab`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L73-L101) |
| **Mục 2.1.3** | `C3` | Bố cục màu theo lưới giải phẫu $3 \times 2$ | **48** | `[87 .. 134]` | [`extract_spatial_block_color`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L103-L157) |
| **Mục 2.2.1** | `S1` | Tỷ số hình thái học hình học | **8** | `[135 .. 142]` | [`extract_morphometrics`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L22-L85) |
| **Mục 2.2.2** | `S2` | Biên dạng dọc lưng – bụng (16 lát cắt) | **32** | `[143 .. 174]` | [`extract_dorsal_ventral_profile`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L87-L128) |
| **Mục 2.2.3** | `S3` | Mô-men bất biến Hu (nén logarit) | **7** | `[175 .. 181]` | [`extract_hu_moments`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L130-L151) |
| **Mục 2.2.4** | `S4` | Hệ số Fourier elip chuẩn hóa Kuhl–Giardina | **29** | `[182 .. 210]` | [`extract_elliptic_fourier_descriptors_kuhl`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L153-L263) |
| **Mục 2.2.5** | `S5` | Lưới không gian $8 \times 8$ + Chữ ký nhị phân 64-bit | **64** (+ `uint64`) | `[211 .. 274]` | [`extract_binary_grid_8x8`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L265-L290) |
| **Mục 2.3.1** | `T1` | Ma trận đồng xuất mức xám vùng thân cá (GLCM) | **60** | `[275 .. 334]` | [`extract_glcm_features`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L27-L76) |
| **Mục 2.3.2** | `T2` | Mẫu nhị phân cục bộ đồng nhất (NRI-Uniform LBP) | **59** | `[335 .. 393]` | [`extract_lbp_features`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L78-L102) |
| **Mục 2.3.3** | `T3` | Đặc trưng kết cấu thị giác Tamura | **3** | `[394 .. 396]` | [`extract_tamura_features`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L104-L238) |
| **Mục 2.3.4** | `T4` | Năng lượng bộ lọc Gabor đa tỷ lệ và đa hướng | **24** | `[397 .. 420]` | [`extract_gabor_features`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L240-L285) |
| **TỔNG CỘNG** | **12** | **3 Bộ Đặc trưng Thị giác (Color + Shape + Texture)** | **421** | `[0 .. 420]` | [`process_single_image`](file:///D:/PTIT/CSDLDPT/src/features/pipeline.py#L27-L96) |

---

### 1.2. Giải thích chi tiết hàm `process_single_image(img_bgra)` ([`src/features/pipeline.py#L27-L96`](file:///D:/PTIT/CSDLDPT/src/features/pipeline.py#L27-L96))

```python
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
```

- **Ý nghĩa lý thuyết (Bám sát Phần 1.2 & Mở đầu Phần 2 của Báo cáo)**:
  - Trong bài giảng *Hệ CSDL Đa phương tiện* (Lecture 11), nếu tính đặc trưng trên toàn bộ khung ảnh chữ nhật thì vùng nền (chiếm $60\% - 75\%$ diện tích ảnh) sẽ lấn át hoàn toàn thông tin của vật thể (*masking effect*).
  - Do đó, dòng `mask = (alpha > 128).astype(np.uint8)` định nghĩa chính xác tập điểm ảnh tiền cảnh (vùng thân cá):
    $$\Omega_{\text{fg}} = \{(x, y) \mid \alpha(x, y) > 128\}$$
  - Dòng `ys, xs = np.where(mask > 0)` tìm tọa độ cực trị của thân cá để đóng khung bao tối thiểu `bbox = (xlb, xub, ylb, yub)` tương ứng với $[x_{\min}, x_{\max}, y_{\min}, y_{\max}]$. Mọi phép chia lưới không gian (`C3`, `S2`, `S5`) đều chỉ co giãn trên khung bao `bbox` này nên đạt **tính bất biến tịnh tiến và bất biến tỷ lệ kích thước**.

---

## 2. NHÓM 2.1: BỘ THUỘC TÍNH MÀU SẮC (`src/features/color.py` — 135 CHIỀU)

File [`src/features/color.py`](file:///D:/PTIT/CSDLDPT/src/features/color.py) triển khai 3 thành phần màu sắc (`C1: 78D`, `C2: 9D`, `C3: 48D`) tại hàm điều phối [`extract_all_color_features(bgr_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L159-L203):

```python
hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2Lab)

hsv_fg = hsv[mask > 0]
lab_fg = lab[mask > 0]
```
- **Lưu ý quan trọng**: Dòng `hsv_fg = hsv[mask > 0]` và `lab_fg = lab[mask > 0]` trích xuất trực tiếp mảng 1 chiều chỉ gồm $N = |\Omega_{\text{fg}}|$ điểm ảnh thuộc thân cá. Toàn bộ điểm ảnh nền đen (`mask == 0`) bị loại bỏ hoàn toàn ngay từ đầu.

---

### 2.1.1. Thành phần `C1` — Biểu đồ màu HSV phân vùng thích nghi (78 chiều)
- **Hàm trong code**: [`extract_adaptive_hsv_hist(hsv_fg)`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L19-L71)
- **Mục tương ứng trong Báo cáo**: Mục `2.1.1` (công thức `[image8]`).

#### Giải thích từng bước trong code:
1. **Quy đổi thang đo kênh HSV của OpenCV về chuẩn lý thuyết** (dòng 33–35):
   ```python
   h = hsv_fg[:, 0].astype(np.float32) * 2.0   # OpenCV H in [0, 180] -> [0, 360] độ
   s = hsv_fg[:, 1].astype(np.float32) / 255.0 # [0, 1.0]
   v = hsv_fg[:, 2].astype(np.float32) / 255.0 # [0, 1.0]
   ```
   - OpenCV lưu ảnh HSV 8-bit (`uint8`) với $H \in [0, 180]$, $S \in [0, 255]$, $V \in [0, 255]$. Code nhân $H$ với `2.0` để đưa về đúng góc vòng tròn màu $[0^\circ, 360^\circ)$ và chia $S, V$ cho `255.0` để đưa về đoạn $[0, 1]$ khớp với công thức trong báo cáo.

2. **Tách mặt nạ Vô sắc (Achromatic) và Hữu sắc (Chromatic)** (dòng 39–47):
   ```python
   achromatic_mask = s < 0.15
   chromatic_mask = ~achromatic_mask

   # 1. Achromatic (6 bins: index 0 -> 5)
   if np.any(achromatic_mask):
       v_achr = v[achromatic_mask]
       v_bins = np.clip((v_achr * 6.0).astype(int), 0, 5)
       hist[:6] = np.bincount(v_bins, minlength=6).astype(np.float32)
   ```
   - **Tại sao phải tách `s < 0.15`?**: Hơn $47\%$ điểm ảnh vảy cá nước ngọt (`ilish`, `boal`, `katla`, bụng `rui`) có màu trắng bạc hoặc xám chì với độ bão hòa rất thấp ($S < 0.15$). Ở vùng này, công thức tính góc Hue bị suy biến (mẫu số $\max(R,G,B) - \min(R,G,B) \approx 0$), chỉ cần nhiễu sáng 1–2 đơn vị RGB sẽ làm góc Hue nhảy ngẫu nhiên từ $0^\circ$ sang $240^\circ$.
   - Do đó, mọi điểm ảnh có $S < 0.15$ được đưa vào **6 ô vô sắc (`hist[0..5]`)** chia đều theo độ sáng $V \in [0, 1]$.

3. **Lượng tử hóa 72 ô Hữu sắc (`12 Hue × 3 Sat × 2 Val`)** (dòng 49–67):
   ```python
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
   ```
   - Với các điểm ảnh có màu rõ ($S \ge 0.15$):
     - Góc Hue chia đều thành **12 cung màu** ($30^\circ/\text{ô}$, `h_bin` $\in \{0, \dots, 11\}$).
     - Độ bão hòa $S$ chia thành **3 mức** (`[0.15, 0.35)`, `[0.35, 0.60)`, `[0.60, 1.0]`, `s_bin` $\in \{0, 1, 2\}$).
     - Độ sáng $V$ chia thành **2 mức** (`[0, 0.50)` và `[0.50, 1.0]`, `v_bin` $\in \{0, 1\}$).
   - Công thức ánh xạ tuyến tính `chr_sub_idx = h_bin * 6 + s_bin * 2 + v_bin` xếp $12 \times 3 \times 2 = 72$ tổ hợp vào các vị trí `hist[6..77]` và đếm siêu tốc bằng `np.bincount`.

4. **Chuẩn hóa $L_1$ theo diện tích thân cá** (dòng 70):
   ```python
   hist = hist / float(total_pixels)
   ```
   - Khớp chính xác công thức trong báo cáo:
     $$h_k^{\text{C1}} = \frac{1}{|\Omega_{\text{fg}}|} \sum_{(x,y) \in \Omega_{\text{fg}}} \mathbb{I}\big((x,y) \in \text{Bin}_k\big), \quad \sum_{k=1}^{78} h_k^{\text{C1}} = 1$$

---

### 2.1.2. Thành phần `C2` — Các mô-men màu trên không gian CIE Lab (9 chiều)
- **Hàm trong code**: [`extract_color_moments_lab(lab_fg)`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L73-L101)
- **Mục tương ứng trong Báo cáo**: Mục `2.1.2` (công thức `[image9]`).

#### Giải thích từng bước trong code:
```python
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
    m_skew = np.clip(m_skew / 5.0, -1.0, 1.0)
    moments.extend([m_mean, m_std, m_skew])
```
- **Tại sao tính mô-men trên CIE Lab mà không tính trên HSV?**:
  - Kênh Hue là đại lượng góc tuần hoàn ($0^\circ \equiv 360^\circ$ cùng là màu đỏ). Nếu lấy trung bình cộng số học $\frac{1}{2}(1^\circ + 359^\circ) = 180^\circ$ sẽ ra màu xanh lơ (sai hoàn toàn về mặt toán học).
  - Không gian **CIE $L^*a^*b^*$** là không gian màu đều về mặt tri giác (*perceptually uniform*) với 3 trục trực giao tuyến tính: $L^*$ (Độ sáng), $a^*$ (Lục $\leftrightarrow$ Đỏ), $b^*$ (Lam $\leftrightarrow$ Vàng).
- **3 đại lượng thống kê trên mỗi kênh $c \in \{L^*, a^*, b^*\}$**:
  1. Kỳ vọng (Mô-men bậc 1): $\mu_c = \frac{1}{N}\sum_{i=1}^N P_c(x_i, y_i)$ (`np.mean(channel)`).
  2. Độ lệch chuẩn (Căn bậc hai mô-men trung tâm bậc 2): $\sigma_c = \sqrt{\frac{1}{N}\sum_{i=1}^N (P_c(x_i, y_i) - \mu_c)^2}$ (`np.std(channel)`).
  3. Độ bất đối xứng chuẩn hóa (Skewness bậc 3):
     $$s_c = \frac{\frac{1}{N}\sum_{i=1}^N (P_c(x_i, y_i) - \mu_c)^3}{\sigma_c^3}$$
     được tính bằng `scipy.stats.skew(channel)`, sau đó chia cho `5.0` và giới hạn trong `[-1.0, 1.0]` để tránh các đuôi phân phối ngoại lai làm lệch khoảng cách Z-score.
- Ghép 3 kênh $\times$ 3 mô-men thu được **9 chiều**.

---

### 2.1.3. Thành phần `C3` — Bố cục màu theo lưới không gian giải phẫu $3 \times 2$ (48 chiều)
- **Hàm trong code**: [`extract_spatial_block_color(bgr_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/color.py#L103-L157)
- **Mục tương ứng trong Báo cáo**: Mục `2.1.3` (công thức `[image10]`).

#### Giải thích từng bước trong code:
```python
xlb, xub, ylb, yub = bbox
w = max(1, xub - xlb + 1)
h = max(1, yub - ylb + 1)

# Ranh giới cột (Đầu 25%, Thân giữa 50%, Đuôi 25%) và hàng (Lưng 50%, Bụng 50%)
x_splits = [xlb, int(xlb + 0.25 * w), int(xlb + 0.75 * w), xub + 1]
y_splits = [ylb, int(ylb + 0.50 * h), yub + 1]
```
- **Ý nghĩa giải phẫu học**:
  - Biểu đồ màu toàn cục `C1` chỉ biết tổng lượng màu trên cả con cá nhưng không biết màu đó nằm ở lưng hay ở bụng.
  - Ở cá thật, quy luật **ngụy trang ngược sáng (Countershading)** làm cho vùng lưng (`dorsal`, nửa trên) luôn sẫm màu hơn vùng bụng (`ventral`, nửa dưới trắng bạc); ngoài ra nắp mang ở vùng đầu (`head`) của `rui` hoặc gốc đuôi (`tail`) của `koi` có sắc tố đặc trưng riêng.
  - Code chia khung bao `bbox` thành **3 cột dọc** (Đầu $25\%$, Thân giữa $50\%$, Đuôi $25\%$) $\times$ **2 hàng ngang** (Lưng $50\%$, Bụng $50\%$) $= \mathbf{6\text{ vùng giải phẫu}}$: `head_dorsal`, `head_ventral`, `mid_dorsal`, `mid_ventral`, `tail_dorsal`, `tail_ventral`.
- **Trích xuất 8 bin màu cho từng vùng** (dòng 138–155):
  - Bin `0`: Tỷ lệ điểm ảnh vô sắc tối ($S < 0.15$ và $V < 0.5$).
  - Bin `1`: Tỷ lệ điểm ảnh vô sắc sáng ($S < 0.15$ và $V \ge 0.5$).
  - Bin `2..7`: Tỷ lệ điểm ảnh hữu sắc ($S \ge 0.15$) rơi vào 6 cung màu Hue (mỗi cung rộng $60^\circ$: $[0^\circ, 60^\circ), \dots, [300^\circ, 360^\circ)$).
  - Chuẩn hóa tổng mỗi vùng bằng `1.0` (`hist8 / float(len(block_fg))`). Tổng cộng $6 \text{ vùng} \times 8 \text{ bin} = \mathbf{48\text{ chiều}}$.

---

## 3. NHÓM 2.2: BỘ THUỘC TÍNH HÌNH DẠNG (`src/features/shape.py` — 140 CHIỀU + `uint64`)

File [`src/features/shape.py`](file:///D:/PTIT/CSDLDPT/src/features/shape.py) chỉ làm việc trên mặt nạ nhị phân `mask_bin = (mask > 0).astype(np.uint8)` và đường bao ngoài lớn nhất `c_max = max(contours, key=cv2.contourArea)`.

---

### 3.1. Thành phần `S1` — Các tỷ số hình thái học hình học (8 chiều)
- **Hàm trong code**: [`extract_morphometrics(mask, bbox, contour)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L22-L85)
- **Mục tương ứng trong Báo cáo**: Mục `2.2.1` (công thức `[image11]` và `[image12]`).

#### Đối chiếu 1-1 cả 8 chỉ số giữa Báo cáo và Code:
Với diện tích thân cá $A = |\Omega_{\text{fg}}|$ (`area`), chu vi đường bao $P$ (`perimeter`), diện tích bao lồi $A_{\text{hull}}$ (`hull_area`), chu vi bao lồi $P_{\text{hull}}$ (`hull_perimeter`), chiều dài hộp bao $W$ (`w`) và chiều cao hộp bao $H$ (`h`):

1. **Tỷ lệ khung bao (`aspect_ratio`)** — dòng 36:
   $$\text{AR} = \frac{W}{H}$$
   Phân biệt rõ nhóm cá thân dài như cá leo `Boal` ($\text{AR} \approx 2.81$) với nhóm cá thân bè cao như cá rô phi `Telapia` ($\text{AR} \approx 1.81$).
2. **Độ tròn (`circularity`)** — dòng 45:
   $$\text{Circularity} = \frac{4\pi A}{P^2}$$
3. **Độ đặc (`solidity`)** — dòng 48:
   $$\text{Solidity} = \frac{A}{A_{\text{hull}}}$$
   Đo mức độ khuyết lõm của các vây và khe đuôi chữ V so với đa giác bao lồi.
4. **Độ lấp đầy hộp bao (`extent`)** — dòng 51:
   $$\text{Extent} = \frac{A}{W \cdot H}$$
5. **Độ lệch tâm elip (`eccentricity`)** — dòng 58–71:
   Khớp elip tương đương bằng `cv2.fitEllipse(contour)` để lấy trục lớn $a$ (`major_axis`) và trục nhỏ $b$ (`minor_axis`):
   $$\text{Eccentricity} = \sqrt{1 - \left(\frac{b}{a}\right)^2}$$
6. **Độ lồi chu vi (`convexity`)** — dòng 54:
   $$\text{Convexity} = \frac{P_{\text{hull}}}{P}$$
7. **Độ chữ nhật (`rectangularity`)** — dòng 74–76:
   Tìm hình chữ nhật xoay có diện tích nhỏ nhất bao quanh cá bằng `cv2.minAreaRect(contour)`:
   $$\text{Rectangularity} = \frac{A}{A_{\text{minAreaRect}}}$$
8. **Tỷ số đường kính tương đương (`eq_diameter_ratio`)** — dòng 79–80:
   $$\text{EquivDiamRatio} = \frac{\sqrt{4A / \pi}}{\sqrt{W^2 + H^2}}$$

> **Điểm nhấn thiết kế**: Cả 8 đại lượng đều là **tỷ số không thứ nguyên (dimensionless ratios)** giữa các đại lượng cùng bậc độ dài hoặc diện tích, nên hoàn toàn **bất biến với phép phóng to/thu nhỏ ảnh**.

---

### 3.2. Thành phần `S2` — Biên dạng dọc lưng – bụng (Dorsal–Ventral Profile — 32 chiều)
- **Hàm trong code**: [`extract_dorsal_ventral_profile(mask, bbox, num_points=16)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L87-L128)
- **Mục tương ứng trong Báo cáo**: Mục `2.2.2` (công thức `[image13]`).

#### Giải thích từng bước trong code:
```python
ys, xs = np.where(mask > 0)
cy = float(np.mean(ys))

for i in range(num_points):
    x1 = int(round(xlb + i * w / float(num_points)))
    x2 = int(round(xlb + (i + 1) * w / float(num_points)))
    ...
    slice_mask = mask[:, x1:x2]
    slice_ys, _ = np.where(slice_mask > 0)
    if len(slice_ys) > 0:
        y_top = float(np.min(slice_ys))
        y_bot = float(np.max(slice_ys))
        d_d = max(0.0, cy - y_top) / w
        d_v = max(0.0, y_bot - cy) / w
```
- **Ý nghĩa toán học & sinh học**:
  - Do ảnh cá đã chuẩn hóa nằm ngang (đầu bên trái tại `xlb`, đuôi bên phải tại `xub`), code chia chiều dài thân cá $W$ thành `num_points = 16` lát cắt dọc cách đều nhau từ đầu tới đuôi.
  - Tại lát cắt thứ $k$ ($k = 1, \dots, 16$), xác định điểm mép lưng cao nhất $y_{\text{top}}(x_k)$ và điểm mép bụng thấp nhất $y_{\text{bottom}}(x_k)$ so với trục ngang trọng tâm $c_y$:
    $$d_k^{\text{dorsal}} = \frac{\max(0, c_y - y_{\text{top}}(x_k))}{W}, \quad d_k^{\text{ventral}} = \frac{\max(0, y_{\text{bottom}}(x_k) - c_y)}{W}$$
  - Đặc trưng này nắm bắt cực kỳ sắc nét **độ gù vồng cao của lưng cá `Katla`**, **bụng bầu tròn của cá cháy `Ilish`**, và **độ thắt cổ đuôi** ở các lát cắt số 13–15.

---

### 3.3. Thành phần `S3` — Các mô-men bất biến Hu (7 chiều)
- **Hàm trong code**: [`extract_hu_moments(mask)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L130-L151)
- **Mục tương ứng trong Báo cáo**: Mục `2.2.3` (công thức `[image14]`).

#### Giải thích từng bước trong code:
```python
moments = cv2.moments((mask > 0).astype(np.uint8))
hu = cv2.HuMoments(moments).flatten()

log_hu = np.zeros(7, dtype=np.float32)
for i in range(7):
    val = hu[i]
    sign = np.sign(val)
    abs_v = np.abs(val)
    log_hu[i] = -sign * np.log10(abs_v + 1e-30) if abs_v > 0 else 0.0

log_hu = np.clip(log_hu / 20.0, -1.0, 1.0)
```
- **Tại sao phải lấy $-\text{sign}(\phi_k)\log_{10}(|\phi_k| + 10^{-30})$?**:
  - 7 đa thức bất biến Hu $\phi_1 \dots \phi_7$ được xây dựng từ các mô-men trung tâm chuẩn hóa bậc 2 và bậc 3 ($\eta_{20}, \eta_{02}, \eta_{11}, \eta_{30}, \dots$). Vì lũy thừa bậc cao nên giá trị thô của $\phi_1 \approx 10^{-1}$ trong khi $\phi_7 \approx 10^{-25}$ (chênh nhau hơn 20 bậc độ lớn).
  - Phép biến đổi logarit giữ dấu nén toàn bộ 7 mô-men về cùng một mặt bằng độ lớn, sau đó chia `/ 20.0` đưa về đoạn $[-1, 1]$ để ổn định số học.

---

### 3.4. Thành phần `S4` — Bộ mô tả Fourier elip chuẩn hóa Kuhl–Giardina (29 chiều)
- **Hàm trong code**: [`extract_elliptic_fourier_descriptors_kuhl(contour, order=8)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L153-L263)
- **Mục tương ứng trong Báo cáo**: Mục `2.2.4` (công thức `[image15]`).

#### Giải thích 4 bước toán học Kuhl & Giardina (1982) trong code:
1. **Bước 1 — Tham số hóa độ dài cung và tính tích phân chuỗi Fourier rời rạc (dòng 176–205)**:
   - Đường bao khép kín gồm các đoạn thẳng nối tiếp $(\Delta x_i, \Delta y_i)$ có độ dài $\Delta t_i = \sqrt{\Delta x_i^2 + \Delta y_i^2}$ và tổng chu vi $T = \sum \Delta t_i$.
   - Với mỗi bậc hài $n = 1, \dots, 8$, tính 4 hệ số Fourier $(a_n, b_n, c_n, d_n)$ theo công thức giải tích chính xác của Kuhl–Giardina:
     $$a_n = \frac{T}{2n^2\pi^2} \sum_{i=1}^K \frac{\Delta x_i}{\Delta t_i} \left[\cos\frac{2n\pi t_i}{T} - \cos\frac{2n\pi t_{i-1}}{T}\right]$$
     (tương tự cho $b_n, c_n, d_n$).

2. **Bước 2 — Chuẩn hóa điểm bắt đầu $\theta_1$ và khóa hướng đầu cá bên trái (dòng 207–234)**:
   - Khi `cv2.findContours` quét biên ảnh, điểm bắt đầu $(x_0, y_0)$ trên đường bao có thể thay đổi. Code tìm góc pha $\theta_1$ của elip cơ sở bậc 1:
     $$\theta_1 = \frac{1}{2} \arctan2\big(2(a_1 b_1 + c_1 d_1),\; a_1^2 + c_1^2 - b_1^2 - d_1^2\big)$$
   - **Kỹ thuật xử lý bất định $\pi$ (dòng 232–234)**: Một hình elip có 2 đỉnh bán trục lớn đối xứng nhau ($\theta_1$ và $\theta_1 + \pi$). Vì bộ dữ liệu đã chuẩn hóa đầu cá quay sang trái (chiều âm trục hoành), code kiểm tra `if an_star[0] > 0: theta1 = theta1 + np.pi` để **ép điểm xuất phát của đường bao luôn cố định tại mỏm đầu cá bên trái**.

3. **Bước 3 — Chuẩn hóa góc xoay trục chính $\psi_1$ (dòng 236–244)**:
   - Tính góc nghiêng của bán trục lớn $\psi_1 = \arctan2(c_1^*, a_1^*)$ và nhân ma trận quay $-\psi_1$ cho toàn bộ 8 bậc hài. Sau bước này, $b_{1,\text{rot}} = 0$ và $c_{1,\text{rot}} = 0$.

4. **Bước 4 — Chuẩn hóa tỷ lệ kích thước theo bán trục lớn $E = a_{1,\text{rot}}$ và rút gọn chiều (dòng 246–263)**:
   - Chia toàn bộ hệ số cho độ dài bán trục lớn $E = a_{1,\text{rot}}$.
   - Sau khi chia, 3 hệ số đầu của bậc 1 luôn trở thành hằng số bất biến đối với mọi ảnh:
     $$(a_1^{\text{norm}}, b_1^{\text{norm}}, c_1^{\text{norm}}, d_1^{\text{norm}}) = (1,\; 0,\; 0,\; d_1^{\text{norm}})$$
   - Do 3 hằng số $(1, 0, 0)$ không mang thông tin phân biệt, code loại bỏ chúng, chỉ giữ lại $d_1^{\text{norm}}$ (tỷ lệ trục nhỏ/trục lớn của elip bậc 1) cùng $7 \times 4 = 28$ hệ số của các bậc hài $n = 2, \dots, 8$, thu được đúng **$1 + 28 = 29\text{ chiều}$**.

---

### 3.5. Thành phần `S5` — Bộ mô tả lưới không gian $8 \times 8$ và chữ ký nhị phân 64-bit (64 chiều + `uint64`)
- **Hàm trong code**: [`extract_binary_grid_8x8(mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L265-L290) và [`extract_binary_grids_multi_res(mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/shape.py#L293-L359)
- **Mục tương ứng trong Báo cáo**: Mục `2.2.5` (công thức `[image16]` và lý thuyết chỉ số hóa hình ảnh Lecture 11 Slide 30).

#### Giải thích từng bước trong code:
```python
crop = mask[ylb:yub+1, xlb:xub+1]
crop_f = (crop > 0).astype(np.float64)
grid = cv2.resize(crop_f, (8, 8), interpolation=cv2.INTER_AREA)
grid_continuous = np.clip(grid.flatten(), 0.0, 1.0)
grid_continuous = np.where(grid_continuous > 1.0 - 1e-5, 1.0, grid_continuous).astype(np.float32)

bits64 = (grid_continuous >= 0.15).astype(np.uint8)
bytes64 = np.packbits(bits64)
grid_uint64 = np.uint64(bytes64.view(">u8")[0])
```
- **Tính tỷ lệ che phủ liên tục $\rho_{r,c} \in [0, 1]$ (64 chiều)**:
  - Thay vì dùng 2 vòng lặp `for` chậm chạp để cắt 64 ô con, việc gọi `cv2.resize(crop_f, (8, 8), interpolation=cv2.INTER_AREA)` trên mặt nạ `{0.0, 1.0}` tính trung bình diện tích tích phân chính xác trên từng ô $(r, c)$:
    $$\rho_{r,c} = \frac{|\Omega_{\text{fg}} \cap \text{Cell}(r, c)|}{|\text{Cell}(r, c)|} \in [0, 1]$$
  - Dòng `np.where(grid_continuous > 1.0 - 1e-5, 1.0, ...)` khử sai số làm tròn dấu phẩy động (`0.99999994 -> 1.0`) ở các ô giữa thân cá luôn đạt độ che phủ $100\%$.
- **Lượng tử hóa chữ ký nhị phân 64-bit với ngưỡng 15% (`>= 0.15`)**:
  - Theo đúng bài giảng của TS. Nguyễn Đình Hóa (Lecture 11 Slide 30: *"Ô có phần diện tích ảnh $\ge 15\%$ diện tích ô nhận giá trị 1, ngược lại nhận giá trị 0"*):
    $$b_{r,c} = \mathbb{I}(\rho_{r,c} \ge 0.15) \in \{0, 1\}$$
  - Hàm `np.packbits(bits64).view(">u8")[0]` nén 64 bit nhị phân theo chuẩn Big-Endian (MSB-first) vào một số nguyên không dấu 64-bit duy nhất (`uint64`). Nhờ vậy, khi truy vấn có thể lọc thô 1.100 ảnh bằng phép toán phần cứng `XOR` + `popcount` (khoảng cách Hamming) chỉ mất chưa tới $0.1\text{ ms}$.

---

## 4. NHÓM 2.3: BỘ THUỘC TÍNH KẾT CẤU BỀ MẶT (`src/features/texture.py` — 146 CHIỀU)

File [`src/features/texture.py`](file:///D:/PTIT/CSDLDPT/src/features/texture.py) đo lường cấu trúc vi mô của bề mặt da và vảy cá (da trơn nhẵn của `Boal`, mắt lưới vảy to thô của `Katla`/`Rui`, sọc vảy đều của `Telapia`).

---

### 4.1. Thành phần `T1` — Ma trận đồng xuất mức xám vùng thân cá (Foreground GLCM — 60 chiều)
- **Hàm trong code**: [`extract_glcm_features(gray_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L27-L76)
- **Mục tương ứng trong Báo cáo**: Mục `2.3.1` (công thức `[image17]` và `[image18]`).

#### Giải thích kỹ thuật "Foreground-Only GLCM" trong code:
```python
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
eroded_mask = cv2.erode(crop_mask, kernel, iterations=2)

# Lượng tử hóa mức xám thân cá về 1..16, pixel ngoài mặt nạ gán bằng 0
quantized = (np.clip(crop_gray.astype(np.int32) // 16, 0, 15).astype(np.uint8) + 1)
quantized[eroded_mask == 0] = 0

distances = [1, 3, 5]
angles = [0.0, np.pi/4.0, np.pi/2.0, 3.0*np.pi/4.0]

glcm_full = graycomatrix(quantized, distances=distances, angles=angles, levels=17, symmetric=True, normed=False)
# Chỉ giữ ma trận con 16x16 của các cặp pixel cùng thuộc thân cá (mức 1..16)
glcm_fg = glcm_full[1:, 1:, :, :].astype(np.float64)
sums = glcm_fg.sum(axis=(0, 1), keepdims=True)
glcm_fg = np.divide(glcm_fg, sums, out=np.zeros_like(glcm_fg), where=sums > 0)
```
- **Tại sao không gọi thẳng `graycomatrix` trên ảnh gốc?**:
  - Nếu gọi `graycomatrix` trên ảnh chữ nhật có nền đen (`gray = 0`), ô $(0, 0)$ của ma trận GLCM sẽ đếm hàng trăm nghìn cặp điểm ảnh nền đen đứng cạnh nhau, còn hàng $0$ / cột $0$ sẽ đếm bước nhảy giả tại rìa thân cá tiếp giáp nền đen.
  - **Giải pháp thông minh trong code**:
    1. Co nhẹ mặt nạ vào trong 2 pixel (`cv2.erode(..., iterations=2)`) để loại bỏ rìa biên tiếp giáp nền.
    2. Dịch 16 mức xám của thân cá lên dải **`1..16`**, và dành riêng mức **`0`** cho toàn bộ vùng nền bên ngoài mặt nạ (`quantized[eroded_mask == 0] = 0`).
    3. Tính ma trận GLCM kích thước `17 × 17` (`levels=17`), sau đó **cắt bỏ hàng 0 và cột 0 (`glcm_full[1:, 1:, :, :]`)** rồi mới chuẩn hóa tổng xác suất $\sum_{i,j=1}^{16} P(i,j) = 1$.
    4. Nhờ đó, **100% các cặp điểm ảnh được thống kê đều có cả điểm đầu và điểm cuối nằm trọn bên trong vùng thân cá**.
- **Tại sao chọn khoảng cách $d \in \{1, 3, 5\}$?**:
  - Trong `skimage.feature.graycomatrix`, bước nhảy chéo ở góc $45^\circ$ và $135^\circ$ được tính bằng $\text{round}(d \cdot \cos 45^\circ) = \text{round}(0.7071 d)$. Nếu chọn $d = 1, 2$ thì $\text{round}(0.7071 \times 1) = 1$ và $\text{round}(0.7071 \times 2) = 1$ bị trùng nhau hoàn toàn! Chọn $d \in \{1, 3, 5\}$ cho ra bước nhảy chéo phân biệt hoàn toàn $[1, 2, 4]$.
- **5 đại lượng Haralick trên mỗi ma trận** ($3\text{ khoảng cách} \times 4\text{ góc} \times 5\text{ đại lượng} = \mathbf{60\text{ chiều}}$):
  1. `contrast`: $\sum_{i,j} (i - j)^2 P(i,j)$ (Độ tương phản rãnh vảy).
  2. `dissimilarity`: $\sum_{i,j} |i - j| P(i,j)$ (Độ dị biệt tuyến tính).
  3. `homogeneity`: $\sum_{i,j} \frac{P(i,j)}{1 + (i - j)^2}$ (Độ đồng nhất da trơn).
  4. `energy`: $\sqrt{\sum_{i,j} P(i,j)^2}$ (Năng lượng / độ tuần hoàn đều của lưới vảy).
  5. `correlation`: $\sum_{i,j} \frac{(i - \mu_i)(j - \mu_j)P(i,j)}{\sigma_i \sigma_j}$ (Tương quan tuyến tính hướng vảy).

---

### 4.2. Thành phần `T2` — Mẫu nhị phân cục bộ đồng nhất (NRI-Uniform LBP — 59 chiều)
- **Hàm trong code**: [`extract_lbp_features(gray_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L78-L102)
- **Mục tương ứng trong Báo cáo**: Mục `2.3.2` (công thức `[image19]`).

#### Giải thích từng bước trong code:
```python
eroded_mask = cv2.erode(crop_mask, kernel, iterations=1)
lbp_nri = local_binary_pattern(crop_gray, P=8, R=1, method='nri_uniform')
fg_lbp = lbp_nri[eroded_mask > 0]
hist, _ = np.histogram(fg_lbp, bins=59, range=(0, 59))
hist = hist.astype(np.float32) / float(len(fg_lbp))
```
- **Ý nghĩa toán học**:
  - Xét $P = 8$ điểm lân cận trên vòng tròn bán kính $R = 1$ quanh tâm $(x_c, y_c)$, so sánh mức xám $g_p \ge g_c$ để tạo chuỗi nhị phân 8-bit:
    $$\text{LBP}_{8,1}(x_c, y_c) = \sum_{p=0}^{7} s(g_p - g_c) 2^p$$
  - Một mẫu 8-bit được gọi là **đồng nhất (Uniform)** nếu số lần chuyển bit $0 \leftrightarrow 1$ trên vòng tròn khép kín thỏa mãn $U(\text{LBP}_{8,1}) \le 2$ (biểu diễn các cấu trúc vi mô cơ bản: điểm sáng, điểm tối, cạnh thẳng, góc vảy).
  - Trong $2^8 = 256$ mẫu khả dĩ, có đúng **58 mẫu đồng nhất có hướng** (`nri_uniform`, đánh số `0..57`) và toàn bộ 198 mẫu nhiễu ($U > 2$) được gom chung vào **thùng thứ 59** (chỉ số `58`), tạo thành biểu đồ tần suất chuẩn hóa $L_1$ gồm **59 chiều**.
  - Mặt nạ được co 1 pixel (`iterations=1`) để đảm bảo cả 8 điểm lân cận ở bán kính $R=1$ đều nằm trong thân cá.

---

### 4.3. Thành phần `T3` — Các đặc trưng kết cấu thị giác Tamura (3 chiều)
- **Hàm trong code**: [`extract_tamura_features(gray_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L104-L238)
- **Mục tương ứng trong Báo cáo**: Mục `2.3.3` (công thức `[image20]` và lý thuyết Tamura trong Lecture 11).

#### Giải thích 3 đại lượng Tamura trong code:

1. **Độ tương phản Tamura ($F_{\text{con}}$ — dòng 125–134)**:
   ```python
   fg_mean = float(np.mean(fg_pixels))
   sigma = np.std(fg_pixels)
   mu4 = np.mean((fg_pixels - fg_mean) ** 4)
   alpha4 = max(1.0, mu4 / (sigma ** 4))
   f_con = float(sigma / (alpha4 ** 0.25)) / 128.0
   ```
   - Khớp chính xác công thức Tamura:
     $$F_{\text{con}} = \frac{\sigma_I}{\alpha_4^{1/4}}, \quad \text{với } \alpha_4 = \frac{\mu_4}{\sigma_I^4} \text{ (Kurtosis)}$$
     sau đó chia cho `128.0` để quy chuẩn về dải $[0, 1]$.

2. **Độ thô bề mặt Tamura ($F_{\text{crs}}$ — dòng 136–154)**:
   ```python
   # Điền vùng nền ngoài mặt nạ bằng mức xám trung bình của thân cá để khử nhiễu biên đen 0
   gray_f64 = np.where(fg_mask, crop_gray.astype(np.float64), fg_mean)

   scales = [1, 2, 3, 4]
   diff_maps = []
   for k in scales:
       s = 1 << k            # Kích thước cửa sổ 2^k: 2, 4, 8, 16
       shift = 1 << (k - 1)  # Bán kính dịch chuyển không chồng lấp 2^(k-1): 1, 2, 4, 8
       box_avg = cv2.boxFilter(gray_f64, -1, (s, s), normalize=True, borderType=cv2.BORDER_REPLICATE)
       pad_h = np.pad(box_avg, ((0, 0), (shift, shift)), mode="edge")
       d_h = np.abs(pad_h[:, 2 * shift:] - pad_h[:, :-2 * shift])
       pad_v = np.pad(box_avg, ((shift, shift), (0, 0)), mode="edge")
       d_v = np.abs(pad_v[2 * shift:, :] - pad_v[:-2 * shift, :])
       diff_maps.append(np.maximum(d_h, d_v))

   diff_stack = np.stack(diff_maps, axis=0)
   best_scale_idx = np.argmax(diff_stack, axis=0)
   s_opt_map = 2.0 ** (best_scale_idx + 1)
   f_crs = float(np.mean(s_opt_map[eroded_fg])) / 16.0
   ```
   - Với mỗi điểm ảnh $(x,y)$ thuộc thân cá, thuật toán tính trung bình mức xám trong cửa sổ kích thước $2^k \times 2^k$ ($k \in \{1, 2, 3, 4\} \Rightarrow 2, 4, 8, 16\text{ px}$), sau đó tính độ chênh lệch lớn nhất giữa hai cửa sổ đối diện theo phương ngang $E_{k,h}$ và phương dọc $E_{k,v}$.
   - Thang đo tối ưu $k_{\text{opt}}(x,y) = \arg\max_k \max(E_{k,h}, E_{k,v})$ xác định kích thước hạt kết cấu $S_{\text{opt}}(x,y) = 2^{k_{\text{opt}}(x,y)}$. Trung bình cộng $S_{\text{opt}}$ trên vùng thân cá cho ra độ thô $F_{\text{crs}}$ (cá vảy to như `Katla`, `Rui` có $F_{\text{crs}}$ lớn hơn cá da trơn `Boal`).

3. **Độ định hướng Tamura ($F_{\text{dir}}$ — dòng 156–237)**:
   ```python
   gx = cv2.Sobel(gray_f32, cv2.CV_32F, 1, 0, ksize=3)
   gy = cv2.Sobel(gray_f32, cv2.CV_32F, 0, 1, ksize=3)
   mag = np.sqrt(gx**2 + gy**2)
   theta = np.mod(np.arctan2(gy, gx) + np.pi / 2.0, np.pi)
   ```
   - Tính đạo hàm Sobel $(g_x, g_y)$, biên độ $|\Delta G| = \sqrt{g_x^2 + g_y^2}$ và góc hướng cạnh $\theta = (\text{atan2}(g_y, g_x) + \pi/2) \bmod \pi \in [0, \pi)$.
   - Chỉ giữ các điểm biên có cường độ vượt ngưỡng trung bình (`mag_fg > thresh`) và lập biểu đồ tần suất chuẩn hóa 16 bin $H_D(\phi)$.
   - Tìm các đỉnh chủ đạo $\phi_p$ ($p = 1, \dots, n_p$), xác định miền thung lũng $w_p$ bao quanh từng đỉnh trên vòng tròn 16 bin và tính chính xác công thức mô-men bậc hai của Tamura trong báo cáo (`[image20]`):
     $$F_{\text{dir}} = 1 - r \cdot n_p \sum_{p=1}^{n_p} \sum_{\phi \in w_p} (\phi - \phi_p)^2 H_D(\phi)$$

---

### 4.4. Thành phần `T4` — Năng lượng bộ lọc Gabor đa tỷ lệ và đa hướng (24 chiều)
- **Hàm trong code**: [`extract_gabor_features(gray_img, mask, bbox)`](file:///D:/PTIT/CSDLDPT/src/features/texture.py#L240-L285)
- **Mục tương ứng trong Báo cáo**: Mục `2.3.4` (công thức `[image21]`).

#### Giải thích từng bước trong code:
```python
gray_f = crop_gray.astype(np.float32) / 255.0
fg_mean = float(np.mean(gray_f[raw_fg])) if np.any(raw_fg) else 0.0
gray_f = np.where(raw_fg, gray_f, fg_mean).astype(np.float32)
lambdas = [4.0, 8.0, 16.0]
thetas = [0.0, np.pi/4.0, np.pi/2.0, 3.0*np.pi/4.0]

features = []
for lm in lambdas:
    sigma = 0.56 * lm
    ksize = min(31, max(7, int(round(3.0 * sigma)) * 2 + 1))
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
```
- **Cơ chế cặp bộ lọc Gabor cầu phương (Quadrature Pair)**:
  - Với mỗi tổ hợp bước sóng $\lambda \in \{4, 8, 16\}$ (tương ứng tần số không gian từ vảy mịn đến vảy thô) và góc hướng $\theta \in \{0^\circ, 45^\circ, 90^\circ, 135^\circ\}$, code tạo 2 nhân tích chập Gabor lệch pha nhau $\frac{\pi}{2}$:
    - Phần thực `k_real` ($\psi = 0$): hàm $\cos$ điều chế bởi bao hình Gauss.
    - Phần ảo `k_imag` ($\psi = \pi/2$): hàm $\sin$ điều chế bởi bao hình Gauss.
  - Biên độ năng lượng cục bộ $E_{\lambda, \theta}(x, y) = \sqrt{(I * g_{\lambda,\theta}^{\text{real}})^2 + (I * g_{\lambda,\theta}^{\text{imag}})^2}$ không phụ thuộc vào pha vị trí của mép vảy cá.
  - Trên mỗi bản đồ năng lượng thuộc vùng thân cá $\Omega_{\text{fg}}$, trích xuất kỳ vọng $\mu_{\lambda,\theta}$ và độ lệch chuẩn $\sigma_{\lambda,\theta}$:
    $$3\text{ bước sóng } \lambda \times 4\text{ góc } \theta \times 2\text{ thống kê } (\mu, \sigma) = \mathbf{24\text{ chiều}}$$

---

## 5. TỔNG KẾT CÁC KỸ THUẬT CHỐNG NHIỄU QUAN TRỌNG TRONG CODE (DÙNG KHI VẤN ĐÁP)

Nếu giảng viên hỏi *"Khi lập trình trích xuất đặc trưng trên ảnh cá thực tế, nhóm đã xử lý những bẫy kỹ thuật nào?"*, có 5 điểm cốt lõi trong code rất đáng nhấn mạnh:

1. **Loại bỏ tuyệt đối hiệu ứng lấn át nền (Foreground-Only Extraction)**:
   - Không chỉ dùng `mask > 0` cho màu sắc, mà ở phần kết cấu (`T1 GLCM`, `T2 LBP`, `T3 Tamura`, `T4 Gabor`), code còn **co mặt nạ vào trong 1–2 pixel (`cv2.erode`)** và **điền nền bằng mức xám trung bình thân cá (`fg_mean`)** trước khi trượt cửa sổ lọc. Nhờ đó bước nhảy độ sáng từ thân cá ra nền đen (`pixel = 0`) không tạo ra biên giả hay năng lượng tần số cao giả.
2. **Xử lý điểm kỳ dị của góc màu Hue ở vùng vảy bạc (`C1` & `C3`)**:
   - Tách riêng mọi điểm ảnh có độ bão hòa thấp $S < 0.15$ vào các ô vô sắc (Achromatic bins) theo kênh $V$, tránh hoàn toàn nhiễu nhảy góc Hue trên thân cá trắng bạc.
3. **Tính mô-men màu trên không gian tuyến tính CIE Lab thay vì HSV (`C2`)**:
   - Tránh sai lầm cộng trung bình số học trên đại lượng góc tuần hoàn Hue ($0^\circ \equiv 360^\circ$).
4. **Khóa hướng đầu cá bên trái khi chuẩn hóa pha Fourier elip (`S4`)**:
   - Giải quyết bài toán bất định $\pi$ của bán trục lớn elip (`if an_star[0] > 0: theta1 += np.pi`), giúp các hệ số hài bậc chẵn không bị đảo dấu ngẫu nhiên.
5. **Khử trùng lặp bước nhảy chéo và loại bỏ cặp pixel nền trong GLCM (`T1`)**:
   - Dùng $d \in \{1, 3, 5\}$ để bước nhảy chéo $\text{round}(d \cos 45^\circ) = [1, 2, 4]$ không bị trùng, và dịch mức xám thân cá lên `1..16` (nền = `0`) rồi cắt ma trận con `glcm_full[1:, 1:]` để chỉ đếm cặp điểm ảnh nội vùng thân cá.
