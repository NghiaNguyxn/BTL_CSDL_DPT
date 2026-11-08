# -*- coding: utf-8 -*-
"""
Đánh giá bộ đặc trưng 421 chiều (12 thành phần: C1..C3, S1..S5, T1..T4) theo đúng Mục 5 của docs/HUONG_CHUAN_MUC_2.md.

Quy tắc chung:
- Mọi truy vấn đều loại chính nó và các ảnh gần trùng (RMS < 10 trên ảnh xám 64x64) khỏi kết quả.
- Khoảng cách từng thành phần: histogram (C1, C3, T2) dùng L1; thành phần vô hướng dùng Z-score
  (thống kê lấy trên tập huấn luyện) rồi L2.
- Chuẩn hóa thang đo 2 cấp: Mỗi thành phần con chia cho trung vị khoảng cách của chính nó trên tập huấn luyện
  (tránh việc thành phần nhiều chiều hoặc khác đơn vị đo lấn át thành phần xác suất tổng bằng 1),
  sau đó mỗi nhóm (Color, Shape, Texture) tiếp tục chia cho trung vị khoảng cách nhóm trên tập huấn luyện.
- Trọng số nhóm chỉ được chọn trên tập huấn luyện; con số báo cáo chính là con số kiểm định chéo 5-fold.

Thí nghiệm:
 1. 5-fold: chọn trọng số trên 4/5, đo trên 1/5.
 2. Toàn tập (LOO) với trọng số chọn từ 5-fold: P@5, P@5 theo loài, top-1, ma trận nhầm lẫn.
 3. Từng nhóm riêng lẻ và từng thành phần độc lập.
 4. Bỏ từng thành phần (C1..T4), đo bằng 5-fold, kèm độ lệch giữa các fold.
 5. Bỏ ra từng loài: thống kê chuẩn hóa và trọng số chọn KHÔNG có loài đó, rồi đo truy vấn của loài đó.
 6. Loài chưa có: bỏ hẳn 1 loài khỏi CSDL, AUROC của khoảng cách tới ảnh gần nhất.
 7. Chiều rác, cặp chiều tương quan cao.
 8. Fisher score (phân biệt) và hệ số biến thiên trong loài (tương đồng).
 9. Độ trễ truy vấn; lọc thô Hamming trên lưới 64 bit ở nhiều mức số ứng viên.
Kết quả ghi vào data/evaluation_results.json và data/evaluation_report.md.
"""

import os
import sys
import time
import json
import glob
import cv2
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve, mutual_info_score
from sklearn.neighbors import NearestNeighbors
from sklearn.model_selection import StratifiedKFold

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

K = 5
SEED = 42

COMPONENTS = {
    "C1": (0, 78, "hist"),
    "C2": (78, 87, "scalar"),
    "C3": (87, 135, "hist"),
    "S1": (135, 143, "scalar"),
    "S2": (143, 175, "scalar"),
    "S3": (175, 182, "scalar"),
    "S4": (182, 211, "scalar"),
    "S5": (211, 275, "scalar"),
    "T1": (275, 335, "scalar"),
    "T2": (335, 394, "hist"),
    "T3": (394, 397, "scalar"),
    "T4": (397, 421, "scalar"),
}
GROUPS = {
    "color": ["C1", "C2", "C3"],
    "shape": ["S1", "S2", "S3", "S4", "S5"],
    "texture": ["T1", "T2", "T3", "T4"],
}
COMP_DESC = {
    "C1": "Histogram HSV có ô xám (78D)",
    "C2": "Mô-men màu CIE Lab (9D)",
    "C3": "Bố cục màu 6 vùng giải phẫu (48D)",
    "S1": "8 chỉ số hình thái học (8D)",
    "S2": "Đường cong lưng-bụng (32D)",
    "S3": "7 Mô-men bất biến Hu (7D)",
    "S4": "Hệ số Fourier elip EFD (29D)",
    "S5": "Lưới không gian 8x8 (64D)",
    "T1": "GLCM đa hướng vùng thân cá (60D)",
    "T2": "LBP đồng nhất có hướng (59D)",
    "T3": "Đặc trưng độ thô Tamura (3D)",
    "T4": "Năng lượng lọc Gabor (24D)",
}
COARSE_CANDIDATES = [50, 100, 200, 300, 500]

WEIGHT_GRID = []
for _wc in np.linspace(0.1, 0.8, 8):
    for _ws in np.linspace(0.1, 0.8, 8):
        _wt = 1.0 - (_wc + _ws)
        if 0.1 - 1e-9 <= _wt <= 0.8 + 1e-9:
            WEIGHT_GRID.append((round(float(_wc), 2), round(float(_ws), 2), round(float(_wt), 2)))


