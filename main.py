# main.py
import os
import random
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()

# 容器内资源挂载路径
CONTENT_DIR = Path("/app/content")

# 挂载静态文件，使前端可以通过 /media/xxx 访问视频和图片
app.mount("/media", StaticFiles(directory=str(CONTENT_DIR)), name="media")

templates = Jinja2Templates(directory="templates")

# 支持的文件扩展名
VIDEO_EXTS = {'.mp4', '.mov', '.webm'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# 内存缓存，避免频繁 IO
CACHE = {
    "douyin": [],
    "x_video": [],
    "x_image": [],
    "recommend": []
}

def scan_files():
    """扫描目录并更新缓存"""
    print("正在扫描媒体文件...")
    
    # 1. 扫描抖音视频
    douyin_videos = []
    douyin_path = CONTENT_DIR / "douyin" / "videos"
    if douyin_path.exists():
        for root, _, files in os.walk(douyin_path):
            for file in files:
                if Path(file).suffix.lower() in VIDEO_EXTS:
                    # 获取相对于 CONTENT_DIR 的路径
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    douyin_videos.append(str(rel_path))
    
    # 2. 扫描 X 视频 (x/videos/*/*.mp4)
    x_videos = []
    x_vid_path = CONTENT_DIR / "x" / "videos"
    if x_vid_path.exists():
        for root, _, files in os.walk(x_vid_path):
            for file in files:
                if Path(file).suffix.lower() in VIDEO_EXTS:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    x_videos.append(str(rel_path))

    # 3. 扫描 X 图片 (x/images/*/*.jpg)
    x_images = []
    x_img_path = CONTENT_DIR / "x" / "images"
    if x_img_path.exists():
        for root, _, files in os.walk(x_img_path):
            for file in files:
                if Path(file).suffix.lower() in IMAGE_EXTS:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(CONTENT_DIR)
                    x_images.append(str(rel_path))

    # 更新缓存
    # 这里不需要全局 shuffle 了，因为会在 API 里根据 seed 动态 shuffle
    CACHE["douyin"] = douyin_videos
    CACHE["x_video"] = x_videos
    CACHE["x_image"] = x_images
    
    # 推荐：混合抖音和X的视频
    recommend = douyin_videos + x_videos
    CACHE["recommend"] = recommend
    
    print(f"扫描完成: 抖音视频 {len(douyin_videos)}, X视频 {len(x_videos)}, X图片 {len(x_images)}")

# 启动时扫描一次
scan_files()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/list")
async def get_media_list(tab: str, page: int = 1, size: int = 10, seed: int = 0):
    """
    分页获取媒体列表
    tab: recommend | x | douyin | images
    seed: 随机种子，保证同一会话翻页顺序一致，不同会话顺序不同
    """
    key_map = {
        "recommend": "recommend",
        "douyin": "douyin",
        "x": "x_video",
        "images": "x_image"
    }
    
    target_key = key_map.get(tab, "recommend")
    source_list = CACHE.get(target_key, [])
    
    # 创建列表副本以避免影响全局缓存
    current_list = source_list[:]
    
    # 如果有种子，使用种子进行确定性随机打乱
    # 这样翻页（page增加）时，因为seed没变，顺序也是固定的，不会重复或遗漏
    if seed != 0:
        random.Random(seed).shuffle(current_list)
    
    total = len(current_list)
    start = (page - 1) * size
    end = start + size
    
    # 切片分页
    items = current_list[start:end]
    
    # 构造返回数据
    # type: 'video' or 'image'
    media_type = 'image' if target_key == 'x_image' else 'video'
    
    result = []
    for path in items:
        result.append({
            "src": f"/media/{path}",
            "type": media_type
        })
        
    return {
        "items": result,
        "page": page,
        "has_more": end < total
    }