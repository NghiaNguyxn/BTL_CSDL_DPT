# CẨM NANG GIẢI THÍCH CHI TIẾT TOÀN BỘ CÔNG THỨC PHẦN 2 (DÀNH CHO TEAM NHÓM 14 - LỚP 04)

> Tài liệu này giải thích **tận gốc từ bản chất bằng lời, ý nghĩa từng ký hiệu toán học, cách tính số chiều cho đến bộ câu hỏi – trả lời vấn đáp với thầy Nguyễn Đình Hóa** đối với toàn bộ 12 thuộc tính (421 chiều + chữ ký nhị phân 64-bit) trong file báo cáo `CSDL ĐPT 1 2 Final.docx`.

## TỔNG QUAN BỘ THUỘC TÍNH 421 CHIỀU CỦA NHÓM 14

### 0. Bức tranh toàn cảnh: Tại sao lại là 421 chiều + 1 chữ ký nhị phân 64-bit?

#### 1. Giải thích bản chất cực dễ hiểu
Khi máy tính nhìn vào một bức ảnh con cá (500×500 pixel trên nền đen), nó không hiểu 'con cá' là gì mà chỉ thấy hàng trăm nghìn điểm ảnh. Để máy tính so sánh được 2 con cá giống hay khác nhau, ta phải đo đạc con cá đó ở 3 góc độ giống hệt mắt người:
1. Nhóm Màu sắc (135 chiều): Con cá có màu gì? Sáng hay tối? Màu nằm ở đầu, thân hay đuôi?
2. Nhóm Hình dạng (140 chiều + chữ ký 64-bit): Con cá thon dài hay tròn bầu? Lưng gù hay bụng võng? Vây đuôi xẻ chữ V hay tròn hình quạt?
3. Nhóm Kết cấu bề mặt (146 chiều): Da cá trơn nhẵn (như cá da trơn Boal) hay có vảy? Vảy to gồ ghề hay vảy nhỏ lấp lánh? Có sọc vằn ở đuôi không?

Tổng cộng: 135 (Màu sắc) + 140 (Hình dạng) + 146 (Kết cấu) = 421 con số thực (421 chiều), đi kèm 1 dãy 64 bit nhị phân (0/1) để lọc nhanh hình bóng con cá.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- Mẹo nhớ quy tắc vàng số 1 (Tách nền - Foreground Only): Mọi công thức trong bài đều CHỈ tính trên các điểm ảnh thuộc vùng thân cá (ký hiệu là Ω_fg), tuyệt đối KHÔNG tính các điểm ảnh nền đen xung quanh. Nhờ đó nền đen chiếm 70–85% khung ảnh không làm sai lệch màu sắc và kết cấu của cá.
- Mẹo nhớ quy tắc vàng số 2 (Chuẩn hóa bất biến kích thước): Mọi công thức đếm điểm ảnh đều được CHIA cho tổng diện tích thân cá |Ω_fg| (hoặc chia cho chiều dài thân cá W). Nhờ vậy một con cá chụp gần (to) và một con cá cùng loài chụp xa (nhỏ) vẫn cho ra cùng một bộ số liệu tương đồng nhau.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Trong 12 mục đặc trưng của nhóm, những cái nào có trong bài giảng trên lớp của thầy, cái nào nhóm tự mở rộng thêm?**
  - *Trả lời: Có 10/12 mục nằm trực tiếp trong Slide Bài giảng Chương Truy vấn ảnh (Lecture 11) của thầy (gồm Histogram màu, Mô-men màu, Bố cục màu phân vùng, Hình thái học cơ bản, Mô-men bất biến Hu, Biến đổi Fourier đường bao, Lưới nhị phân ngưỡng 15%, GLCM, Tamura và Gabor). Nhóm chỉ bổ sung thêm 2 mục mở rộng là Biên dạng Sống lưng – Lườn bụng 16 lát cắt (2.2.2 - để tách riêng lưng gù của cá Katla với bụng võng của cá Ilish) và Mẫu nhị phân cục bộ LBP (2.3.2 - để chống lóa sáng trên vảy cá ướt).*

---

## NHÓM 1: BỘ THUỘC TÍNH MÀU SẮC (135 CHIỀU)

### 2.1.1. Biểu đồ màu HSV thích nghi có ô vô sắc (78 chiều)

