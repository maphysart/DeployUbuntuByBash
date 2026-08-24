# 执行逻辑说明
1. 删除正在执行的容器，并显示结果
2. 删除`$HOME/Podman`目录
3. 删除下载的image
4. 清理.bashrc中插入的脚本


## 停止并删除AI容器
```bash
echo "===== 停止并删除容器 ${CONTAINER_NAME} ====="

# 检查容器是否存在
if podman ps -a --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "ℹ️ 检测到容器 ${CONTAINER_NAME} 存在，准备停止并删除"
    # 先停止容器
    podman stop "${CONTAINER_NAME}"
    # 删除容器
    podman rm "${CONTAINER_NAME}"
else
    echo "ℹ️ 容器 ${CONTAINER_NAME} 不存在，跳过删除"
fi

# 校验：确认容器已经消失
if podman ps -a --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "❌ 校验失败：容器 ${CONTAINER_NAME} 仍然存在！"
    exit 1
else
    echo "✅ 校验通过：容器 ${CONTAINER_NAME} 已不存在"
fi
```


## 删除PODMAN_ROOT目录
```bash
echo "===== 删除宿主机目录 ${PODMAN_ROOT} ====="

# 检查目录是否存在
if [ -d "${PODMAN_ROOT}" ]; then
    echo "ℹ️ 目录 ${PODMAN_ROOT} 存在，执行删除"
    rm -rf "${PODMAN_ROOT:?}"
else
    echo "ℹ️ 目录 ${PODMAN_ROOT} 不存在，跳过删除"
fi

# 校验：确认目录已经删除
if [ -d "${PODMAN_ROOT}" ]; then
    echo "❌ 校验失败：目录 ${PODMAN_ROOT} 依然存在！"
    exit 1
else
    echo "✅ 校验通过：目录 ${PODMAN_ROOT} 已删除"
fi
```


## 删除容器镜像
```bash
echo "===== 删除镜像 ${CONTAINER_IMAGE} ====="
# 检查镜像是否存在（兼容podman完整repo名称 docker.io/library/xxx）
if podman images --format "{{.Repository}}:{{.Tag}}" | grep -qE "^(${CONTAINER_IMAGE}|docker.io/library/${CONTAINER_IMAGE})$"; then
    echo "ℹ️ 镜像 ${CONTAINER_IMAGE} 存在，执行删除"
    podman rmi "${CONTAINER_IMAGE}"
else
    echo "ℹ️ 镜像 ${CONTAINER_IMAGE} 不存在，跳过删除"
fi

# 校验：确认镜像已移除
if podman images --format "{{.Repository}}:{{.Tag}}" | grep -qE "^(${CONTAINER_IMAGE}|docker.io/library/${CONTAINER_IMAGE})$"; then
    echo "❌ 校验失败：镜像 ${CONTAINER_IMAGE} 仍然存在！"
    exit 1
else
    echo "✅ 校验通过：镜像 ${CONTAINER_IMAGE} 已不存在"
fi
```


## 清理~/.bashrc
```bash
BASHRC_FILE="${HOME}/.bashrc"

# 删除标记包裹的整块
sed -i '/# >>> PodmanAI: auto‑generated block start >>>/,/# <<< PodmanAI: auto‑generated block end <<</d' "${BASHRC_FILE}"
echo "✅ 已移除.bashrc内PodmanAI自动生成的容器快捷函数"
```