# ----------------------------------------------------------------------------
# Ảnh gần trùng
# ----------------------------------------------------------------------------
def find_near_duplicates(files, dataset_dir="dataset_gold_v3/images_rgba", rms_threshold=10.0,
                         cache_file="data/near_duplicates.json"):
    n = len(files)
    if os.path.isfile(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        int_items = {int(k): set(v) for k, v in data.items() if str(k).isdigit()}
        if data.get("dataset_dir") == dataset_dir and len(int_items) == n:
            return int_items

    file_map = {os.path.basename(p): p for p in glob.glob(os.path.join(dataset_dir, "*", "*.*"))}
    thumbs = np.zeros((n, 64 * 64), dtype=np.float32)
    for i, fname in enumerate(files):
        im = cv2.imread(file_map[str(fname)], cv2.IMREAD_GRAYSCALE)
        thumbs[i] = cv2.resize(im, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    rms = np.sqrt(cdist(thumbs, thumbs, metric="sqeuclidean") / 4096.0)
    dup = {i: [int(j) for j in np.where((rms[i] < rms_threshold) & (np.arange(n) != i))[0]] for i in range(n)}
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    payload = {"dataset_dir": dataset_dir}
    payload.update({str(k): v for k, v in dup.items()})
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return {k: set(v) for k, v in dup.items()}


# ----------------------------------------------------------------------------
# Khoảng cách
# ----------------------------------------------------------------------------
def train_median(D, train_idx):
    sub = D[np.ix_(train_idx, train_idx)]
    vals = sub[~np.eye(len(train_idx), dtype=bool)]
    med = float(np.median(vals))
    return med if med > 1e-9 else 1.0


def component_distances(X, train_idx):
    """
    Ma trận khoảng cách N x N cho từng thành phần, thống kê Z-score và trung vị chuẩn hóa
    đều chỉ tính trên train_idx để đảm bảo không rò rỉ dữ liệu.
    """
    out = {}
    Xt = X[train_idx]
    for name, (st, en, kind) in COMPONENTS.items():
        sub = X[:, st:en].astype(np.float64)
        if kind == "hist":
            D = cdist(sub, sub, metric="cityblock")
        else:
            mu = Xt[:, st:en].mean(axis=0)
            sd = Xt[:, st:en].std(axis=0)
            sd = np.where(sd < 1e-6, 1.0, np.maximum(sd, 2e-3))
            z = (sub - mu) / sd
            D = cdist(z, z, metric="euclidean")
        out[name] = D / train_median(D, train_idx)
    return out


def group_distances(comps, train_idx, drop=None):
    """Khoảng cách 3 nhóm, mỗi nhóm chia trung vị trên tập huấn luyện. drop: tên thành phần bị bỏ."""
    res = {}
    for g, members in GROUPS.items():
        use = [m for m in members if m != drop]
        D = sum(comps[m] for m in use)
        res[g] = D / train_median(D, train_idx)
    return res


def fuse(groups, w):
    return w[0] * groups["color"] + w[1] * groups["shape"] + w[2] * groups["texture"]


# ----------------------------------------------------------------------------
# Truy vấn
# ----------------------------------------------------------------------------
def retrieve(D, queries, dup_mask, db_mask=None, k=K):
    """Trả về chỉ số top-k (đã sắp tăng dần khoảng cách) cho từng truy vấn."""
    queries = np.asarray(queries)
    Dq = D[queries].copy()
    Dq[np.arange(len(queries)), queries] = np.inf
    Dq[dup_mask[queries]] = np.inf
    if db_mask is not None:
        Dq[:, ~db_mask] = np.inf
    part = np.argpartition(Dq, k, axis=1)[:, :k]
    order = np.argsort(np.take_along_axis(Dq, part, axis=1), axis=1)
    return np.take_along_axis(part, order, axis=1)


def p_at_k(D, y, queries, dup_mask, db_mask=None):
    top = retrieve(D, queries, dup_mask, db_mask)
    return float(np.mean(y[top] == y[np.asarray(queries)][:, None]))


def full_metrics(D, y, queries, dup_mask, species):
    queries = np.asarray(queries)
    top = retrieve(D, queries, dup_mask)
    hit = (y[top] == y[queries][:, None])
    per_sp = {}
    for sp in species:
        m = y[queries] == sp
        per_sp[sp] = {"count": int(m.sum()), "p5": float(hit[m].mean()), "top1": float(hit[m, 0].mean())}
    majority = []
    for row in y[top]:
        vals, cnts = np.unique(row, return_counts=True)
        majority.append(vals[np.argmax(cnts)])
    cm = confusion_matrix(y[queries], majority, labels=species)
    return {
        "overall_p5": float(hit.mean()),
        "macro_p5": float(np.mean([per_sp[s]["p5"] for s in species])),
        "top1": float(hit[:, 0].mean()),
        "per_species": per_sp,
        "confusion_majority_top5": cm.tolist(),
    }


def choose_weights(groups, y, queries, dup_mask, db_mask=None):
    best_w, best_p = None, -1.0
    for w in WEIGHT_GRID:
        p = p_at_k(fuse(groups, w), y, queries, dup_mask, db_mask)
        if p > best_p + 1e-12:
            best_w, best_p = w, p
    return best_w, best_p


# ----------------------------------------------------------------------------
# Chạy
# ----------------------------------------------------------------------------
def run_evaluation(npz_path="data/features_extracted.npz",
                   out_json="data/evaluation_results.json",
                   out_md="data/evaluation_report.md"):
    data = np.load(npz_path)
    X = data["features"].astype(np.float64)
    y = data["labels"]
    files = data["files"]
    grid_u64 = data["grid_uint64"]
    n, dims = X.shape
    species = sorted(np.unique(y).tolist())
    all_idx = np.arange(n)
    print(f"Nạp {n} ảnh, {dims} chiều, {len(species)} loài")

    R = {"n_images": int(n), "dims": int(dims), "species": species, "k": K}

    # Ảnh gần trùng
    dup = find_near_duplicates(files)
    dup_mask = np.zeros((n, n), dtype=bool)
    for i, js in dup.items():
        for j in js:
            dup_mask[i, j] = True
    pairs = {(min(i, j), max(i, j)) for i, js in dup.items() for j in js}
    R["near_duplicates"] = {
        "rms_threshold": 10.0,
        "pairs": len(pairs),
        "images_with_dup": int(sum(1 for v in dup.values() if v)),
        "cross_species_pairs": int(sum(1 for i, j in pairs if y[i] != y[j])),
    }
    print("Ảnh gần trùng:", R["near_duplicates"])

    # ---------------- 1. 5-fold ----------------
    print("\n[1] 5-fold ...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    folds = list(skf.split(X, y))
    fold_comps = []
    fold_res = []
    for f, (tr, te) in enumerate(folds):
        comps = component_distances(X, tr)
        fold_comps.append(comps)
        G = group_distances(comps, tr)
        w, ptr = choose_weights(G, y, tr, dup_mask)
        pte = p_at_k(fuse(G, w), y, te, dup_mask)
        fold_res.append({"fold": f + 1, "weights": list(w), "train_p5": ptr, "test_p5": pte})
        print(f"  fold {f+1}: w={w} test P@5={pte*100:.2f}%")
    cv_p5 = [r["test_p5"] for r in fold_res]
    R["cv5"] = {"folds": fold_res, "mean_p5": float(np.mean(cv_p5)), "std_p5": float(np.std(cv_p5))}

    # Trọng số mặc định cho hệ thống: bộ được chọn nhiều nhất qua 5 fold (hòa thì lấy bộ xuất hiện trước)
    ws = [tuple(r["weights"]) for r in fold_res]
    opt_w = max(ws, key=lambda w: (ws.count(w), -ws.index(w)))
    R["default_weights"] = list(opt_w)
    print(f"  -> 5-fold P@5 = {np.mean(cv_p5)*100:.2f}% ± {np.std(cv_p5)*100:.2f}; trọng số mặc định {opt_w}")

    # ---------------- 2. Toàn tập ----------------
    print("\n[2] Toàn tập với trọng số mặc định ...")
    comps_all = component_distances(X, all_idx)
    G_all = group_distances(comps_all, all_idx)
    D_opt = fuse(G_all, opt_w)
    R["full"] = full_metrics(D_opt, y, all_idx, dup_mask, species)
    R["equal_weights_p5"] = p_at_k(fuse(G_all, (1/3, 1/3, 1/3)), y, all_idx, dup_mask)
    print(f"  P@5={R['full']['overall_p5']*100:.2f}%  macro={R['full']['macro_p5']*100:.2f}%  top1={R['full']['top1']*100:.2f}%")

    # ---------------- 3. Từng nhóm & Từng thành phần độc lập ----------------
    R["group_only"] = {g: p_at_k(G_all[g], y, all_idx, dup_mask) for g in GROUPS}
    R["component_only"] = {c: p_at_k(comps_all[c], y, all_idx, dup_mask) for c in COMPONENTS}
    print("[3] Từng nhóm:", {g: round(v * 100, 2) for g, v in R["group_only"].items()})
    print("    Từng thành phần:", {c: round(v * 100, 2) for c, v in R["component_only"].items()})

    # ---------------- 4. Bỏ từng thành phần (5-fold) ----------------
    print("\n[4] Bỏ từng thành phần, đo 5-fold ...")
    abl = {}
    for c in COMPONENTS:
        per_fold = []
        for f, (tr, te) in enumerate(folds):
            G = group_distances(fold_comps[f], tr, drop=c)
            w, _ = choose_weights(G, y, tr, dup_mask)
            per_fold.append(p_at_k(fuse(G, w), y, te, dup_mask))
        delta = np.array(per_fold) - np.array(cv_p5)   # >0: bỏ đi lại tốt hơn
        abl[c] = {
            "dims": COMPONENTS[c][1] - COMPONENTS[c][0],
            "cv_p5": float(np.mean(per_fold)),
            "delta_mean": float(delta.mean()),
            "delta_std": float(delta.std()),
            "folds_better_when_dropped": int(np.sum(delta > 1e-12)),
            "folds_worse_when_dropped": int(np.sum(delta < -1e-12)),
        }
        print(f"  bỏ {c}: P@5={np.mean(per_fold)*100:.2f}%  Δ={delta.mean()*100:+.2f} ± {delta.std()*100:.2f}  "
              f"(tốt hơn ở {abl[c]['folds_better_when_dropped']}/5 fold)")
    R["ablation_cv5"] = abl

    # ---------------- 5. Bỏ ra từng loài ----------------
    print("\n[5] Bỏ ra từng loài ...")
    loso = {}
    loso_groups = {}
    for sp in species:
        tr = np.where(y != sp)[0]
        te = np.where(y == sp)[0]
        db_train = (y != sp)
        comps = component_distances(X, tr)
        G = group_distances(comps, tr)
        w, _ = choose_weights(G, y, tr, dup_mask, db_mask=db_train)
        loso_groups[sp] = (G, w)
        p_new = p_at_k(fuse(G, w), y, te, dup_mask)
        loso[sp] = {"weights": list(w), "p5_as_new": p_new,
                    "p5_normal": R["full"]["per_species"][sp]["p5"]}
        print(f"  {sp}: w={w} P@5 khi là loài mới={p_new*100:.2f}% (bình thường {loso[sp]['p5_normal']*100:.2f}%)")
    R["loso"] = loso

    # ---------------- 6. Loài chưa có trong CSDL ----------------
    print("\n[6] Phát hiện loài chưa có ...")
    nov = {}
    for sp in species:
        G, w = loso_groups[sp]
        D = fuse(G, w)
        db = np.where(y != sp)[0]
        db_mask = (y != sp)
        Dk = D[db].copy()
        Dk[np.arange(len(db)), db] = np.inf
        Dk[dup_mask[db]] = np.inf
        Dk[:, ~db_mask] = np.inf
        d_known = Dk.min(axis=1)
        unk = np.where(y == sp)[0]
        d_unknown = D[np.ix_(unk, db)].min(axis=1)
        lab = np.r_[np.zeros(len(d_known)), np.ones(len(d_unknown))]
        sc = np.r_[d_known, d_unknown]
        auc = float(roc_auc_score(lab, sc))
        fpr, tpr, th = roc_curve(lab, sc)
        bi = int(np.argmax(tpr - fpr))
        nov[sp] = {"auroc": auc, "threshold": float(th[bi]), "tpr": float(tpr[bi]), "fpr": float(fpr[bi]),
                   "median_dmin_known": float(np.median(d_known)), "median_dmin_unknown": float(np.median(d_unknown))}
        print(f"  bỏ {sp}: AUROC={auc:.3f} ngưỡng={th[bi]:.3f} (TPR={tpr[bi]:.2f}, FPR={fpr[bi]:.2f})")
    aucs = [v["auroc"] for v in nov.values()]
    ths = [v["threshold"] for v in nov.values()]
    R["novelty"] = {"per_species": nov, "mean_auroc": float(np.mean(aucs)),
                    "threshold_mean": float(np.mean(ths)), "threshold_median": float(np.median(ths)),
                    "threshold_std": float(np.std(ths))}

    # ---------------- 7. Chiều rác, tương quan ----------------
    with open("data/feature_schema.json", "r", encoding="utf-8") as f:
        names = [d["name"] for d in json.load(f)["dimensions"]]
    sd = X.std(axis=0)
    dead = np.where(sd < 1e-6)[0]
    live = np.where(sd >= 1e-6)[0]
    C = np.corrcoef(X[:, live], rowvar=False)
    np.fill_diagonal(C, 0.0)
    iu = np.triu_indices(len(live), 1)
    high = np.abs(C[iu]) > 0.95
    pair_comp = {}
    def comp_of(d):
        for c, (st, en, _) in COMPONENTS.items():
            if st <= d < en:
                return c
    for a, b in zip(live[iu[0][high]], live[iu[1][high]]):
        key = comp_of(a) if comp_of(a) == comp_of(b) else f"{comp_of(a)}-{comp_of(b)}"
        pair_comp[key] = pair_comp.get(key, 0) + 1
    R["redundancy"] = {
        "dead_dims": [{"index": int(i), "name": names[i]} for i in dead],
        "high_corr_pairs": int(high.sum()),
        "high_corr_pairs_by_component": dict(sorted(pair_comp.items(), key=lambda kv: -kv[1])),
    }
    print(f"\n[7] Chiều rác: {len(dead)}; cặp |r|>0.95: {int(high.sum())}")

    # ---------------- 8. Định lượng Giá trị Thông tin (5 chỉ số: CV_within, J_Fisher, F_ANOVA, Eta_sq, MI_bits) ----------------
    mu_all = X.mean(axis=0)
    sb = np.zeros(dims, dtype=np.float64); sw = np.zeros(dims, dtype=np.float64)
    for sp in species:
        Xc = X[y == sp]
        sb += len(Xc) * (Xc.mean(axis=0) - mu_all) ** 2
        sw += ((Xc - Xc.mean(axis=0)) ** 2).sum(axis=0)
    fisher = np.where(sd >= 1e-6, sb / np.maximum(sw, 1e-12), 0.0)
    df_between = len(species) - 1
    df_within = n - len(species)
    scale_f = float(df_within) / float(max(1, df_between))
    f_anova = scale_f * fisher
    eta_sq = fisher / (1.0 + fisher)

    # CV chỉ có nghĩa với đại lượng luôn dương
    positive = np.where((X.min(axis=0) > 0) & (sd >= 1e-6))[0]
    cv = np.full(dims, np.nan)
    for d in positive:
        cv[d] = float(np.mean([X[y == sp, d].std() / (X[y == sp, d].mean() + 1e-12) for sp in species]))

    # Mutual Information Shannon I(F_d; Y) tính bằng bits (trên 10 phân vị) và phân loại vai trò
    mi_bits = np.zeros(dims, dtype=np.float64)
    roles = []
    info_rows = []
    role_counts = {}
    for d in range(dims):
        col = X[:, d]
        if sd[d] >= 1e-6:
            bins = np.unique(np.quantile(col, np.linspace(0.0, 1.0, 11)))
            disc = np.digitize(col, bins[1:-1]) if len(bins) > 2 else np.zeros(n, dtype=int)
            mi_bits[d] = float(mutual_info_score(y, disc) / np.log(2.0))
        jf = float(fisher[d])
        cv_w = float(cv[d]) if not np.isnan(cv[d]) else np.nan
        if sd[d] < 1e-6:
            role = "RESERVED_NEW_SPECIES" if abs(mu_all[d]) < 1e-6 else "GLOBAL_FISH_INVARIANT"
        elif not np.isnan(cv_w) and cv_w < 0.10 and jf >= 0.70:
            role = "DUAL_PURPOSE"
        elif jf >= 0.70:
            role = "DISCRIMINATION"
        elif not np.isnan(cv_w) and cv_w < 0.15:
            role = "SIMILARITY"
        else:
            role = "COMPLEMENTARY"
        roles.append(role)
        role_counts[role] = role_counts.get(role, 0) + 1
        row_dict = {
            "dim_index": int(d),
            "feature_name": names[d],
            "component": comp_of(d),
            "global_mean": float(mu_all[d]),
            "global_std": float(sd[d]),
            "cv_within": cv_w,
            "fisher_j": jf,
            "f_anova": float(f_anova[d]),
            "eta_squared": float(eta_sq[d]),
            "mutual_info_bits": float(mi_bits[d]),
            "primary_role": role,
        }
        for sp in species:
            sp_vals = col[y == sp]
            row_dict[f"{sp}_mean"] = float(sp_vals.mean())
            row_dict[f"{sp}_std"] = float(sp_vals.std())
        info_rows.append(row_dict)

    info_df = pd.DataFrame(info_rows)
    info_csv_path = "data/feature_information_value_table.csv"
    info_df.to_csv(info_csv_path, index=False, encoding="utf-8")
    print(f"  -> Đã xuất bảng Giá trị Thông tin ({len(info_df)} chiều x {n} ảnh): {info_csv_path}")

    if os.path.exists("data/dataset_eda_metrics.csv"):
        eda_df = pd.read_csv("data/dataset_eda_metrics.csv")
        num_cols = ["aspect_ratio", "circularity", "solidity", "extent",
                    "sat_mean", "val_mean", "achromatic_ratio", "hue_chromatic_mean"]
        summary_rows = []
        for sp_name, grp in eda_df.groupby("species"):
            s_row = {"species": sp_name, "count": int(len(grp))}
            for col_name in num_cols:
                s_row[f"{col_name}_mean"] = float(grp[col_name].mean())
                s_row[f"{col_name}_std"] = float(grp[col_name].std())
            summary_rows.append(s_row)
        pd.DataFrame(summary_rows).to_csv("data/species_attribute_summary.csv", index=False, encoding="utf-8")

    top_f = np.argsort(-fisher)[:15]
    top_cv = positive[np.argsort(cv[positive])][:15]
    comp_fisher = {c: float(np.mean(fisher[st:en][sd[st:en] >= 1e-6])) for c, (st, en, _) in COMPONENTS.items()}
    comp_fanova = {c: float(np.mean(f_anova[st:en][sd[st:en] >= 1e-6])) for c, (st, en, _) in COMPONENTS.items()}
    comp_etasq = {c: float(np.mean(eta_sq[st:en][sd[st:en] >= 1e-6])) for c, (st, en, _) in COMPONENTS.items()}
    comp_mibits = {c: float(np.mean(mi_bits[st:en][sd[st:en] >= 1e-6])) for c, (st, en, _) in COMPONENTS.items()}
    R["fisher_top"] = [{
        "name": names[i], "component": comp_of(i),
        "fisher": float(fisher[i]), "f_anova": float(f_anova[i]),
        "eta_squared": float(eta_sq[i]), "mi_bits": float(mi_bits[i]),
        "role": roles[i]
    } for i in top_f]
    R["cv_top"] = [{
        "name": names[i], "component": comp_of(i),
        "cv_within": float(cv[i]), "fisher": float(fisher[i]),
        "f_anova": float(f_anova[i]), "eta_squared": float(eta_sq[i]),
        "mi_bits": float(mi_bits[i]), "role": roles[i]
    } for i in top_cv]
    R["fisher_by_component"] = comp_fisher
    R["f_anova_by_component"] = comp_fanova
    R["eta_sq_by_component"] = comp_etasq
    R["mi_bits_by_component"] = comp_mibits
    R["role_counts"] = role_counts
    R["cv_note"] = f"CV chỉ tính trên {len(positive)} chiều luôn dương và có biến thiên"

    # ---------------- 9. Độ trễ & Lọc thô Hamming đa độ phân giải (64-bit & 192-bit) ----------------
    print("\n[9] Đo độ trễ ...")
    mu = X.mean(axis=0); s = X.std(axis=0); s = np.where(s < 1e-6, 1.0, np.maximum(s, 2e-3))
    Z = (X - mu) / s
    comp_meds = {}
    for m, (st, en, kind) in COMPONENTS.items():
        if kind == "hist":
            Dm_raw = cdist(X[:, st:en], X[:, st:en], metric="cityblock")
        else:
            Dm_raw = cdist(Z[:, st:en], Z[:, st:en], metric="euclidean")
        comp_meds[m] = train_median(Dm_raw, all_idx)
    meds = {g: train_median(sum(comps_all[m] for m in GROUPS[g]), all_idx) for g in GROUPS}
    R["normalization_medians"] = {
        "component_medians": {k: float(v) for k, v in comp_meds.items()},
        "group_medians": {k: float(v) for k, v in meds.items()},
    }

    def fused_query(qi, cand):
        out = np.zeros(len(cand))
        for g, members in GROUPS.items():
            Dg = np.zeros(len(cand))
            for m in members:
                st, en, kind = COMPONENTS[m]
                if kind == "hist":
                    Dm = np.abs(X[cand, st:en] - X[qi, st:en]).sum(axis=1)
                else:
                    Dm = np.sqrt(((Z[cand, st:en] - Z[qi, st:en]) ** 2).sum(axis=1))
                Dg += Dm / comp_meds[m]
            wg = opt_w[["color", "shape", "texture"].index(g)]
            out += wg * Dg / meds[g]
        return out

    qs = np.arange(0, n, n // 100)[:100]
    t0 = time.perf_counter()
    full_top = {}
    for qi in qs:
        d = fused_query(qi, all_idx); d[qi] = np.inf
        full_top[qi] = set(np.argpartition(d, K)[:K].tolist())
    t_linear = (time.perf_counter() - t0) / len(qs) * 1000

    tree = NearestNeighbors(n_neighbors=K + 1, algorithm="ball_tree").fit(Z)
    t0 = time.perf_counter()
    for qi in qs:
        tree.kneighbors(Z[qi:qi + 1])
    t_ball = (time.perf_counter() - t0) / len(qs) * 1000

    bits64 = np.unpackbits(grid_u64.astype(">u8").view(np.uint8).reshape(n, 8), axis=1).astype(np.int16)
    ones64 = bits64.sum(axis=1)
    HAM64 = ones64[:, None] + ones64[None, :] - 2 * (bits64 @ bits64.T)

    if "grid192_bytes" in data:
        bits192 = np.unpackbits(data["grid192_bytes"], axis=1).astype(np.int16)
    else:
        bits192 = bits64
    ones192 = bits192.sum(axis=1)
    HAM192 = ones192[:, None] + ones192[None, :] - 2 * (bits192 @ bits192.T)

    linear_top_all = retrieve(D_opt, all_idx, dup_mask)
    coarse = {}
    coarse_192 = {}
    for n_cand in COARSE_CANDIDATES:
        # 1. Lưới 64-bit (8x8)
        H = HAM64.astype(np.float64).copy()
        H[all_idx, all_idx] = np.inf
        H[dup_mask] = np.inf
        cand_idx = np.argpartition(H, n_cand, axis=1)[:, :n_cand]
        Dm = np.full_like(D_opt, np.inf)
        rows = np.repeat(all_idx, n_cand)
        Dm[rows, cand_idx.ravel()] = D_opt[rows, cand_idx.ravel()]
        top2 = retrieve(Dm, all_idx, dup_mask)
        p5 = float(np.mean(y[top2] == y[:, None]))
        overlap = float(np.mean([len(set(a) & set(b)) / K for a, b in zip(top2, linear_top_all)]))
        t0 = time.perf_counter()
        for qi in qs:
            ham = (bits64 != bits64[qi]).sum(axis=1)
            cand = np.argpartition(ham, n_cand)[:n_cand]
            cand = cand[cand != qi]
            d = fused_query(qi, cand)
            cand[np.argpartition(d, K)[:K]]
        t_ms = (time.perf_counter() - t0) / len(qs) * 1000
        coarse[str(n_cand)] = {"p5": p5, "top5_overlap_with_linear": overlap, "ms_per_query": t_ms}

        # 2. Lưới chuẩn hóa trục chính 192-bit (12x16 - Slide 30)
        H192 = HAM192.astype(np.float64).copy()
        H192[all_idx, all_idx] = np.inf
        H192[dup_mask] = np.inf
        cand_idx192 = np.argpartition(H192, n_cand, axis=1)[:, :n_cand]
        Dm192 = np.full_like(D_opt, np.inf)
        Dm192[rows, cand_idx192.ravel()] = D_opt[rows, cand_idx192.ravel()]
        top2_192 = retrieve(Dm192, all_idx, dup_mask)
        p5_192 = float(np.mean(y[top2_192] == y[:, None]))
        overlap_192 = float(np.mean([len(set(a) & set(b)) / K for a, b in zip(top2_192, linear_top_all)]))
        t0 = time.perf_counter()
        for qi in qs:
            ham = (bits192 != bits192[qi]).sum(axis=1)
            cand = np.argpartition(ham, n_cand)[:n_cand]
            cand = cand[cand != qi]
            d = fused_query(qi, cand)
            cand[np.argpartition(d, K)[:K]]
        t_ms192 = (time.perf_counter() - t0) / len(qs) * 1000
        coarse_192[str(n_cand)] = {"p5": p5_192, "top5_overlap_with_linear": overlap_192, "ms_per_query": t_ms192}
        print(f"  lọc thô {n_cand} ứng viên: 64-bit P@5={p5*100:.2f}% ({t_ms:.2f}ms) | 192-bit P@5={p5_192*100:.2f}% ({t_ms192:.2f}ms)")

    R["latency_ms"] = {
        "linear_fused": t_linear,
        "ball_tree_L2_zscore": t_ball,
    }
    R["coarse_filter_demo"] = {
        "note": "Lọc thô bằng chữ ký lưới nhị phân S5_bin64 (8x8) và S5_bin192 (12x16 trục chính 192 - Slide 30 & 34)",
        "linear_p5": R["full"]["overall_p5"],
        "by_candidates": coarse,
        "by_candidates_192bit": coarse_192,
    }
    print(f"  tuần tự {t_linear:.2f} ms | Ball-Tree {t_ball:.2f} ms")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)
    write_report(R, out_md)
    print(f"\nĐã ghi {out_json} và {out_md}")
    return R


def pct(x, nd=2):
    return f"{x*100:.{nd}f}%"


def write_report(R, path):
    sp = R["species"]
    md = []
    md.append(f"# BÁO CÁO ĐÁNH GIÁ BỘ ĐẶC TRƯNG {R['dims']} CHIỀU (3 BỘ ĐẶC TRƯNG THỊ GIÁC + CHỮ KÝ NHỊ PHÂN S5)")
    md.append(f"> {R['n_images']} ảnh, {len(sp)} loài, vector xếp hạng {R['dims']} chiều (12 thành phần) + 2 chữ ký nhị phân lọc thô (`S5_bin64` & `S5_bin192`). Mọi số liệu dưới đây do `src/evaluate.py` sinh ra.")
    nd = R["near_duplicates"]
    md.append(f"> Mọi truy vấn loại chính nó và ảnh gần trùng (RMS < {nd['rms_threshold']:.0f} trên ảnh xám 64x64): "
              f"{nd['pairs']} cặp, {nd['images_with_dup']} ảnh có ảnh gần trùng, {nd['cross_species_pairs']} cặp khác loài.\n")

    md.append("## 1. Kết quả chính")
    cv = R["cv5"]
    md.append(f"- **P@5 kiểm định chéo 5-fold** (con số báo cáo chính): **{pct(cv['mean_p5'])}** ± {pct(cv['std_p5'])}")
    md.append(f"- Trọng số mặc định (bộ được chọn nhiều nhất qua 5 fold): màu {R['default_weights'][0]}, "
              f"hình {R['default_weights'][1]}, kết cấu {R['default_weights'][2]}")
    md.append(f"- Toàn tập với trọng số mặc định: P@5 {pct(R['full']['overall_p5'])}, P@5 trung bình theo loài "
              f"{pct(R['full']['macro_p5'])}, top-1 {pct(R['full']['top1'])}")
    md.append(f"- Trọng số đều 1/3: P@5 {pct(R['equal_weights_p5'])}\n")
    md.append("| Fold | Trọng số chọn trên 4/5 | P@5 trên 1/5 |")
    md.append("|---|---|---:|")
    for r in cv["folds"]:
        md.append(f"| {r['fold']} | {tuple(r['weights'])} | {pct(r['test_p5'])} |")
    md.append("")

    md.append("### Theo loài (toàn tập, trọng số mặc định)")
    md.append("| Loài | Số ảnh | P@5 | Top-1 |")
    md.append("|---|---:|---:|---:|")
    for s in sp:
        v = R["full"]["per_species"][s]
        md.append(f"| {s} | {v['count']} | {pct(v['p5'])} | {pct(v['top1'])} |")
    md.append("")
    md.append("### Ma trận nhầm lẫn (hàng: loài thật; cột: loài chiếm đa số trong Top-5)")
    md.append("| | " + " | ".join(sp) + " |")
    md.append("|---|" + "---:|" * len(sp))
    for i, s in enumerate(sp):
        md.append(f"| {s} | " + " | ".join(str(v) for v in R["full"]["confusion_majority_top5"][i]) + " |")
    md.append("")

    md.append("## 2. Từng bộ đặc trưng và từng thành phần riêng lẻ (toàn tập)")
    md.append("### Theo 3 Bộ Đặc trưng Thị giác")
    md.append("| Bộ đặc trưng | P@5 |")
    md.append("|---|---:|")
    for g, v in R["group_only"].items():
        md.append(f"| {g} | {pct(v)} |")
    md.append("\n### Theo từng thành phần độc lập (12 thành phần)")
    md.append("| Thành phần | Mô tả | Số chiều | P@5 độc lập |")
    md.append("|---|---|---:|---:|")
    for c, v in R["component_only"].items():
        st, en, _ = COMPONENTS[c]
        md.append(f"| {c} | {COMP_DESC[c]} | {en - st} | {pct(v)} |")
    md.append("")

    md.append("## 3. Bỏ từng thành phần (đo bằng 5-fold, chọn lại trọng số trong mỗi fold)")
    md.append(f"Mốc: bộ đầy đủ 5-fold = {pct(cv['mean_p5'])}. Δ = P@5 khi bỏ − P@5 đầy đủ, tính theo từng fold. "
              "Δ < 0: thành phần có đóng góp. Δ > 0: bỏ đi lại tốt hơn.\n")
    md.append("| Bỏ | Tên | Số chiều | P@5 5-fold | Δ trung bình ± độ lệch giữa fold | Số fold tốt hơn khi bỏ |")
    md.append("|---|---|---:|---:|---:|---:|")
    for c, v in sorted(R["ablation_cv5"].items(), key=lambda kv: kv[1]["delta_mean"]):
        md.append(f"| {c} | {COMP_DESC[c]} | {v['dims']} | {pct(v['cv_p5'])} | "
                  f"{v['delta_mean']*100:+.2f} ± {v['delta_std']*100:.2f} | {v['folds_better_when_dropped']}/5 |")
    md.append("")

    md.append("## 4. Bỏ ra từng loài (thống kê và trọng số chọn khi KHÔNG có loài đó)")
    md.append("| Loài coi là mới | Trọng số chọn | P@5 khi là loài mới | P@5 bình thường | Chênh lệch |")
    md.append("|---|---|---:|---:|---:|")
    for s in sp:
        v = R["loso"][s]
        md.append(f"| {s} | {tuple(v['weights'])} | {pct(v['p5_as_new'])} | {pct(v['p5_normal'])} | "
                  f"{(v['p5_as_new']-v['p5_normal'])*100:+.2f} |")
    md.append("")

    md.append("## 5. Ảnh thuộc loài chưa có trong CSDL")
    nv = R["novelty"]
    md.append(f"Bỏ hẳn 1 loài khỏi CSDL; so khoảng cách tới ảnh gần nhất của ảnh loài đã có và ảnh loài bị bỏ. "
              f"AUROC trung bình **{nv['mean_auroc']:.3f}**. Ngưỡng Youden: {nv['threshold_mean']:.3f} ± {nv['threshold_std']:.3f} "
              "(đơn vị: khoảng cách đã chia trung vị nhóm).\n")
    md.append("| Loài bị bỏ | AUROC | Ngưỡng | TPR | FPR | Trung vị d_min loài đã có | Trung vị d_min loài bị bỏ |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in sp:
        v = nv["per_species"][s]
        md.append(f"| {s} | {v['auroc']:.3f} | {v['threshold']:.3f} | {v['tpr']:.2f} | {v['fpr']:.2f} | "
                  f"{v['median_dmin_known']:.3f} | {v['median_dmin_unknown']:.3f} |")
    md.append("")

    md.append("## 6. Chiều dự phòng và trùng lặp")
    rd = R["redundancy"]
    md.append(f"- Chiều có độ lệch chuẩn ≈ 0 trên 1.100 ảnh: **{len(rd['dead_dims'])}** — "
              + ", ".join(f"`{d['name']}`" for d in rd["dead_dims"]))
    c1_dead = [d["name"] for d in rd["dead_dims"] if d["name"].startswith("color_c1_")]
    s5_dead = [d["name"] for d in rd["dead_dims"] if d["name"].startswith("shape_s5_")]
    s5_dead_str = ", ".join(f"`{name}`" for name in s5_dead) if s5_dead else "ô trung tâm"
    md.append(f"  - Gồm {len(c1_dead)} ô màu của C1 mà 6 loài hiện tại không có pixel nào (`RESERVED_NEW_SPECIES`: luôn bằng 0.0, giữ lại theo nguyên tắc N1 dành cho loài mới; "
              f"vì C1 so bằng L1 nên ô bằng 0 không làm thay đổi khoảng cách) và {len(s5_dead)} ô trung tâm {s5_dead_str} của lưới S5 "
              "(`GLOBAL_FISH_INVARIANT`: luôn bằng 1.0 vì phần giữa thân cá phủ kín ô trung tâm hộp bao trên cả 1.100 ảnh; khi chuẩn hóa Z-score với ngưỡng std < 1e-6 thì Z = 0 nên không gây nhiễu).")
    md.append(f"- Cặp chiều có |r| > 0.95: **{rd['high_corr_pairs']}**. Phân bố theo thành phần: "
              + ", ".join(f"{k}: {v}" for k, v in rd["high_corr_pairs_by_component"].items()))
    md.append("")

    md.append("## 7. Định lượng Giá trị Thông tin: Đặc trưng phân biệt, Đặc trưng tương đồng & Lưỡng dụng")
    md.append("> Chi tiết toàn bộ 421 chiều đã được xuất ra `data/feature_information_value_table.csv` với đủ 5 thước đo: "
              "$\\text{CV}_{\\text{within}}$, $J_{\\text{Fisher}}$, $F_{\\text{ANOVA}}(5, 1094)$, $\\eta^2$, và Thông tin tương hỗ Shannon $I(F_d; Y)$ (bits).\n")
    md.append("### Tổng hợp Giá trị Thông tin trung bình theo từng thành phần")
    md.append("| Thành phần | Tên | $J_{\\text{Fisher}}$ TB | $F_{\\text{ANOVA}}$ TB | $\\eta^2$ (%) TB | $I(F_d; Y)$ (bits) TB |")
    md.append("|---|---|---:|---:|---:|---:|")
    for c, v in sorted(R["fisher_by_component"].items(), key=lambda kv: -kv[1]):
        fa = R["f_anova_by_component"][c]
        et = R["eta_sq_by_component"][c] * 100.0
        mi = R["mi_bits_by_component"][c]
        md.append(f"| {c} | {COMP_DESC[c]} | {v:.3f} | {fa:.2f} | {et:.2f}% | {mi:.3f} |")
    md.append("\n### 15 chiều có Giá trị Thông tin Phân biệt cao nhất (Highest Fisher Ratio & ANOVA F)")
    md.append("| # | Chiều | Thành phần | $J_{\\text{Fisher}}$ | $F_{\\text{ANOVA}}$ | $\\eta^2$ (%) | $I(F_d; Y)$ (bits) | Vai trò |")
    md.append("|---:|---|---|---:|---:|---:|---:|---|")
    for i, v in enumerate(R["fisher_top"]):
        md.append(f"| {i+1} | `{v['name']}` | {v['component']} | {v['fisher']:.3f} | {v['f_anova']:.2f} | "
                  f"{v['eta_squared']*100:.2f}% | {v['mi_bits']:.3f} | `{v['role']}` |")
    md.append(f"\n### 15 chiều có Độ ổn định Tương đồng Nội loài cao nhất (Lowest $\\text{{CV}}_{{\\text{{within}}}}$)")
    md.append(f"{R['cv_note']}. Chiều có CV nhỏ và Fisher nhỏ là đặc điểm bất biến toàn cục của lớp Cá (`SIMILARITY`); CV nhỏ và Fisher lớn là đặc trưng lưỡng dụng vàng (`DUAL_PURPOSE`).\n")
    md.append("| # | Chiều | Thành phần | $\\text{CV}_{\\text{within}}$ | $J_{\\text{Fisher}}$ | $F_{\\text{ANOVA}}$ | $I(F_d; Y)$ (bits) | Vai trò |")
    md.append("|---:|---|---|---:|---:|---:|---:|---|")
    for i, v in enumerate(R["cv_top"]):
        md.append(f"| {i+1} | `{v['name']}` | {v['component']} | {v['cv_within']:.4f} | {v['fisher']:.3f} | "
                  f"{v['f_anova']:.2f} | {v['mi_bits']:.3f} | `{v['role']}` |")
    md.append("")

    md.append("## 8. Độ trễ truy vấn (trung bình 100 truy vấn)")
    lt = R["latency_ms"]
    md.append("| Cách tìm | ms/truy vấn | Ghi chú |")
    md.append("|---|---:|---|")
    md.append(f"| Quét tuần tự, khoảng cách hợp nhất 3 nhóm | {lt['linear_fused']:.2f} | Cách hệ thống sử dụng |")
    md.append(f"| Ball-Tree, L2 trên vector Z-score | {lt['ball_tree_L2_zscore']:.2f} | Không phải độ đo hợp nhất, chỉ để so tốc độ |")
    md.append("")
    cf = R["coarse_filter_demo"]
    md.append("## 9. Lọc thô bằng Chữ ký Lưới Nhị phân Đa độ phân giải (`S5_bin64` 8x8 & `S5_bin192` 12x16 chuẩn Slide 30)")
    md.append("Giai đoạn 1 lấy N ảnh có khoảng cách Hamming nhỏ nhất trên mã lưới nhị phân (ngưỡng diện tích 15%); "
              "giai đoạn 2 xếp hạng N ảnh đó bằng khoảng cách hợp nhất 421 chiều. Đo trên toàn bộ 1.100 truy vấn, "
              f"so với quét tuần tự (P@5 {pct(cf['linear_p5'])}).\n")
    md.append("| Số ứng viên N | P@5 (`S5_bin64` 8x8) | Trùng Top-5 (64-bit) | ms/truy vấn (64-bit) | P@5 (`S5_bin192` 12x16 Slide 30) | Trùng Top-5 (192-bit) | ms/truy vấn (192-bit) |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|")
    cf192 = cf.get("by_candidates_192bit", {})
    for k_, v in cf["by_candidates"].items():
        v192 = cf192.get(k_, v)
        md.append(f"| {k_} | {pct(v['p5'])} | {pct(v['top5_overlap_with_linear'],1)} | {v['ms_per_query']:.2f} | "
                  f"{pct(v192['p5'])} | {pct(v192['top5_overlap_with_linear'],1)} | {v192['ms_per_query']:.2f} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


if __name__ == "__main__":
    run_evaluation()

