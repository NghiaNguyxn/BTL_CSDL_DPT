# -*- coding: utf-8 -*-
"""
Backend API (FastAPI) cho Hệ thống CSDL Lưu trữ và Tìm kiếm Ảnh Cá Dựa trên Nội dung (Fish CBIR System):
- Tách biệt tầng dịch vụ truy vấn CBIR (src/search_engine.py) và tầng điều phối HTTP REST API.
- Phục vụ giao diện Web Demo trực quan (Phần 3, Phần 4 & Phần 5) tại http://127.0.0.1:8000
"""

import os
import sys
import json
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from src.search_engine import FishCBIRSearchEngine

app = FastAPI(
    title="Hệ CSDL Lưu Trữ & Tìm Kiếm Ảnh Cá Dựa Trên Nội Dung (Fish CBIR System)",
    description="BTL Hệ Cơ Sở Dữ Liệu Đa Phương Tiện - PTIT (GVHD: TS. Nguyễn Đình Hóa)",
    version="1.0.0",
)

# Mount thư mục ảnh chuẩn hóa để trình duyệt hiển thị trực tiếp
for folder_name in ["dataset_gold_v3", "data"]:
    folder_path = os.path.join(ROOT_DIR, folder_name)
    if os.path.isdir(folder_path):
        app.mount(f"/{folder_name}", StaticFiles(directory=folder_path), name=folder_name)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Khởi tạo Singleton CBIR Search Engine kết nối CSDL SQLite
engine = FishCBIRSearchEngine(
    db_path=os.path.join(ROOT_DIR, "data", "fish_multimedia.db"),
    index_path=os.path.join(ROOT_DIR, "data", "ball_tree_index.pkl"),
)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    html_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h3>Chưa tìm thấy file giao diện src/static/index.html</h3>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/db-info")
async def get_db_info():
    """Trả về thông tin tổng quan 6 bảng CSDL SQLite, danh sách mẫu thử nhanh và kết quả đánh giá."""
    summary = engine.get_db_summary()

    # Lấy mỗi loài 4 ảnh tiêu biểu để người dùng có thể chọn thử nhanh 1-click trên giao diện Demo
    quick_samples = {}
    for rec in engine.records:
        sp = rec["species"]
        if sp not in quick_samples:
            quick_samples[sp] = []
        if len(quick_samples[sp]) < 4:
            quick_samples[sp].append(
                {
                    "image_id": rec["image_id"],
                    "species": sp,
                    "species_vi": rec["species_vi"],
                    "file_name": rec["file_name"],
                    "file_path": "/" + rec["file_path"].lstrip("/"),
                    "black_file_path": "/" + rec["black_file_path"].lstrip("/"),
                }
            )

    eval_data = {}
    eval_path = os.path.join(ROOT_DIR, "data", "evaluation_results.json")
    if os.path.exists(eval_path):
        with open(eval_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

    sql_ddl = ""
    ddl_path = os.path.join(ROOT_DIR, "data", "sql_mmdb_schema.sql")
    if os.path.exists(ddl_path):
        with open(ddl_path, "r", encoding="utf-8") as f:
            sql_ddl = f.read()

    return JSONResponse(
        {
            "db_summary": summary,
            "quick_samples": quick_samples,
            "evaluation_results": eval_data,
            "sql_ddl": sql_ddl,
        }
    )


@app.get("/api/db-table")
async def get_db_table(
    table: str = Query("Fish_Metadata", description="Tên bảng trong SQLite"),
    limit: int = Query(20, ge=1, le=200),
    species: str = Query(None, description="Lọc theo loài cá (tùy chọn)"),
):
    """Truy vấn trực tiếp các bản ghi trong 6 bảng của data/fish_multimedia.db (Phần 3)."""
    try:
        rows = engine.get_table_preview(table_name=table, limit=limit, species_filter=species)
        return JSONResponse({"table": table, "count": len(rows), "rows": rows})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/search")
async def search_fish(
    file: UploadFile = File(None),
    sample_image_id: str = Form(None),
    top_k: int = Form(5),
    metric_mode: str = Form("hybrid_2level"),
    w_color: float = Form(0.5),
    w_shape: float = Form(0.3),
    w_texture: float = Form(0.2),
    coarse_filter_mode: str = Form("none"),
    coarse_candidates: int = Form(200),
    use_quadratic_color: bool = Form(False),
    exclude_exact_self: bool = Form(False),
    diversify_top_k: bool = Form(True),
    simulate_unknown_species: str = Form(""),
):
    """
    Endpoint tìm kiếm Top-K ảnh cá tương đồng nhất:
    - Nhận file ảnh upload mới HOẶC mã `sample_image_id` chọn nhanh từ CSDL.
    - Trả về Top-5 ảnh giống nhất kèm toàn bộ Kết quả Trung gian (Intermediate Results).
    """
    try:
        sim_sp = simulate_unknown_species.strip() if simulate_unknown_species else None
        weights = (float(w_color), float(w_shape), float(w_texture))

        if file is not None and file.filename:
            raw_bytes = await file.read()
            np_arr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("File tải lên không phải là định dạng ảnh hợp lệ.")
            result = engine.search(
                img_bgra_or_bgr=img,
                query_label_name=file.filename,
                top_k=int(top_k),
                metric_mode=metric_mode,
                weights=weights,
                coarse_filter_mode=coarse_filter_mode,
                coarse_candidates=int(coarse_candidates),
                use_quadratic_color=bool(use_quadratic_color),
                exclude_exact_self=bool(exclude_exact_self),
                diversify_top_k=bool(diversify_top_k),
                simulate_unknown_species=sim_sp,
            )
        elif sample_image_id:
            result = engine.query_by_id(
                image_id=sample_image_id.strip(),
                top_k=int(top_k),
                metric_mode=metric_mode,
                weights=weights,
                coarse_filter_mode=coarse_filter_mode,
                coarse_candidates=int(coarse_candidates),
                use_quadratic_color=bool(use_quadratic_color),
                exclude_exact_self=bool(exclude_exact_self),
                diversify_top_k=bool(diversify_top_k),
                simulate_unknown_species=sim_sp,
            )
        else:
            raise ValueError("Vui lòng tải lên một bức ảnh cá hoặc chọn một ảnh mẫu để truy vấn.")

        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    print("=" * 75)
    print("KHỞI ĐỘNG WEB DEMO HỆ CSDL TÌM KIẾM ẢNH CÁ (FISH CBIR SYSTEM)")
    print("Truy cập giao diện tại: http://127.0.0.1:8000")
    print("=" * 75)
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=False)
