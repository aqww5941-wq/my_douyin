import os
import random
from pathlib import Path
from typing import List, Dict, Set
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import time

app = FastAPI()

# 容器内资源挂载路径
CONTENT_DIR = Path("/app/content")

# 挂载静态文件
app.mount("/media", StaticFiles(directory=str(CONTENT_DIR)), name="media")

templates = Jinja2Templates(directory="templates")

# 支持的文件扩展名
VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.avi', '.mkv', '.flv', '.m4v', '.wmv'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}

# 全局缓存
FILE_CACHE = {
    "all_videos": [],      # 所有视频文件
    "all_images": [],      # 所有图片文件
    "douyin_videos": [],   # 抖音视频
    "x_videos": [],        # X视频
    "x_images": [],        # X图片
    "liked": set(),        # 点赞的文件路径集合
    "last_scan_time": 0    # 上次扫描时间
}

class DeleteRequest(BaseModel):
    path: str

class LikeRequest(BaseModel):
    path: str

def scan_all_media_files():
    """扫描所有媒体文件，构建完整缓存"""
    print(f"开始扫描媒体文件，目录: {CONTENT_DIR}")
    
    # 清空缓存
    FILE_CACHE["all_videos"] = []
    FILE_CACHE["all_images"] = []
    FILE_CACHE["douyin_videos"] = []
    FILE_CACHE["x_videos"] = []
    FILE_CACHE["x_images"] = []
    
    total_files = 0
    scanned_paths = set()
    
    # 递归扫描所有文件
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            file_path = Path(root) / file
            try:
                rel_path = file_path.relative_to(CONTENT_DIR)
                str_path = str(rel_path).replace("\\", "/")
                
                # 避免重复扫描
                if str_path in scanned_paths:
                    continue
                    
                scanned_paths.add(str_path)
                ext = file_path.suffix.lower()
                
                # 分类文件
                if ext in VIDEO_EXTS:
                    FILE_CACHE["all_videos"].append(str_path)
                    
                    # 抖音视频 - 改进路径匹配
                    if "douyin" in str_path.lower():
                        FILE_CACHE["douyin_videos"].append(str_path)
                    
                    # X视频
                    elif "x" in str_path.lower() and "video" in str_path.lower():
                        FILE_CACHE["x_videos"].append(str_path)
                    
                    total_files += 1
                    
                elif ext in IMAGE_EXTS:
                    FILE_CACHE["all_images"].append(str_path)
                    
                    # X图片
                    if "/x/images/" in str_path.lower() or "x/image" in str_path.lower():
                        FILE_CACHE["x_images"].append(str_path)
                    
                    total_files += 1
                    
            except ValueError:
                continue
            except Exception as e:
                print(f"扫描文件出错 {file_path}: {e}")
                continue
    
    # 打乱顺序（为了随机推荐）
    random.shuffle(FILE_CACHE["all_videos"])
    random.shuffle(FILE_CACHE["all_images"])
    random.shuffle(FILE_CACHE["douyin_videos"])
    random.shuffle(FILE_CACHE["x_videos"])
    random.shuffle(FILE_CACHE["x_images"])
    
    FILE_CACHE["last_scan_time"] = time.time()
    
    print(f"扫描完成！共找到 {total_files} 个媒体文件")
    print(f"  所有视频: {len(FILE_CACHE['all_videos'])} 个")
    print(f"  所有图片: {len(FILE_CACHE['all_images'])} 个")
    print(f"  抖音视频: {len(FILE_CACHE['douyin_videos'])} 个")
    print(f"  X视频: {len(FILE_CACHE['x_videos'])} 个")
    print(f"  X图片: {len(FILE_CACHE['x_images'])} 个")
    print(f"  喜欢的文件: {len(FILE_CACHE['liked'])} 个")

def get_tab_files(tab: str, seed: int = 0):
    """根据标签获取对应的文件列表"""
    if tab == "recommend":
        # 推荐：所有视频混合
        files = FILE_CACHE["all_videos"].copy()
        if seed:
            random.Random(seed).shuffle(files)
        return files
        
    elif tab == "douyin":
        # 抖音视频
        files = FILE_CACHE["douyin_videos"].copy()
        if seed:
            random.Random(seed).shuffle(files)
        return files
        
    elif tab == "x":
        # X视频
        files = FILE_CACHE["x_videos"].copy()
        if seed:
            random.Random(seed).shuffle(files)
        return files
        
    elif tab == "images":
        # X图片
        files = FILE_CACHE["x_images"].copy()
        if seed:
            random.Random(seed).shuffle(files)
        return files
        
    elif tab == "likes":
        # 喜欢的文件（按点赞时间倒序）
        liked_files = list(FILE_CACHE["liked"])
        # 确保文件存在
        valid_files = []
        for file_path in liked_files:
            full_path = CONTENT_DIR / file_path
            if full_path.exists():
                valid_files.append(file_path)
        return valid_files[::-1]  # 倒序，最新的在前面
        
    else:
        return []

