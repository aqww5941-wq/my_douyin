#!/bin/bash
echo "==> 停掉旧容器..."
docker compose down

echo "==> 重建镜像并启动容器..."
docker compose up -d --build

echo "✅ 完成！服务已启动！"
