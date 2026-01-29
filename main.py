import os
import random
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import time

app = FastAPI()

# ========================
# 基础配置
# ========================
CONTENT_DIR = Path("/app/content")
app.mount("/media", StaticFiles(directory=str(CONTENT_DIR)), name="media")
templates = Jinja2Templates(directory="templates")

VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.avi', '.mkv', '.flv', '.m4v', '.wmv'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}

# ========================
# 全局缓存
# ========================
FILE_CACHE = {
    "all_videos": [],      # M号区: 所有视频
    "douyin_videos": [],   # M号区: 抖音
    "x_videos": [],        # M号区: X
    "x_images": [],        # M号区: 图片
    "asmr_audios": [],     # M号区: ASMR
    "normal_videos": [],   # N号区: 专属视频池
    "liked": set(),
    "last_scan_time": 0
}

class DeleteRequest(BaseModel):
    path: str

class LikeRequest(BaseModel):
    path: str

# ========================
# 扫描逻辑 (核心修改)
# ========================

def scan_all_media_files():
    print(f"开始扫描媒体文件: {CONTENT_DIR}")
    for key in FILE_CACHE:
        if isinstance(FILE_CACHE[key], list):
            FILE_CACHE[key] = []

    scanned = set()
    total = 0

    for root, _, files in os.walk(CONTENT_DIR):
        for file in files:
            file_path = Path(root) / file
            try:
                rel_path = file_path.relative_to(CONTENT_DIR)
                rel_str = str(rel_path).replace("\\", "/")
                lower = rel_str.lower()

                if rel_str in scanned: continue
                scanned.add(rel_str)

                ext = file_path.suffix.lower()

                if ext in VIDEO_EXTS:
                    # --- 区域划分逻辑 ---
                    if "normal/" in lower:
                        # 只要路径包含 normal/ 就进 N号区
                        FILE_CACHE["normal_videos"].append(rel_str)
                    else:
                        # 其他全部进 M号区
                        FILE_CACHE["all_videos"].append(rel_str)
                        if "douyin" in lower:
                            FILE_CACHE["douyin_videos"].append(rel_str)
                        elif "x/video" in lower:
                            FILE_CACHE["x_videos"].append(rel_str)
                        if "x/asmr/" in lower:
                            FILE_CACHE["asmr_audios"].append(rel_str)
                    total += 1

                elif ext in IMAGE_EXTS:
                    if "x/image" in lower or "x/images" in lower:
                        FILE_CACHE["x_images"].append(rel_str)
                    total += 1

            except Exception as e:
                print(f"文件处理错误: {file} - {e}")

    # 随机打乱
    for k in FILE_CACHE:
        if isinstance(FILE_CACHE[k], list):
            random.shuffle(FILE_CACHE[k])

    FILE_CACHE["last_scan_time"] = time.time()
    print(f"扫描完成: Total={total}, M区={len(FILE_CACHE['all_videos'])}, N区={len(FILE_CACHE['normal_videos'])}")

scan_all_media_files()

# ========================
# 工具函数
# ========================

def get_tab_files(tab: str):
    if tab == "normal":        # N号区请求
        return FILE_CACHE["normal_videos"]
    elif tab == "recommend":   # M号区默认
        return FILE_CACHE["all_videos"]
    elif tab == "douyin":
        return FILE_CACHE["douyin_videos"]
    elif tab == "x":
        return FILE_CACHE["x_videos"]
    elif tab == "images":
        return FILE_CACHE["x_images"]
    elif tab == "likes":
        return [p for p in FILE_CACHE["liked"] if (CONTENT_DIR / p).exists()][::-1]
    else:
        return []

# ========================
# 接口
# ========================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/list")
async def get_media_list(tab: str, page: int = 1, size: int = 30, seed: int = 0):
    if time.time() - FILE_CACHE["last_scan_time"] > 300:
        scan_all_media_files()

    files_source = get_tab_files(tab)
    total = len(files_source)
    
    if total == 0:
        return {"items": [], "page": page, "has_more": False, "total": 0}

    start = (page - 1) * size
    end = start + size

    if seed != 0 and tab != "likes":
        rng = random.Random(seed)
        indices = list(range(total))
        rng.shuffle(indices)
        page_files = [files_source[i] for i in indices[start:end]]
    else:
        page_files = files_source[start:end]

    items = []
    for p in page_files:
        ext = Path(p).suffix.lower()
        items.append({
            "src": f"/media/{p}",
            "raw_path": p,
            "type": "image" if ext in IMAGE_EXTS else "video"
        })

    return {"items": items, "page": page, "has_more": end < total, "total": total}

# ... 其余 delete/like/stats 接口保持不变 ...
@app.post("/api/like")
async def like_file(req: LikeRequest):
    FILE_CACHE["liked"].add(req.path.replace("\\", "/"))
    return {"status": "success"}

@app.get("/api/rescan")
async def rescan():
    scan_all_media_files()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)