# 启动时扫描
scan_all_media_files()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/list")
async def get_media_list(tab: str, page: int = 1, size: int = 30, seed: int = 0):
    """获取媒体列表"""
    # 如果长时间没扫描，自动重新扫描
    if time.time() - FILE_CACHE["last_scan_time"] > 300:  # 5分钟
        print("自动重新扫描媒体文件...")
        scan_all_media_files()
    
    # 获取对应标签的文件列表
    all_files = get_tab_files(tab, seed)
    
    if not all_files:
        return {"items": [], "page": page, "has_more": False, "total": 0}
    
    total = len(all_files)
    start = (page - 1) * size
    end = start + size
    
    # 分页
    page_files = all_files[start:end]
    
    result = []
    for file_path in page_files:
        full_path = CONTENT_DIR / file_path
        if not full_path.exists():
            continue
            
        # 判断文件类型
        ext = Path(file_path).suffix.lower()
        file_type = 'image' if ext in IMAGE_EXTS else 'video'
        
        result.append({
            "src": f"/media/{file_path}",
            "raw_path": file_path,
            "type": file_type
        })
    
    has_more = end < total
    
    print(f"API请求 - Tab: {tab}, Page: {page}, Size: {size}, Total: {total}, Returned: {len(result)}, HasMore: {has_more}")
    
    return {
        "items": result, 
        "page": page, 
        "has_more": has_more,
        "total": total
    }

@app.post("/api/like")
async def like_file(req: LikeRequest):
    """点赞文件"""
    path = req.path.replace("\\", "/").strip()
    if not path:
        return JSONResponse({"status": "error", "message": "路径不能为空"})
    
    # 检查文件是否存在
    full_path = CONTENT_DIR / path
    if not full_path.exists():
        return JSONResponse({"status": "error", "message": "文件不存在"})
    
    # 添加到喜欢集合
    if path not in FILE_CACHE["liked"]:
        FILE_CACHE["liked"].add(path)
        print(f"已添加收藏: {path}")
    else:
        # 如果已存在，取消点赞（可选）
        # FILE_CACHE["liked"].remove(path)
        # print(f"已取消收藏: {path}")
        print(f"收藏夹已存在: {path}")
        
    return {"status": "success", "liked": path in FILE_CACHE["liked"]}

@app.post("/api/delete")
async def delete_file(req: DeleteRequest):
    """删除文件"""
    try:
        target_path = (CONTENT_DIR / req.path).resolve()
        
        # 安全检查：确保删除的文件在内容目录内
        if not str(target_path).startswith(str(CONTENT_DIR)):
            raise HTTPException(status_code=403, detail="非法路径")
            
        if target_path.exists() and target_path.is_file():
            # 从缓存中移除（如果有）
            str_path = req.path.replace("\\", "/")
            
            # 从所有视频/图片列表中移除
            for key in ["all_videos", "all_images", "douyin_videos", "x_videos", "x_images"]:
                if str_path in FILE_CACHE[key]:
                    FILE_CACHE[key].remove(str_path)
            
            # 从喜欢的列表中移除
            if str_path in FILE_CACHE["liked"]:
                FILE_CACHE["liked"].remove(str_path)
            
            # 删除文件
            os.remove(target_path)
            
            print(f"已删除文件: {req.path}")
            return {"status": "success", "message": "文件已删除"}
            
        return {"status": "error", "message": "文件不存在"}
    except Exception as e:
        print(f"删除文件时出错: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/rescan")
async def rescan_files():
    """重新扫描所有文件"""
    try:
        scan_all_media_files()
        return {
            "status": "success", 
            "message": f"重新扫描完成",
            "counts": {
                "all_videos": len(FILE_CACHE["all_videos"]),
                "all_images": len(FILE_CACHE["all_images"]),
                "douyin_videos": len(FILE_CACHE["douyin_videos"]),
                "x_videos": len(FILE_CACHE["x_videos"]),
                "x_images": len(FILE_CACHE["x_images"]),
                "liked": len(FILE_CACHE["liked"])
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return {
        "status": "success",
        "stats": {
            "all_videos": len(FILE_CACHE["all_videos"]),
            "all_images": len(FILE_CACHE["all_images"]),
            "douyin_videos": len(FILE_CACHE["douyin_videos"]),
            "x_videos": len(FILE_CACHE["x_videos"]),
            "x_images": len(FILE_CACHE["x_images"]),
            "liked": len(FILE_CACHE["liked"]),
            "last_scan": FILE_CACHE["last_scan_time"],
            "content_dir": str(CONTENT_DIR)
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")