![p187.png](../data/report_equations/final_doc_eqs/p187.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Hãy tưởng tượng ta đặt sẵn 78 cái 'rổ phân loại màu' (gọi là 78 bin). Ta đi duyệt qua từng điểm ảnh trên thân cá xem điểm ảnh đó có màu gì thì bỏ 1 phiếu vào chiếc rổ tương ứng. Cuối cùng, lấy số phiếu trong mỗi rổ chia cho tổng số điểm ảnh của toàn bộ thân cá để ra tỷ lệ phần trăm (tổng 78 rổ cộng lại đúng bằng 1.0 hay 100%).

Tại sao phải dùng hệ màu HSV và tách riêng 6 ô Vô sắc (S < 0.15)?
- Hệ màu RGB trộn lẫn màu sắc và độ sáng với nhau. Hệ màu HSV tách riêng thành 3 kênh độc lập: H (Hue: Góc màu từ 0° đến 360° trên vòng tròn màu), S (Saturation: Độ đậm đặc của màu từ 0 đến 1), và V (Value: Độ sáng tối từ 0 đến 1).
- Trên thân cá có rất nhiều vùng vảy trắng bạc, bụng trắng hoặc lưng xám đen. Ở những vùng không có màu này, độ bão hòa S rất thấp (S < 0.15). Khi S quá thấp, góc màu H sẽ bị nhảy loạn xạ do nhiễu ánh sáng đèn. Vì vậy, mọi điểm ảnh có S < 0.15 được tách riêng ra gọi là nhóm Vô sắc (Đen – Xám – Trắng bạc) và chia làm 6 rổ theo độ sáng V từ tối đến sáng bóng.
- Các điểm ảnh có màu rõ rệt (S ≥ 0.15) được gọi là nhóm Hữu sắc và chia vào 72 rổ kết hợp từ: 12 góc màu H (mỗi góc 30°: 12 × 30° = 360°) × 3 mức độ đậm nhạt S × 2 mức sáng tối V = 72 rổ.
-> Tổng cộng: 6 rổ vô sắc + 72 rổ hữu sắc = 78 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- h_k: Tỷ lệ phần trăm (tần suất chuẩn hóa) của rổ màu thứ k (với k chạy từ 0 đến 77). Giá trị của h_k nằm trong đoạn [0, 1] và tổng cả 78 số h_k cộng lại bằng 1.
- Ω_fg (Omega foreground): Tập hợp tất cả các điểm ảnh (x, y) nằm bên trong mặt nạ thân cá (không tính nền đen).
- |Ω_fg|: Tổng số điểm ảnh của thân cá (diện tích thân cá tính bằng pixel). Phép chia 1 / |Ω_fg| ở đầu công thức giúp chuẩn hóa kích thước: cá to 50.000 pixel hay cá nhỏ 25.000 pixel mà có 20% diện tích màu vàng thì h_k đều bằng 0.20 như nhau.
- Σ_{(x,y) ∈ Ω_fg}: Phép cộng duyệt qua toàn bộ các điểm ảnh (x, y) nằm trên thân cá.
- I[ b(x, y) = k ]: Hàm chỉ thị (hàm đếm điều kiện). Trong đó b(x, y) là chỉ số rổ màu của điểm ảnh (x, y). Nếu điểm ảnh (x, y) rơi đúng vào rổ màu k thì I[...] = 1 (được cộng 1 phiếu), nếu rơi vào rổ khác thì I[...] = 0 (không cộng).

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao không tính Histogram màu trên toàn bức ảnh luôn mà chỉ tính trên tập Ω_fg (vùng thân cá)?**
  - *Trả lời: Theo bài giảng Lecture 11 của thầy về Hiệu ứng lấn át nền (Masking Effect), trong bức ảnh 500×500 thì phần nền đen bên ngoài con cá chiếm tới 70%–85% diện tích ảnh. Nếu tính cả nền đen vào Histogram thì ô màu đen sẽ chiếm áp đảo >75% ở mọi bức ảnh, làm chìm nghỉm sự khác biệt màu sắc thực sự trên mình cá. Do đó bắt buộc phải chỉ tính trên vùng thân cá Ω_fg.*
- **Thầy hỏi: Góc Hue là vòng tròn khép kín (0° trùng 360°, đều là màu Đỏ). Nếu vây đỏ của cá Rui một nửa rơi vào bin đầu (0°–30°), một nửa rơi vào bin cuối (330°–360°) thì sao?**
  - *Trả lời: Đó chính là hiện tượng đứt gãy tuần hoàn tại biên 0°/360° của kênh Hue. Để khắc phục, nhóm kết hợp 2 giải pháp: (1) Ở mục 2.1.2 ngay tiếp theo, nhóm bổ sung Mô-men màu trên không gian CIE Lab – nơi trục màu Đỏ (+a*) nằm liên tục ở một đầu dương mà không bị cắt đôi; và (2) Khi đo khoảng cách giữa 2 biểu đồ màu ở Phần 4, các bin màu lân cận nhau trên vòng tròn Hue được liên kết qua ma trận tương đồng màu.*

---

### 2.1.2. Mô-men màu không gian CIE Lab (9 chiều)

![p204.png](../data/report_equations/final_doc_eqs/p204.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Biểu đồ màu HSV ở mục 2.1.1 chia màu sắc vào 78 cái hộp cứng. Nhưng nếu có 2 con cá màu rất giống nhau mà một con nằm ở góc 29° (Hộp 1), con kia lệch sáng nhẹ sang 31° (nhảy sang Hộp 2) thì phép chia hộp sẽ tưởng nhầm 2 con cá khác màu nhau. Vì vậy, mục 2.1.2 dùng phương pháp KHÔNG CHIA HỘP: chuyển toàn bộ điểm ảnh thân cá sang hệ tọa độ màu phẳng CIE L*a*b* (hệ màu thiết kế theo đúng mắt người nhìn) rồi tính 3 con số thống kê liên tục:
1. Trung bình cộng (μ_c - Mean): Màu chủ đạo chung của cả con cá là gì?
2. Độ lệch chuẩn (σ_c - Standard Deviation): Màu sắc trên mình cá đều tăm tắp một màu (σ nhỏ, như cá Katla) hay tương phản mạnh giữa lưng đen, bụng trắng, vây đỏ (σ lớn, như cá Rui)?
3. Độ lệch vẹo (s_c - Skewness): Trên thân cá có một mảng màu nhỏ nào nổi bật lệch hẳn về một phía không (ví dụ thân cá Rui 85% xám bạc nhưng có 15% vây đỏ rực làm phân bố kênh đỏ bị kéo lệch dương)?

Tính 3 con số thống kê này trên 3 kênh (L*, a*, b*) ta được: 3 kênh × 3 con số = 9 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- c ∈ {L*, a*, b*}: Ký hiệu đại diện cho 1 trong 3 kênh màu của không gian CIE Lab:
   + Kênh L* (Lightness): Độ sáng từ tối đen (nhỏ) đến trắng bạc (lớn).
   + Kênh a*: Trục màu từ Xanh lá (nhỏ) sang Đỏ/Hồng (lớn).
   + Kênh b*: Trục màu từ Xanh dương (nhỏ) sang Vàng/Đồng (lớn).
- N: Tổng số điểm ảnh thuộc vùng thân cá (chính là |Ω_fg|).
- P_{c,i}: Giá trị màu của điểm ảnh thân cá thứ i (i chạy từ 1 đến N) trên kênh màu c.
- μ_c (Mô-men bậc 1 - Kỳ vọng/Trung bình): Lấy tổng giá trị màu của tất cả N điểm ảnh trên kênh c rồi chia đều cho N.
- σ_c (Mô-men bậc 2 - Độ lệch chuẩn): Lấy hiệu (P_{c,i} - μ_c) bình phương để đo khoảng cách lệch khỏi mức trung bình, lấy trung bình cộng rồi khai căn bậc hai.
- s_c (Mô-men bậc 3 - Độ lệch vẹo Skewness): Lấy hiệu (P_{c,i} - μ_c) mũ 3 (giữ nguyên dấu âm/dương để biết lệch về bên phải hay bên trái), lấy trung bình rồi chia cho σ_c^3 để chuẩn hóa không thứ nguyên.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Đã có Biểu đồ màu HSV (2.1.1) rồi, tại sao lại dùng thêm Mô-men màu CIE Lab (2.1.2)? Hai cái này có trùng tác dụng không?**
  - *Trả lời: Hai thuộc tính này bù đắp điểm mù toán học cho nhau:
- Thứ nhất, Biểu đồ màu HSV chia 78 ô rời rạc để bắt chi tiết cấu trúc đa màu (như vây đỏ chiếm 10% không bị hòa tan vào 85% thân xám), nhưng lại bị 'hiệu ứng ranh giới ô' khi màu nằm mấp mé vách ngăn giữa 2 bin. Ngược lại, Mô-men CIE Lab tính liên tục không chia ô nên không bao giờ bị nhảy bậc đột ngột khi lệch sáng nhẹ.
- Thứ hai, kênh Hue trong HSV là vòng tròn (0° trùng 360°) nên không thể tính trung bình cộng hay độ lệch Skewness trực tiếp được; phải chuyển sang 3 trục thẳng vuông góc (L*, a*, b*) của CIE Lab thì phép tính Mean, Std, Skewness mới hợp lệ về mặt toán học.*

---

### 2.1.3. Bố cục màu phân vùng giải phẫu (48 chiều)

![p232.png](../data/report_equations/final_doc_eqs/p232.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Hai mục 2.1.1 và 2.1.2 ở trên gom toàn bộ điểm ảnh của cả con cá lại để tính chung, nên bị 'mù vị trí không gian' (biết con cá có màu đỏ nhưng không biết màu đỏ đó nằm ở ngực hay nằm ở vây đuôi).
Vì toàn bộ 1.100 bức ảnh của nhóm đã được chuẩn hóa nằm ngang (Đầu quay sang trái, Đuôi hướng sang phải, Lưng ở trên, Bụng ở dưới), ta cắt khung hình chữ nhật bao quanh con cá thành 6 ô cố định theo đúng giải phẫu cơ thể cá:
- Chia ngang làm 3 phần: Đầu (25% chiều dài bên trái) – Thân giữa (50% ở giữa) – Đuôi (25% bên phải).
- Chia dọc làm 2 nửa: Nửa Lưng phía trên (50% chiều cao trên) – Nửa Bụng phía dưới (50% chiều cao dưới).
-> Giao nhau tạo thành 3 × 2 = 6 vùng giải phẫu: Đầu-Lưng, Đầu-Bụng, Thân-Lưng, Thân-Bụng, Đuôi-Lưng, Đuôi-Bụng.

Trong mỗi vùng nhỏ này, ta đếm một biểu đồ màu rút gọn gồm 8 rổ màu (2 rổ vô sắc Tối/Sáng + 6 rổ sắc màu Hue mỗi rổ 60°).
-> Nối 6 vùng × 8 rổ mỗi vùng = 48 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- r ∈ {1..6}: Chỉ số thứ tự của 6 vùng giải phẫu trên thân cá (1: Đầu-Lưng, 2: Đầu-Bụng, 3: Thân-Lưng, 4: Thân-Bụng, 5: Đuôi-Lưng, 6: Đuôi-Bụng).
- b ∈ {0..7}: Chỉ số của 8 rổ màu rút gọn trong mỗi vùng (b = 0, 1 là 2 rổ vô sắc tối/sáng khi S < 0.15; b = 2..7 là 6 cung màu Hue mỗi cung 60° khi S ≥ 0.15).
- Ω_r: Tập hợp các điểm ảnh thân cá nằm riêng trong vùng giải phẫu thứ r.
- |Ω_r|: Tổng số điểm ảnh thân cá có mặt trong vùng thứ r (dùng làm mẫu số để chuẩn hóa tỷ lệ màu trong nội bộ vùng đó).
- h_{r,b}: Tỷ lệ điểm ảnh mang màu b nằm trong vùng giải phẫu r.
- c_3 = [h_{1,0}, ..., h_{6,7}]: Vector 48 chiều thu được khi xếp nối tiếp kết quả của cả 6 vùng lại với nhau.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao ở mỗi vùng trong 6 vùng chỉ chia 8 bin màu mà không chia 78 bin như ở mục 2.1.1?**
  - *Trả lời: Vì mỗi vùng giải phẫu chỉ chứa một phần diện tích nhỏ của con cá (ví dụ vùng Đuôi chỉ có vài nghìn pixel). Nếu chia tới 78 bin cho mỗi vùng thì tổng số chiều sẽ lên tới 6 × 78 = 468 chiều, làm vector đặc trưng quá lớn và hầu hết các bin đều bằng 0 (dữ liệu bị thưa - sparse). Rút gọn xuống 8 bin màu chủ đạo cho mỗi vùng (48 chiều) là vừa đủ để định vị chính xác vùng màu (như vùng ngực hồng ở Đầu-Bụng của cá Telapia hay vây bụng đỏ ở Thân-Bụng của cá Rui) mà vẫn gọn nhẹ.*

---

## NHÓM 2: BỘ THUỘC TÍNH HÌNH DẠNG (140 CHIỀU + CHỮ KÝ NHỊ PHÂN 64-BIT)

### 2.2.1. Các chỉ số hình thái học cơ thể (8 chiều)

![p247.png](../data/report_equations/final_doc_eqs/p247.png)
![p248.png](../data/report_equations/final_doc_eqs/p248.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Đây là 8 phép đo tỷ lệ hình học cơ bản nhất khi nhìn vào bóng dáng (silhouette) của một con cá, giống như người thợ may đo các tỷ lệ cơ thể vậy. Tất cả 8 chỉ số đều là phép chia giữa hai đại lượng cùng đơn vị (chiều dài chia chiều cao, diện tích chia diện tích, chu vi chia chu vi) nên hoàn toàn KHÔNG phụ thuộc vào việc ảnh con cá to hay nhỏ.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- 1. AspectRatio (AR = W / H - Tỷ lệ khung bao): Lấy chiều dài ngang W chia cho chiều cao đứng H của khung chữ nhật bao quanh con cá. Cá thân dài mảnh như cá leo Boal có AR rất lớn (khoảng 3.5 – 4.5); cá mình bầu bản rộng như cá rô phi Telapia hay cá rô đồng Koi có AR nhỏ (khoảng 1.8 – 2.3).
- 2. Eccentricity (e = √(1 - (b/a)²) - Tâm sai của elip tương đương): Trong đó a là bán trục lớn, b là bán trục nhỏ của hình elip khớp theo thân cá. Nếu cá tròn xoe (b = a) thì e = 0; nếu cá thuôn dài như dải băng (b rất nhỏ so với a, như cá Boal) thì b/a gần bằng 0 nên tâm sai e tiến sát tới 1.
- 3. Circularity (4πA / P² - Độ tròn): Trong đó A là diện tích thân cá, P là chu vi đường viền quanh thân và vây cá. Hình tròn hoàn hảo có giá trị lớn nhất bằng 1. Con cá nào càng thon dài và có vây đuôi xẻ sâu làm chu vi P dài ra thì Circularity càng nhỏ.
- 4. Solidity (A / A_hull - Độ đặc bao lồi): Tưởng tượng ta lấy một sợi dây cao su căng vòng bên ngoài tất cả các chóp vây cá thì tạo thành một đa giác lồi gọi là 'Bao lồi' (Convex Hull) có diện tích A_hull. Lấy diện tích thật của cá A chia cho diện tích bao lồi A_hull:
   + Nếu cá có đuôi tròn liền khối (như cá Koi, Telapia), dây cao su ôm sát thân cá -> A gần bằng A_hull -> Solidity cao (gần 1).
   + Nếu cá có đuôi xẻ chữ V sâu hoắm và thắt eo đuôi sâu (như cá Ilish, Katla, Rui), giữa sợi dây cao su và thân cá có những khoảng trống lõm rất lớn -> A nhỏ hơn A_hull nhiều -> Solidity thấp.
- 5. Extent (A / (W · H) - Độ lấp đầy hộp bao ngang): Lấy diện tích thân cá A chia cho diện tích hình chữ nhật ngang W × H bao ngoài con cá.
- 6. Convexity (P_hull / P - Độ lồi chu vi): Lấy chu vi sợi dây cao su bao lồi P_hull chia cho chu vi thực tế đi men theo từng kẽ vây P. Vây cá càng xẻ sâu, nhấp nhô nhiều thì chu vi thật P càng dài ra so với dây căng P_hull -> Convexity càng giảm.
- 7. Rectangularity (A / A_rect - Độ chữ nhật xoay): Lấy diện tích cá A chia cho diện tích hình chữ nhật bao nhỏ nhất có xoay theo trục cá A_rect.
- 8. EquivDiamRatio (√(4A/π) / √(W² + H²) - Tỷ lệ đường kính tương đương): Tử số √(4A/π) là đường kính của một hình tròn có cùng diện tích A với con cá. Chia đường kính đó cho đường chéo hộp bao √(W² + H²): cá mình càng mập, bản rộng thì tỷ số này càng cao.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao nhóm không đưa trực tiếp Diện tích A (số pixel) và Chu vi P (số pixel) vào vector đặc trưng mà chỉ đưa các tỷ số chia?**
  - *Trả lời: Vì nếu đưa trực tiếp diện tích A hay chu vi P (tính bằng pixel) vào vector đặc trưng thì khi một con cá chụp ở khoảng cách gần hơn một chút (lớn hơn 10% kích thước), diện tích A sẽ tăng vọt lên làm sai lệch khoảng cách. Khi lập tỷ số không thứ nguyên (như 4πA/P², A/A_hull, W/H), đại lượng kích thước triệt tiêu ở cả tử và mẫu nên đảm bảo bất biến tỷ lệ tuyệt đối.*

---

### 2.2.2. Biên dạng sống lưng – lườn bụng (32 chiều)

![p267.png](../data/report_equations/final_doc_eqs/p267.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Giả sử có 2 con cá có cùng chiều dài W và cùng chiều cao H: một con là cá Katla (sống lưng gù vọt lên rất cao ở phía trên, bụng tương đối phẳng), còn một con là cá Ilish (sống lưng thoai thoải nhưng cái bụng lại phình võng sâu xuống phía dưới). Nếu chỉ đo tỷ lệ chung W/H ở mục 2.2.1 thì 2 con này bằng nhau!
Để tách riêng hình dáng của Lưng và Bụng, ta kẻ một đường trục ngang đi qua trọng tâm y_c của con cá (chia con cá thành nửa trên là Lưng, nửa dưới là Bụng). Sau đó, dọc theo chiều dài con cá từ đầu đến đuôi, ta cắt 16 lát cắt thẳng đứng cách đều nhau (k = 1, 2, ..., 16). Tại mỗi lát cắt thứ k:
- Đo khoảng cách từ trục tâm lên mép sống lưng cao nhất -> được độ cao lưng d_dorsal(k).
- Đo khoảng cách từ trục tâm xuống mép lườn bụng thấp nhất -> được độ sâu bụng d_ventral(k).
Chia cả hai khoảng cách này cho chiều dài con cá W để chuẩn hóa. Với 16 lát cắt × 2 số đo (1 lưng + 1 bụng) = 32 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- k ∈ {1, 2, ..., 16}: Thứ tự của 16 lát cắt thẳng đứng dọc theo thân cá từ đầu (k=1) đến đuôi (k=16).
- x_k: Hoành độ (vị trí ngang) của lát cắt thứ k.
- y_c: Tung độ (vị trí dọc) của đường trục ngang đi qua trọng tâm thân cá.
- y_top(x_k): Tung độ điểm mép trên cùng (sống lưng/vây lưng) tại lát cắt x_k. (Trong tọa độ ảnh máy tính, trục y hướng từ trên xuống dưới nên điểm lưng ở trên có tung độ nhỏ hơn y_c, do đó độ cao lưng là y_c - y_top(x_k)).
- y_bot(x_k): Tung độ điểm mép dưới cùng (lườn bụng/vây bụng) tại lát cắt x_k (nằm dưới trục tâm nên độ sâu bụng là y_bot(x_k) - y_c).
- W: Tổng chiều dài ngang của thân cá (dùng làm mẫu số để chuẩn hóa về khoảng [0, 1]).

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Đặc trưng 16 lát cắt lưng – bụng này phát huy tác dụng mạnh nhất khi phân biệt cặp loài cá nào?**
  - *Trả lời: Mạnh nhất khi phân biệt cá chép Ấn Độ Katla (có các lát cắt lưng d_dorsal từ k=3 đến k=8 vọt lên rất cao do cái gù lưng dốc đứng ngay sau đầu) với cá cháy Ilish (có các lát cắt bụng d_ventral ở giữa thân lớn hơn hẳn lát cắt lưng do bụng võng sâu hình lưỡi dao) và cá trôi Rui (có d_dorsal và d_ventral gần như đối xứng bằng nhau).*

---

### 2.2.3. Hệ 7 mô-men bất biến Hu (7 chiều)

![p283.png](../data/report_equations/final_doc_eqs/p283.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Trong vật lý, 'Mô-men' đo cách mà khối lượng của một vật thể phân bố xoay quanh tâm của nó (tập trung ở giữa hay vươn dài ra hai đầu, đối xứng hay lệch vẹo). Nhà toán học Ming-Kuei Hu (1962) đã chứng minh rằng: từ mặt nạ hình dáng của một vật thể, ta có thể tính ra đúng 7 con số đặc biệt (φ_1 đến φ_7) mà dù vật thể đó có bị dịch chuyển đi chỗ khác, bị phóng to/thu nhỏ, hay bị xoay nghiêng đi bất kỳ góc nào thì 7 con số này vẫn KHÔNG ĐỔI!

Quy trình tính gồm 4 bước tuần tự thể hiện ngay trong công thức:
Bước 1 (Tính mô-men trung tâm μ_pq): Trừ tọa độ từng điểm ảnh cho tọa độ trọng tâm (x̄, ȳ) -> giúp BẤT BIẾN VỚI DỊCH CHUYỂN VỊ TRÍ.
Bước 2 (Tính mô-men chuẩn hóa η_pq): Chia μ_pq cho lũy thừa của diện tích thân cá μ_00 -> giúp BẤT BIẾN VỚI PHÓNG TO / THU NHỎ.
Bước 3 (Tổ hợp thành φ_1..φ_7): Kết hợp các η_pq bậc 2 (p+q=2) và bậc 3 (p+q=3) -> giúp BẤT BIẾN VỚI PHÉP XOAY.
Bước 4 (Biến đổi logarit đối xứng h_k): Vì φ_1 có giá trị cỡ 10^-1 nhưng các bậc cao như φ_7 là tích của nhiều số nhỏ nên bé tới 10^-15, nếu để nguyên thì φ_7 quá nhỏ không có tác dụng khi tính khoảng cách. Lấy -sgn(φ_k)·log10(|φ_k|) sẽ biến 10^-1 thành 1 và 10^-15 thành 15, đưa cả 7 chiều về cùng một thang đo cân bằng!

#### 2. Giải nghĩa từng ký hiệu trong công thức
- (x, y) ∈ Ω_fg: Tọa độ của từng điểm ảnh thuộc vùng thân cá.
- (x̄, ȳ): Tọa độ trọng tâm (tâm khối lượng) của vùng thân cá.
- p, q: Bậc của mô-men theo chiều ngang x và chiều dọc y (xét các bậc p + q = 2 và p + q = 3).
- μ_pq: Mô-men trung tâm bậc (p, q). Đặc biệt khi p=0, q=0 thì μ_00 = Σ 1 chính là tổng diện tích điểm ảnh thân cá.
- η_pq (eta): Mô-men trung tâm đã chuẩn hóa kích thước (bằng cách chia μ_pq cho μ_00 mũ (p+q)/2 + 1).
- φ_k (phi_1 .. phi_7): 7 đại lượng bất biến Hu gốc (trong hình công thức viết tường minh φ_1 = η_20 + η_02 đo độ trải rộng theo 2 trục và φ_2 = (η_20 - η_02)² + 4η_11² đo độ thuôn dẹt dọc trục chính).
- sgn(φ_k): Hàm lấy dấu của φ_k (+1 nếu dương, -1 nếu âm, 0 nếu bằng 0).
- ε = 10^-30: Một số dương cực nhỏ cộng thêm vào trong trị tuyệt đối để tránh lỗi toán học log10(0) khi φ_k = 0.
- h_k (k = 1..7): Giá trị cuối cùng của 7 chiều Mô-men Hu sau khi đã cân bằng thang đo logarit.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao trong mẫu số của η_pq lại chia cho μ_00 mũ ((p+q)/2 + 1)?**
  - *Trả lời: Khi một bức ảnh phóng to gấp α lần theo mỗi chiều (cả chiều ngang x và chiều dọc y đều nhân α), thì diện tích μ_00 sẽ tăng lên α² lần, còn đại lượng (x - x̄)^p · (y - ȳ)^q kèm vi phân diện tích dx·dy sẽ tăng lên α^(p+q+2) = (α²)^((p+q)/2 + 1) lần. Do đó, chia cho μ_00^((p+q)/2 + 1) sẽ triệt tiêu chính xác hệ số phóng đại α ở mọi bậc p, q!*

---

### 2.2.4. Hệ số biến đổi Fourier đường viền elip - EFD (29 chiều)

![p298.png](../data/report_equations/final_doc_eqs/p298.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Hãy tưởng tượng bạn cầm một cây bút chì đặt tại chóp mũi con cá, rồi vẽ một đường khép kín chạy dọc theo sống lưng -> vòng qua vây lưng -> lượn qua khe vây đuôi chữ V -> chạy dọc theo bụng -> quay trở về đúng chóp mũi cá. Khi đi lặp đi lặp lại vòng quanh chu vi con cá như vậy, tọa độ ngang x(t) và tọa độ dọc y(t) của đầu bút chì theo bước đi t sẽ tạo thành 2 sóng tuần hoàn có chu kỳ T (T là tổng chu vi đường viền).

Theo định lý chuỗi Fourier: Mọi đường cong khép kín phức tạp bất kỳ đều có thể phân tích thành tổng của nhiều 'hình elip xoay' (gọi là các bậc sóng điều hòa n = 1, 2, ..., 8) cộng chồng lên nhau:
- Bậc điều hòa n = 1: Là 1 hình elip cơ sở mô tả cái khung bầu dục tổng quát nhất của thân cá.
- Bậc điều hòa n = 2, 3: Bắt đầu uốn hình elip đó cho đầu to đuôi nhỏ.
- Bậc điều hòa n = 4..8: Tinh chỉnh các đường cong nhấp nhô của vây lưng và khe xẻ chữ V ở vây đuôi.
- Các bậc quá cao (n > 8): Chỉ là vết răng cưa nhiễu pixel ở mép ảnh nên ta bỏ đi (nhờ đó tự động làm trơn viền cá!).

Tại sao 8 bậc × 4 hệ số = 32 mà lại còn 29 chiều?
Mỗi bậc điều hòa n có 4 hệ số lượng giác (a_n, b_n cho hàm cos/sin của x; và c_n, d_n cho hàm cos/sin của y), nên N = 8 bậc tạo ra 8 × 4 = 32 hệ số. Tuy nhiên, khi chuẩn hóa hình elip bậc 1 (cho bán trục lớn bằng 1, xoay nằm ngang 0°, điểm xuất phát ở mũi cá), thì 3 hệ số đầu tiên của bậc 1 luôn biến thành hằng số cố định (a_1 = 1, b_1 = 0, c_1 = 0) ở TẤT CẢ mọi bức ảnh cá! Vì 3 con số luôn giống hệt nhau ở mọi ảnh thì không giúp phân biệt ảnh này với ảnh kia, nên ta loại bỏ 3 hằng số dư thừa đó đi, giữ lại đúng: 32 - 3 = 29 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- t ∈ [0, T]: Tham số độ dài cung chạy dọc theo đường viền khép kín quanh thân cá (đi từ 0 đến hết 1 vòng chu vi T).
- T: Tổng chiều dài chu vi đường viền thân cá.
- x(t), y(t): Tọa độ ngang và dọc của điểm nằm trên đường viền tại vị trí t.
- A_0, C_0: Tọa độ tâm trung bình của đường viền (bỏ qua vì chỉ thể hiện vị trí đặt con cá trên ảnh).
- N = 8: Tổng số bậc sóng điều hòa (8 hình elip từ thô đến tinh) được giữ lại.
- n ∈ {1, 2, ..., 8}: Chỉ số bậc điều hòa thứ n (n càng nhỏ tần số càng thấp -> mô tả khung dáng chung; n càng lớn tần số càng cao -> mô tả chi tiết vây và đuôi).
- a_n, b_n: Hai hệ số biên độ sóng cos và sin theo trục ngang x của bậc điều hòa thứ n.
- c_n, d_n: Hai hệ số biên độ sóng cos và sin theo trục dọc y của bậc điều hòa thứ n.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao chỉ lấy đến bậc N = 8 mà không lấy N = 50 hay N = 100?**
  - *Trả lời: Vì theo tính chất của biến đổi Fourier đường bao (Lecture 11 Slide 31), các hệ số tần số thấp (n = 1..8) đã nắm bắt trọn vẹn hình dáng tổng thể của thân cá và các thùy vây chính. Các bậc tần số quá cao (n > 15) thực chất chỉ mã hóa các vết răng cưa rời rạc của lưới pixel khi tách nền; việc cắt ở N = 8 vừa giúp vector đặc trưng gọn nhẹ (29 chiều), vừa đóng vai trò như một bộ lọc thông thấp tự động khử nhiễu răng cưa biên.*

---

### 2.2.5. Bộ mô tả lưới không gian 8×8 và Chữ ký nhị phân ngưỡng 15% (64 chiều + 64-bit)

![p315.png](../data/report_equations/final_doc_eqs/p315.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời (Đúng bài toán mẫu trong Slide Lecture 11 của thầy Hóa):
Ta lấy khung hình chữ nhật vừa khít bao quanh con cá, rồi kẻ một cái lưới bàn cờ vua gồm 8 hàng × 8 cột = 64 ô chữ nhật đều nhau đè lên mình con cá.
Trong từng ô bàn cờ (r, c) (với hàng r từ 0 đến 7, cột c từ 0 đến 7):
1. Ta đếm xem diện tích thịt/vây cá chiếm bao nhiêu phần trăm diện tích của cái ô đó -> được con số thực ρ_{r,c} từ 0.0 (ô trống không có cá) đến 1.0 (ô nằm giữa bụng cá nên kín đặc 100% là cá). Ghép 64 ô lại ta được vector 64 chiều số thực.
2. Tiếp theo, áp dụng đúng quy tắc ngưỡng 15% (0.15) trong bài giảng của thầy Hóa: Nếu trong ô đó diện tích cá chiếm từ 15% trở lên (ρ_{r,c} ≥ 0.15) thì ta bật bit nhị phân của ô đó lên b_{r,c} = 1; nếu dưới 15% thì gán b_{r,c} = 0. Ghép 64 bit (0/1) của 64 ô lại ta được 1 số nguyên 64-bit (uint64) gọi là 'Chữ ký nhị phân hình dạng'!

Tác dụng kép cực hay:
- Chữ ký nhị phân 64-bit giúp máy tính lọc thô siêu tốc bằng phép toán XOR đếm số bit khác nhau (khoảng cách Hamming).
- Vector 64 số thực ρ_{r,c} giúp máy tính tính khoảng cách chi tiết để xếp hạng chính xác Top-5.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- r, c ∈ {0, 1, ..., 7}: Chỉ số hàng r và cột c của ô lưới trong bàn cờ 8×8 (tổng cộng 64 ô).
- Cell(r, c): Tập hợp tất cả các điểm ảnh nằm trong ô lưới ở hàng r, cột c.
- |Cell(r, c)|: Tổng diện tích (số điểm ảnh) của cả ô lưới (r, c).
- |Ω_fg ∩ Cell(r, c)|: Số điểm ảnh thuộc vùng thân cá nằm bên trong ô lưới (r, c) (ký hiệu ∩ là phép giao: vừa nằm trong ô lưới, vừa thuộc thân cá).
- ρ_{r,c} ∈ [0, 1] (rho): Tỷ lệ lấp đầy diện tích thân cá tại ô (r, c).
- b_{r,c} ∈ {0, 1}: Bit nhị phân của ô (r, c) sau khi so sánh ρ_{r,c} với ngưỡng chuẩn 0.15 (tức 15%).

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao lại chọn con số ngưỡng 15% (0.15) để gán bit 1 hoặc 0?**
  - *Trả lời: Ngưỡng che phủ 15% được áp dụng trực tiếp từ phương pháp Bộ mô tả lưới nhị phân trong bài giảng Truy vấn hình ảnh (Lecture 11 - Slide 30 & 34) của thầy. Nếu chọn ngưỡng quá thấp (như 1%–5%), một vài tia vây mảnh hoặc nhiễu rìa chạm nhẹ vào ô cũng làm ô bật lên bit 1; còn nếu chọn ngưỡng quá cao (như 50%), các vùng vây đuôi xẻ thùy sẽ bị mất bit 1. Ngưỡng 15% là điểm cân bằng chuẩn để giữ trọn hình bóng của cả thân và hệ thống vây cá.*

---

## NHÓM 3: BỘ THUỘC TÍNH KẾT CẤU BỀ MẶT (146 CHIỀU)

### 2.3.1. Ma trận đồng xuất mức xám vùng thân cá - GLCM (60 chiều)

![p334.png](../data/report_equations/final_doc_eqs/p334.png)
![p335.png](../data/report_equations/final_doc_eqs/p335.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Nếu chỉ đếm xem ảnh cá có bao nhiêu điểm sáng, bao nhiêu điểm tối (như Histogram bậc 1) thì ta không biết được các điểm sáng – tối đó đứng xen kẽ nhau (tạo thành vảy gồ ghề) hay đứng gom lại một chỗ (tạo thành da trơn nhẵn).
Vì vậy, GLCM xét MỐI QUAN HỆ GIỮA 2 ĐIỂM ẢNH ĐỨNG CÁCH NHAU một khoảng cách d theo góc hướng θ:
- Đầu tiên, co nhẹ mặt nạ biên thân cá vào trong 2 pixel (để không chạm ra nền đen bên ngoài), rồi rút gọn độ sáng ảnh xám của thân cá về G = 16 mức xám (từ mức 1 tối nhất đến mức 16 sáng nhất).
- Tiếp theo, chọn 1 khoảng cách d ∈ {1, 3, 5} pixel và 1 góc nhìn θ ∈ {0° (ngang), 45° (chéo lên), 90° (đứng), 135° (chéo xuống)}. Có 3 khoảng cách × 4 góc = 12 tổ hợp (d, θ).
- Với mỗi tổ hợp (d, θ), ta lập một bảng vuông 16×16 gọi là ma trận P(i, j): Ô ở hàng i, cột j ghi xác suất tìm thấy một cặp điểm ảnh trên thân cá mà điểm đầu có độ sáng là i và điểm thứ hai (cách đó d pixel theo góc θ) có độ sáng là j.
- Cuối cùng, từ mỗi bảng P(i, j), thay vì lưu cả bảng 256 số, nhà khoa học Haralick tóm tắt bảng đó thành 5 chỉ số đặc trưng: Contrast, Dissimilarity, Homogeneity, Energy, Correlation.
-> Tổng số chiều: 5 chỉ số × 3 khoảng cách × 4 góc hướng = 60 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- G = 16: Số mức xám đã lượng tử hóa trên vùng thân cá (i, j chạy từ 1 đến 16).
- P(i, j): Xác suất xuất hiện cặp điểm ảnh có mức xám (i, j) cách nhau khoảng cách d theo góc θ (tổng toàn bộ ma trận P(i, j) bằng 1).
- |i - j|: Độ chênh lệch mức xám giữa 2 điểm ảnh trong cặp. Nếu 2 điểm đứng cạnh nhau có cùng độ sáng (da cá trơn đều màu) thì |i - j| = 0. Nếu 1 điểm nằm ở tâm vảy sáng trưng (i=15) còn điểm kia nằm ngay rãnh viền vảy đen sẫm (j=2) thì |i - j| = 13 rất lớn!
- 1. Contrast = Σ (i - j)² · P(i, j) (Độ tương phản cục bộ): Nhân xác suất P(i, j) với bình phương độ lệch (i - j)². Cá có vảy to gồ ghề (Katla) hoặc vảy viền đen sắc nét (Rui) có nhiều cặp điểm chênh sáng mạnh nên Contrast rất cao.
- 2. Dissimilarity = Σ |i - j| · P(i, j) (Độ bất đồng): Tương tự Contrast nhưng chỉ nhân với bậc nhất |i - j| (ít bị phóng đại bởi các điểm nhiễu cực đoan hơn so với bình phương).
- 3. Homogeneity = Σ P(i, j) / (1 + (i - j)²) (Độ đồng nhất / Độ trơn): Chia cho (1 + (i - j)²). Khi da cá trơn láng đều màu như cá leo Boal, hầu hết các cặp điểm đều có i ≈ j nên mẫu số bằng 1 -> Homogeneity đạt giá trị rất cao.
- 4. Energy = √( Σ P(i, j)² ) (Năng lượng / Độ đồng đều): Khi bề mặt cá đồng đều, xác suất P(i, j) chỉ tập trung cao ở một vài ô trên đường chéo chính nên tổng bình phương P(i, j)² lớn -> Energy cao.
- 5. Correlation = Σ ((i - μ_x)(j - μ_y) P(i, j)) / (σ_x · σ_y) (Độ tương quan hướng): Trong đó μ_x, μ_y và σ_x, σ_y là trung bình và độ lệch chuẩn theo hàng và cột của ma trận P(i, j). Đo xem mức xám biến thiên có theo quy luật hàng lối tuyến tính dọc theo hướng θ hay không.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao nhóm lại phải co mặt nạ (erode) vào trong 2 pixel trước khi tính GLCM?**
  - *Trả lời: Vì GLCM xét cặp 2 điểm ảnh cách nhau khoảng cách d. Nếu xét điểm ảnh nằm sát mép ngoài cùng của con cá, điểm thứ hai trong cặp sẽ nhảy ra ngoài vùng nền đen (mức sáng = 0), tạo ra độ chênh lệch (i - j) cực lớn giả tạo giữa thân cá và nền đen. Việc co mặt nạ vào 2 pixel và chỉ trích ma trận trên các mức xám 1..16 thuộc thân cá giúp đảm bảo 100% cả 2 điểm ảnh trong mọi cặp đều nằm trọn trên da cá.*
- **Thầy hỏi: Tại sao chọn 3 khoảng cách là d ∈ {1, 3, 5} mà không chọn {1, 2, 3}?**
  - *Trả lời: Vì trên lưới pixel vuông, khi xét theo góc chéo 45° hoặc 135°, bước nhảy tọa độ được làm tròn theo round(d · cos 45°). Nếu dùng d = 1 và d = 2 thì 1·cos(45°) ≈ 0.71 và 2·cos(45°) ≈ 1.41 khi làm tròn số nguyên dễ bị trùng bước nhảy pixel chéo. Chọn d ∈ {1, 3, 5} giúp bước nhảy chéo bằng {1, 2, 4} pixel hoàn toàn phân biệt nhau, đồng thời bao quát được cả vi kết cấu sát nhau (1px) lẫn chu kỳ vảy rộng hơn (3px, 5px).*

---

### 2.3.2. Mẫu nhị phân cục bộ đồng nhất - Uniform LBP (59 chiều)

![p352.png](../data/report_equations/final_doc_eqs/p352.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Tại mỗi điểm ảnh tâm (x_c, y_c) trên thân cá (có độ sáng là g_c), ta nhìn ra P = 8 điểm ảnh hàng xóm đứng xung quanh nó trên vòng tròn bán kính R = 1 pixel (độ sáng lần lượt là g_0, g_1, ..., g_7).
Quy tắc mã hóa cực kỳ đơn giản:
- Hàng xóm nào sáng hơn hoặc bằng điểm tâm (g_p ≥ g_c) thì ghi số 1.
- Hàng xóm nào tối hơn điểm tâm (g_p < g_c) thì ghi số 0.
Đi một vòng qua 8 hàng xóm, ta thu được một dãy 8 chữ số nhị phân (8-bit), có tất cả 2^8 = 256 kiểu dãy 8-bit khác nhau.

Tại sao từ 256 mẫu lại rút gọn thành đúng 59 chiều (Thế nào là Mẫu đồng nhất U ≤ 2)?
Nhà khoa học Ojala phát hiện ra rằng: trên bề mặt tự nhiên (như vảy cá), một bờ cạnh vảy hay một góc vảy thật sự luôn chia vùng nhỏ 3×3 pixel thành 1 bên sáng (các bit 1 đứng tụm liền nhau) và 1 bên tối (các bit 0 đứng tụm liền nhau). Khi đi 1 vòng tròn quanh 8 bit đó, ta chỉ bước qua ranh giới từ 0 sang 1 rồi từ 1 về 0 TỐI ĐA 2 LẦN (gọi là số lần chuyển bit U ≤ 2).
- Ví dụ mẫu ĐỒNG NHẤT (U ≤ 2): `00000000` (U=0, vùng phẳng), `11111111` (U=0, đốm tối), `00111000` (U=2, bờ cạnh vảy), hoặc `01110011` (nối vòng tròn thì 5 số 1 đứng liền nhau và 3 số 0 đứng liền nhau nên U=2, vẫn là mẫu đồng nhất!). Trong 256 mẫu, tính toán tổ hợp có đúng 58 mẫu đồng nhất như vậy (gồm 2 mẫu U=0 và 7 × 8 = 56 mẫu U=2).
- Ví dụ mẫu NHIỄU KHÔNG ĐỒNG NHẤT (U ≥ 4): `01010101` (U=8) hoặc `01101001` (U=6) – cứ 1 điểm sáng lại xen 1 điểm tối nhảy loạn xạ trong phạm vi 1 pixel, đó là nhiễu hạt cảm biến hoặc giao cắt khe vảy rối.
Thay vì vứt bỏ 198 mẫu không đồng nhất đó, hệ thống giữ riêng 58 cái rổ cho 58 mẫu đồng nhất, và gom toàn bộ 198 mẫu không đồng nhất chung vào 1 cái rổ thứ 59!
-> Tổng cộng: 58 rổ đồng nhất + 1 rổ gom mẫu không đồng nhất = 59 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- P = 8, R = 1: Số điểm lân cận là 8 điểm nằm trên vòng tròn bán kính 1 pixel quanh tâm.
- g_c: Mức xám (độ sáng) của điểm ảnh tâm (x_c, y_c).
- g_p (p = 0..7): Mức xám của điểm ảnh lân cận thứ p xung quanh tâm.
- s(z): Hàm bước nhảy đơn vị (hàm lấy dấu). Với z = g_p - g_c: nếu g_p - g_c ≥ 0 (lân cận sáng hơn hoặc bằng tâm) thì s(z) = 1; nếu g_p - g_c < 0 (lân cận tối hơn tâm) thì s(z) = 0.
- 2^p: Trọng số nhị phân tại vị trí p để ghép 8 bit thành một số nguyên từ 0 đến 255.
- U(LBP_{P,R}): Số lần chuyển đổi trạng thái giữa bit 0 và bit 1 khi đi hết 1 vòng tròn khép kín qua 8 bit:
   + |s(g_0 - g_c) - s(g_{P-1} - g_c)| là kiểm tra bước chuyển nối giữa điểm đầu (p=0) và điểm cuối (p=7) của vòng tròn.
   + Σ_{p=1}^{P-1} |s(g_p - g_c) - s(g_{p-1} - g_c)| là đếm số lần bit liền kề khác nhau khi đi từ p=0 đến p=7.

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao nói LBP 'bất biến với sự thay đổi độ sáng đơn điệu' và điều đó giúp tìm sự tương đồng như thế nào?**
  - *Trả lời: Vì hàm s(g_p - g_c) chỉ xét DẤU (lớn hơn hay nhỏ hơn) chứ không lấy độ lớn hiệu số. Giả sử chụp 2 bức ảnh cùng 1 loài cá dưới ánh đèn yếu (tâm g_c = 50, lân cận g_p = 60 -> 60 > 50 nên bit = 1) và dưới ánh đèn mạnh làm mọi điểm ảnh sáng tăng thêm +100 đơn vị (tâm g_c = 150, lân cận g_p = 160 -> 160 > 150 nên bit vẫn = 1). Mã LBP của 2 bức ảnh giữ nguyên giống hệt nhau 100%, giúp hệ thống tìm được sự tương đồng chính xác giữa các ảnh cá chụp ở điều kiện ánh sáng mạnh yếu khác nhau!*
- **Thầy hỏi: Tại sao có đúng 58 mẫu đồng nhất (U ≤ 2)? Em tính sao ra con số 58?**
  - *Trả lời: Trong vòng tròn 8 bit:
- Trường hợp U = 0 (không chuyển bit lần nào): Có 2 mẫu là toàn số 0 (`00000000`) và toàn số 1 (`11111111`).
- Trường hợp U = 2 (có đúng 1 cụm số 1 đứng liền nhau): Cụm số 1 đó có thể dài 1 bit, 2 bit, 3 bit, 4 bit, 5 bit, 6 bit hoặc 7 bit (7 độ dài khác nhau). Với mỗi độ dài, cụm số 1 đó có thể xoay đặt ở 8 vị trí bắt đầu khác nhau trên vòng tròn 8 điểm -> có 7 × 8 = 56 mẫu.
- Cộng lại: 2 + 56 = 58 mẫu đồng nhất!*

---

### 2.3.3. Đặc trưng kết cấu tri giác Tamura (3 chiều)

![p368.png](../data/report_equations/final_doc_eqs/p368.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời:
Nếu GLCM và LBP là các con số thống kê toán học thuần túy, thì bộ đặc trưng Tamura được xây dựng từ tâm lý học thị giác – đo đúng 3 tính chất mà mắt người cảm nhận đầu tiên khi nhìn vào bề mặt vảy cá:
1. Độ thô (Coarseness - F_crs): Vảy cá to bản thô ráp (như cá chép Katla, cá trôi Rui) hay vảy nhỏ li ti mịn màng (như cá cháy Ilish, cá rô đồng Koi)?
   -> Cách đo: Tại mỗi điểm ảnh (x, y), ta thử đặt các ô cửa sổ hình vuông có kích thước tăng dần theo lũy thừa của 2: 2^1×2^1 (2×2 px), 2^2×2^2 (4×4 px), 2^3×2^3 (8×8 px), 2^4×2^4 (16×16 px). Cửa sổ 2^k nào vừa khít với kích thước 1 chiếc vảy cá tại điểm đó thì độ chênh lệch mức xám giữa 2 nửa đối diện của cửa sổ sẽ đạt cực đại (gọi bậc đó là k_max). Sau đó lấy trung bình kích thước cửa sổ tối ưu 2^{k_max} trên toàn bộ thân cá!
2. Độ tương phản (Contrast - F_con): Ranh giới sáng – tối giữa các vảy cá có đập mạnh vào mắt không?
3. Độ định hướng (Directionality - F_dir): Các đường gờ vảy và tia vây có xếp thẳng hàng theo các hướng rõ rệt hay nằm tán xạ ngẫu nhiên?

#### 2. Giải nghĩa từng ký hiệu trong công thức
- 1. Công thức Độ thô F_crs = (1 / |Ω_fg|) · Σ 2^{k_max(x, y)}:
   + |Ω_fg|: Tổng số điểm ảnh thuộc vùng thân cá.
   + k_max(x, y) ∈ {1, 2, 3, 4}: Bậc lũy thừa làm cho độ chênh lệch trung bình mức xám giữa hai nửa cửa sổ đạt lớn nhất tại điểm (x, y).
   + 2^{k_max(x, y)}: Kích thước thực tế (tính bằng pixel) của phần tử vảy cá tại điểm (x, y). Cá vảy càng to thì F_crs càng lớn.
- 2. Công thức Độ tương phản F_con = σ / (α_4)^{1/4} với α_4 = μ_4 / σ^4:
   + σ: Độ lệch chuẩn mức xám trên vùng thân cá (đo biên độ dao động sáng tối).
   + μ_4: Mô-men trung tâm bậc 4 của mức xám (μ_4 = trung bình cộng của (I - μ)^4).
   + α_4 = μ_4 / σ^4: Hệ số nhọn (Kurtosis) của biểu đồ phân bố mức xám. Nếu ảnh có cả vùng sáng rõ và vùng tối rõ đối lập nhau (biểu đồ mức xám phân cực rộng, đỉnh bẹt -> α_4 nhỏ), khi lấy σ chia cho α_4 mũ 1/4 sẽ làm F_con tăng lên đúng với cảm nhận tương phản cao của mắt người.
- 3. Công thức Độ định hướng F_dir = 1 - r · n_p · Σ (φ - φ_p)² · H_D(φ):
   + φ: Góc hướng của cạnh (tính bằng đạo hàm Sobel ngang và dọc tại mỗi điểm ảnh trên thân cá).
   + H_D(φ): Biểu đồ tần suất (Histogram) của các góc hướng cạnh φ trên thân cá.
   + n_p: Số lượng đỉnh hướng chủ đạo (peaks) trên biểu đồ H_D(φ); φ_p là vị trí góc của đỉnh thứ p; w_p là khoảng góc quanh đỉnh p; r là hệ số chuẩn hóa.
   + Ý nghĩa: Đại lượng tổng Σ (φ - φ_p)² · H_D(φ) đo độ trải rộng (phương sai) quanh đỉnh hướng chính. Nếu các hàng vảy xếp thẳng tắp theo 1 hướng rõ rệt thì đỉnh nhọn hoắt -> tổng phương sai nhỏ -> 1 trừ đi số nhỏ sẽ cho F_dir lớn (gần bằng 1).

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao Độ tương phản của Tamura (F_con) không chỉ lấy mỗi độ lệch chuẩn σ mà còn phải chia cho căn bậc 4 của Kurtosis (α_4^{1/4})?**
  - *Trả lời: Vì theo nghiên cứu tâm lý thị giác của Tamura, nếu hai bức ảnh có cùng độ lệch chuẩn σ, nhưng bức ảnh thứ nhất chỉ có một vài điểm lóa sáng cực mạnh trên nền xám đều (phân bố nhọn hoắt, Kurtosis α_4 rất lớn) thì mắt người không thấy tương phản rõ bằng bức ảnh thứ hai có các mảng sáng và mảng tối phân bố đều thành hai cực (phân bố bẹt, Kurtosis α_4 nhỏ). Do đó chia σ cho α_4^{1/4} giúp chỉ số tương phản khớp chính xác với thị giác con người.*

---

### 2.3.4. Năng lượng bộ lọc sóng Gabor đa hướng (24 chiều)

![p385.png](../data/report_equations/final_doc_eqs/p385.png)

#### 1. Giải thích bản chất cực dễ hiểu
Bản chất bằng lời (Hãy hình dung như '12 chiếc kính soi gợn sóng'):
Trên mình cá có những họa tiết lặp đi lặp lại theo chu kỳ như các gợn sóng: ví dụ hàng vảy mắt cáo đan chéo trên mình cá Rui, hoặc 6–8 vạch sọc vằn thẳng đứng trên vây đuôi cá rô phi Telapia.
Để bắt được các họa tiết dạng sóng đó, ta chế tạo một 'con tem gợn sóng' gọi là Bộ lọc Gabor 2 chiều. Con tem này được tạo ra bằng cách nhân 2 hàm toán học với nhau:
1. Hàm hình quả chuông Gaussian: Ở tâm con tem thì rõ nhất, càng ra xa rìa con tem thì mờ dần về 0 -> giúp con tem chỉ soi vào một vùng nhỏ cục bộ.
2. Hàm sóng hình cos/sin tuần hoàn: Tạo ra các vạch sáng – tối chạy song song với nhau, cách nhau một bước sóng λ và nghiêng theo góc θ.

Ta tạo ra một ngân hàng gồm 12 con tem ứng với:
- 3 bước sóng (độ thưa của vạch sóng) λ ∈ {4, 8, 16} pixel: λ = 4 soi vảy nhỏ/mịn, λ = 8 soi vảy vừa, λ = 16 soi vảy to và sọc đuôi lớn.
- 4 góc nghiêng θ ∈ {0° (sóng đứng), 45° (sóng chéo phải), 90° (sóng ngang), 135° (sóng chéo trái)}.
-> 3 bước sóng × 4 góc = 12 bộ lọc Gabor.

Khi trượt từng con tem lên ảnh xám của thân cá, ở chỗ nào trên da cá có hàng vảy hoặc sọc vằn TRÙNG ĐÚNG KHOẢNG CÁCH λ VÀ TRÙNG ĐÚNG GÓC NGHIÊNG θ của con tem, thì năng lượng phản hồi E_{λ,θ}(x, y) tại đó sẽ cộng hưởng vọt lên rất mạnh! Với mỗi bản đồ năng lượng của 1 bộ lọc, ta tính 2 con số thống kê trên vùng thân cá là Trung bình (μ) và Độ lệch chuẩn (σ).
-> Tổng số chiều: 12 bộ lọc × 2 con số (μ, σ) = 24 chiều.

#### 2. Giải nghĩa từng ký hiệu trong công thức
- g_{λ,θ}(x, y): Giá trị của bộ lọc (con tem) Gabor tại tọa độ (x, y) ứng với bước sóng λ và góc hướng θ.
- x' = x·cos(θ) + y·sin(θ) và y' = -x·sin(θ) + y·cos(θ): Công thức xoay hệ trục tọa độ (x, y) đi một góc θ để con tem nghiêng theo đúng hướng cần dò.
- exp( - (x'² + γ²·y'²) / (2σ²) ): Hàm bao hình quả chuông Gaussian 2 chiều. Trong đó σ = 0.56λ là độ rộng của quả chuông (tự động co giãn tỉ lệ thuận với bước sóng λ), và γ = 0.5 là tỷ lệ độ dẹt elip của bộ lọc.
- cos( 2π·x'/λ + ψ ): Hàm sóng tuần hoàn có bước sóng λ (khoảng cách giữa 2 đỉnh sóng sáng liên tiếp tính bằng pixel) và góc lệch pha ψ (psi).
- R_{λ,θ}^{real}(x, y) và R_{λ,θ}^{imag}(x, y): Kết quả tích chập (trượt bộ lọc lên ảnh cá) khi dùng sóng cos (phần thực, ψ = 0°) và khi dùng sóng sin (phần ảo, ψ = 90°).
- E_{λ,θ}(x, y) = √( [R^{real}]² + [R^{imag}]² ): Biên độ năng lượng Gabor tại điểm ảnh (x, y). Lấy căn bậc hai tổng bình phương phần thực (cos) và phần ảo (sin) theo hằng đẳng thức cos² + sin² = 1 giúp năng lượng E luôn đạt cực đại trên vùng có vảy cá mà KHÔNG phụ thuộc vào việc tâm chiếc vảy đang nằm trúng đỉnh sóng hay sườn sóng!
- μ_{λ,θ} và σ_{λ,θ}: Giá trị trung bình và độ lệch chuẩn của năng lượng E_{λ,θ}(x, y) tính trên toàn bộ các điểm ảnh thuộc vùng thân cá Ω_fg (sau khi đã co mặt nạ 2 pixel).

#### 3. Câu hỏi vấn đáp thường gặp & Cách trả lời ăn điểm
- **Thầy hỏi: Tại sao không chỉ lọc bằng hàm cos (phần thực R_real) thôi mà phải lọc thêm cả hàm sin (phần ảo R_imag) rồi lấy căn bậc hai tổng bình phương?**
  - *Trả lời: Vì nếu chỉ dùng 1 hàm cos, tại vị trí đỉnh vảy cá trùng với đỉnh sóng cos thì phản hồi lớn, nhưng chỉ cần dịch sang bên cạnh vài pixel trúng điểm sóng cos đi qua số 0 thì phản hồi lại tụt về 0 (gọi là hiện tượng phụ thuộc pha). Khi kết hợp cả bộ lọc cos (pha 0°) và bộ lọc sin (pha 90°) rồi lấy E = √(R_real² + R_imag²), nhờ công thức lượng giác cos²α + sin²α = 1, ta thu được đường bao biên độ năng lượng mượt mà, bất biến với độ dịch pha cục bộ của vảy cá.*

---
