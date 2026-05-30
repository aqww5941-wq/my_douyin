# 这是一个属于自己的视频播放器，让你直接在手机查看电脑文件夹的视频、照片
## 快速实现
## 资源准备
1. 爬取x，tiktok，dy视频（或者直接放入你自己的视频，照片）
2. 修改main.py的映射路径
3. 修改docker-compose.yml的路径
4. 直接部署
```bash
docker compose up --build -d
```
5.访问localhost:9000
## 手机访问
同一网段：
    手机浏览器直接访问电脑ip:9000
不同网段可以用cloudflare
