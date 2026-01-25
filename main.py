# main.py
import os
import random
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# 容器内资源挂载路径
CONTENT_DIR = Path("/app/content")

# 挂载静态文件
app.mount("/media", StaticFiles(directory=str(CONTENT_DIR)), name="media")

templates = Jinja2Templates(directory="templates")

# 支持的文件扩展名
VIDEO_EXTS = {'.mp4', '.mov', '.webm'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# 内存缓存
CACHE = {
    "douyin": [],
    "x_video": [],
    "x_image": [],
    "recommend": []
}

class DeleteRequest(BaseModel):
    path: str

def scan_files():
    """扫描目录并更新缓存"""
    print("正在扫描媒体文件...")
    
    douyin_videos = []
    douyin_path = CONTENT_DIR / "douyin" / "videos"
    if douyin_path.exists():
        for root, _, files in os.walk(douyin_path):
            for file in files:
                if Path(file).suffix.lower() in VIDEO_EXTS:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    douyin_videos.append(str(rel_path))
    
    x_videos = []
    x_vid_path = CONTENT_DIR / "x" / "videos"
    if x_vid_path.exists():
        for root, _, files in os.walk(x_vid_path):
            for file in files:
                if Path(file).suffix.lower() in VIDEO_EXTS:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    x_videos.append(str(rel_path))

    x_images = []
    x_img_path = CONTENT_DIR / "x" / "images"
    if x_img_path.exists():
        for root, _, files in os.walk(x_img_path):
            for file in files:
                if Path(file).suffix.lower() in IMAGE_EXTS:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    x_images.append(str(rel_path))

    CACHE["douyin"] = douyin_videos
    CACHE["x_video"] = x_videos
    CACHE["x_image"] = x_images
    
    recommend = douyin_videos + x_videos
    CACHE["recommend"] = recommend
    
    print(f"扫描完成: 抖音视频 {len(douyin_videos)}, X视频 {len(x_videos)}, X图片 {len(x_images)}")

scan_files()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/list")
async def get_media_list(tab: str, page: int = 1, size: int = 10, seed: int = 0):
    key_map = {
        "recommend": "recommend",
        "douyin": "douyin",
        "x": "x_video",
        "images": "x_image"
    }
    
    target_key = key_map.get(tab, "recommend")
    source_list = CACHE.get(target_key, [])
    current_list = source_list[:]
    
    if seed != 0:
        random.Random(seed).shuffle(current_list)
    
    total = len(current_list)
    start = (page - 1) * size
    end = start + size
    items = current_list[start:end]
    
    media_type = 'image' if target_key == 'x_image' else 'video'
    
    result = []
    for path in items:
        result.append({
            "src": f"/media/{path}",
            "raw_path": path,  # 增加原始路径用于删除
            "type": media_type
        })
        
    return {
        "items": result,
        "page": page,
        "has_more": end < total
    }

# 新增：删除接口
@app.post("/api/delete")
async def delete_file(req: DeleteRequest):
    try:
        # 防止路径遍历攻击，确保只删除 content 目录下的文件
        target_path = (CONTENT_DIR / req.path).resolve()
        
        if not str(target_path).startswith(str(CONTENT_DIR)):
            raise HTTPException(status_code=403, detail="非法路径")
            
        if target_path.exists() and target_path.is_file():
            os.remove(target_path)
            
            # 从缓存中移除
            str_path = req.path.replace("\\", "/") # 统一路径分隔符
            for key in CACHE:
                if str_path in CACHE[key]:
                    CACHE[key].remove(str_path)
            
            print(f"已删除文件: {target_path}")
            return {"status": "success"}
        else:
            return {"status": "error", "message": "文件不存在"}
            
    except Exception as e:
        print(f"删除失败: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)