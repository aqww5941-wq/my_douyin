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
AUDIO_EXTS = {'.mp3', '.m4a', '.aac', '.wav', '.ogg', '.flac'}

# ========================
# 全局缓存
# ========================
FILE_CACHE = {
    "recommend_videos": [],  # 推荐: normal + douyin + x
    "normal_videos": [],     # normal -> 抖音
    "tiktok_videos": [],     # douyin -> TikTok
    "x_videos": [],          # x
    "x_images": [],          # 图片
    "asmr_audios": [],       # ASMR
    "liked": set(),
    "last_scan_time": 0
}

class DeleteRequest(BaseModel):
    path: str

class LikeRequest(BaseModel):
    path: str


def iter_asmr_files():
    asmr_dir = CONTENT_DIR / "x" / "asmr"
    if not asmr_dir.exists():
        return []

    items = []
    for root, _, files in os.walk(asmr_dir):
        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()
            if ext in AUDIO_EXTS or ext in VIDEO_EXTS:
                rel_str = str(file_path.relative_to(CONTENT_DIR)).replace("\\", "/")
                items.append(rel_str)
    return sorted(items)

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
                    if "douyin/" in lower:
                        FILE_CACHE["normal_videos"].append(rel_str)
                    if "tiktok/" in lower:
                        FILE_CACHE["tiktok_videos"].append(rel_str)
                    if "x/videos" in lower:
                        FILE_CACHE["x_videos"].append(rel_str)
                    if "x/asmr/" in lower:
                        FILE_CACHE["asmr_audios"].append(rel_str)
                    total += 1

                elif ext in AUDIO_EXTS:
                    if "x/asmr/" in lower:
                        FILE_CACHE["asmr_audios"].append(rel_str)
                    total += 1

                elif ext in IMAGE_EXTS:
                    if "x/images" in lower:
                        FILE_CACHE["x_images"].append(rel_str)
                    total += 1

            except Exception as e:
                print(f"文件处理错误: {file} - {e}")

    # 随机打乱
    for k in FILE_CACHE:
        if isinstance(FILE_CACHE[k], list):
            random.shuffle(FILE_CACHE[k])

    FILE_CACHE["recommend_videos"] = (
        FILE_CACHE["normal_videos"] + FILE_CACHE["tiktok_videos"] + FILE_CACHE["x_videos"]
    )
    random.shuffle(FILE_CACHE["recommend_videos"])
    FILE_CACHE["last_scan_time"] = time.time()
    print(
        f"扫描完成: Total={total}, 推荐={len(FILE_CACHE['recommend_videos'])}, "
        f"抖音={len(FILE_CACHE['normal_videos'])}, TikTok={len(FILE_CACHE['tiktok_videos'])}, "
        f"x={len(FILE_CACHE['x_videos'])}, 图={len(FILE_CACHE['x_images'])}, asmr={len(FILE_CACHE['asmr_audios'])}"
    )

scan_all_media_files()

# ========================
# 工具函数
# ========================

def get_tab_files(tab: str):
    if tab == "recommend":
        return FILE_CACHE["recommend_videos"]
    elif tab == "douyin":
        return FILE_CACHE["normal_videos"]
    elif tab == "tiktok":
        return FILE_CACHE["tiktok_videos"]
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

@app.post("/api/unlike")
async def unlike_file(req: LikeRequest):
    FILE_CACHE["liked"].discard(req.path.replace("\\", "/"))
    return {"status": "success"}

@app.get("/api/asmr/list")
async def asmr_list():
    files = iter_asmr_files()
    items = [{"src": f"/media/{p}", "raw_path": p} for p in files]
    return {"items": items}

@app.get("/api/asmr/random")
async def random_asmr():
    files = iter_asmr_files()
    if not files:
        return {"src": "", "raw_path": ""}
    p = random.choice(files)
    return {"src": f"/media/{p}", "raw_path": p}

@app.post("/api/delete")
async def delete_file(req: DeleteRequest):
    rel = req.path.replace("\\", "/").strip("/")
    target = (CONTENT_DIR / rel).resolve()
    base = CONTENT_DIR.resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    target.unlink()
    scan_all_media_files()
    FILE_CACHE["liked"].discard(rel)
    return {"status": "success", "deleted": rel}

@app.get("/api/rescan")
async def rescan():
    scan_all_media_files()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
