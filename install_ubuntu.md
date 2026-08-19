# 执行逻辑说明
1. 更新apt软件源
2. 创建临时目录 `softwares` 并进入该目录
3. 在临时目录下载安装包
4. 安装完成后删除临时目录 `softwares`


## 准备安装

```bash
# 更新软件源
sudo apt update -y

# 安装必要的软件
sudo apt install -y net-tools gedit synaptic git gedit curl
```

## 安装 Google Chrome
```bash
echo "===== 开始安装 Google Chrome Stable ====="

# 检测是否已安装 google-chrome-stable
if command -v google-chrome-stable &> /dev/null; then
    echo "✅ 检测到 Google Chrome 已安装，跳过下载与安装步骤"
else
    echo "ℹ️ 未检测到 Chrome，开始下载安装"
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    echo "✅ Chrome 安装成功"
fi
```

## 配置git
```bash
test_github_ssh() {
    echo "==== DEBUG ssh 测试开始 ====" >&2
    ssh -T \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
        -o ConnectTimeout=10 \
        -i "${SSH_KEY_PATH}" \
        git@github.com
    local ret=$?
    echo "==== DEBUG ssh 返回码: $ret ====" >&2
    # 成功输出包含这段字符串
    if [[ $? -eq 0 ]]; then
        return 0
    else
        return 1
    fi
}

echo "=== 1. 安装 git & openssh-client ==="
sudo apt update
sudo apt install -y git openssh-client

echo "=== 2. 设置 Git 全局用户名与邮箱 ==="
git config --global user.name "${GIT_NAME}"
git config --global user.email "${GIT_EMAIL}"

echo "=== 3. 创建 SSH Ed25519 密钥（不存在才生成） ==="
if [ ! -f "${SSH_KEY_PATH}" ]; then
    ssh-keygen -t ed25519 -C "${GIT_EMAIL}" -f "${SSH_KEY_PATH}" -N ""
    echo "✅ 成功新建 SSH 密钥"
else
    echo "ℹ️ SSH 密钥已存在，跳过创建"
fi

echo "=== 4. 尝试将私钥添加到当前会话 ssh-agent ==="
ssh-add "${SSH_KEY_PATH}" 2>/dev/null || echo "ℹ️ 密钥可能已在agent中，忽略"

echo "=== 5. 检测 GitHub SSH 连通状态 ==="
if test_github_ssh; then
    echo "✅ 检测通过：当前已可正常使用 SSH 访问 GitHub，无需添加公钥"
else
    echo "❌ 暂未连通 GitHub，请复制下方公钥添加至 GitHub 账号"
    echo "----------------------------------------------------------------------"
    cat "${SSH_KEY_PATH}.pub"
    echo "----------------------------------------------------------------------"
    echo "网页地址：https://github.com/settings/keys"
    echo "完成添加后，请按下回车键继续..."

    # 方案B：强制终端输入，兼容你的Python管道执行模式
    if [ -c /dev/tty ]; then
        read -r _ < /dev/tty
    else
        echo "⚠️ 当前无交互式终端，无法等待人工确认，直接继续执行"
    fi

    echo "正在重新测试 GitHub 连接..."
    if test_github_ssh; then
        echo "✅ GitHub SSH 认证成功！"
    else
        echo "❌ 连接仍然失败！排查清单："
        echo "1) GitHub页面完整粘贴公钥，无多余换行、空格"
        echo "2) 新开宿主终端手动执行：ssh-add ~/.ssh/id_ed25519 && ssh -T git@github.com"
        echo "3) 确认公钥在GitHub SSH keys列表中已生效"
        exit 1
    fi
fi

echo -e "\n🎉 宿主机 GitHub SSH 初始化流程全部完成\n"
```


## 配置中文语言包
```bash
echo "===== 开始配置中文语言支持 + 安装ibus-libpinyin输入法（界面保持英文） ====="

# 1. 更新源，安装简体中文语言包（仅提供中文文字支持，不修改系统界面语言）
sudo apt -y install language-pack-zh-hans language-pack-gnome-zh-hans language-pack-zh-hans-base fonts-noto-cjk

# 2. 生成 zh_CN.UTF-8 语言环境（必备！输入法需要此locale，不会改变界面语言）
sudo locale-gen zh_CN.UTF-8

# ===== 已彻底删除 sudo update-locale LANG=zh_CN.UTF-8，界面维持英文 =====

# 3. 安装ibus框架 + libpinyin拼音输入法
sudo apt -y install ibus-libpinyin ibus-gtk ibus-gtk3

# 4. 校验 ibus-libpinyin 是否安装成功
echo "🔍 正在校验 ibus-libpinyin 安装状态..."
if dpkg -s ibus-libpinyin &>/dev/null; then
    echo "✅ ibus-libpinyin 安装校验成功"
else
    echo "❌ ibus-libpinyin 未找到，安装失败！"
    echo "👉 调试命令：sudo apt install ibus-libpinyin"
    exit 1
fi

# 5. 当前用户会话配置输入法（禁止sudo运行！）
if [[ "$USER" != "root" ]]; then
    # ========== 关键变更：输入源只保留 libpinyin 一个 ==========
    gsettings set org.gnome.desktop.input-sources sources "[('ibus', 'libpinyin')]"
    echo "✅ GNOME输入源：仅保留 libpinyin 单一输入法"
    
    # 输入法引擎：启动默认英文（Initial State English）
    gsettings set com.github.libpinyin.ibus-libpinyin.libpinyin init-chinese false
    echo "✅ libpinyin 初始输入状态设置为英文"

    # 设置候选词数量修改为9个
    gsettings set com.github.libpinyin.ibus-libpinyin.libpinyin lookup-table-page-size 9
    echo "✅ ibus-libpinyin 候选词数量设置为9"

    # 重启ibus加载新配置
    ibus restart
    echo "✅ IBus服务已重启，配置加载完成"
fi

echo "===== 输入法部署完成 ====="
echo "💡 建议注销会话保证全部设置生效"
echo "操作方式："
echo "  只有一个输入法 libpinyin；按 Shift 切换引擎内中英文"
echo "  初始进入输入法默认英文，Shift切换中文拼音"
echo "验证命令："
echo "gsettings get com.github.libpinyin.ibus-libpinyin.libpinyin init-chinese"
echo "gsettings get com.github.libpinyin.ibus-libpinyin.libpinyin lookup-table-page-size"
```

## v2rayN开机自启
```bash
echo "===== 配置 v2rayN 开机自启 ====="

AUTOSTART_DIR="${HOME}/.config/autostart"
EXE_PATH="${HOME}/Programs/v2rayN-linux-64/v2rayN"
DESKTOP_FILE="${AUTOSTART_DIR}/v2rayN.desktop"

# 创建自启目录（不存在则新建）
mkdir -p "${AUTOSTART_DIR}"

# 校验可执行文件是否存在
if [ ! -x "${EXE_PATH}" ]; then
    echo "❌ 错误：找不到可执行文件 ${EXE_path} 或缺少执行权限"
    exit 1
fi

# 写入 desktop 自启配置
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=v2rayN
Comment=v2rayN Proxy Client
Exec=${EXE_PATH}
Icon=${HOME}/Programs/v2rayN-linux-64/v2rayN.png
StartupWMClass=v2rayN
X-GNOME-Autostart-enabled=true
EOF

# 赋予desktop文件权限
chmod 644 "${DESKTOP_FILE}"

echo "✅ v2rayN 开机自启配置完成"
echo "📄 自启文件路径：${DESKTOP_FILE}"
echo "💡 注销/重启后生效，可在 Startup Applications 图形界面看到条目"
```


## 安装微信
```bash
echo "=== Checking flatpak ==="
if ! command -v flatpak &>/dev/null; then
    echo "Flatpak not found, installing flatpak..."
    sudo apt install -y flatpak
fi

echo "=== Checking flathub remote ==="
# 如果不存在才添加，避免重复报错; 添加【用户级】flathub源，无需sudo、不弹密码
if ! flatpak --user remote-list | grep -q flathub; then
    echo "Adding user-level flathub remote..."
    flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
fi

echo "===== 安装微信 Flatpak(com.tencent.WeChat)【当前用户级别】 ====="
# 检测【用户级别】微信是否已经安装
if flatpak list --user | grep -q "com.tencent.WeChat"; then
    echo "✅ 检测到微信(com.tencent.WeChat)已在当前用户下安装，跳过安装步骤"
else
    echo "ℹ️ 未检测到微信，开始用户级安装"

    # 1. 安装flatpak依赖，非交互模式
    sudo DEBIAN_FRONTEND=noninteractive apt update
    sudo DEBIAN_FRONTEND=noninteractive apt install -y flatpak gnome-software-plugin-flatpak

    # 2. 添加 flathub 仅到【当前用户】remote，--if-not-exists 存在则跳过
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

    # 3. --user：安装到当前用户；-y 自动全部yes，无交互
    flatpak install --user -y flathub com.tencent.WeChat

    # 4. 校验用户级别安装结果
    if flatpak list --user | grep -q "com.tencent.WeChat"; then
        echo "✅ 微信(com.tencent.WeChat)【用户级】安装校验成功"
    else
        echo "❌ 微信安装失败，当前用户下未检测到 com.tencent.WeChat"
        exit 1
    fi
fi

echo "💡 提示：注销会话后，应用菜单可以找到WeChat；命令行启动：flatpak run --user com.tencent.WeChat"
```


## 安装 Podman&Podman desktop
```bash
sudo apt install -y podman

echo "=== Checking flatpak ==="
if ! command -v flatpak &>/dev/null; then
    echo "Flatpak not found, installing flatpak..."
    sudo apt install -y flatpak
fi

echo "=== Checking flathub remote ==="
# 如果不存在才添加，避免重复报错; 添加【用户级】flathub源，无需sudo、不弹密码
if ! flatpak --user remote-list | grep -q flathub; then
    echo "Adding user-level flathub remote..."
    flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
fi

if ! flatpak --user list | grep -q io.podman_desktop.PodmanDesktop; then
    echo "=== Podman Desktop not found, starting installation (non-interactive) ==="
    flatpak install --user -y flathub io.podman_desktop.PodmanDesktop
    if ! flatpak --user list | grep -q io.podman_desktop.PodmanDesktop; then
        echo "ERROR: Podman Desktop installation finished but not detected!" >&2
        exit 1
    fi
    echo "✅ Podman Desktop installed successfully."
else
    echo "✅ Podman Desktop already installed, skip installation."
fi
```


## 安装ubuntu镜像
```bash
# ========== 配置区 ==========
HOST_USER="$USER"
HOME_MOUNT_SRC="${HOME}/Podman/${CONTAINER_NAME}"
# ===========================

# 1. 创建宿主机目录并修正权限
mkdir -p "${HOME_MOUNT_SRC}"
chown -R "${HOST_USER}:${HOST_USER}" "${HOME_MOUNT_SRC}"
chmod -R u+rwX "${HOME_MOUNT_SRC}"

# 2. 判断容器是否存在
if podman ps -a --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "ℹ️ 容器 ${CONTAINER_NAME} 已存在"
    if podman ps --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
        echo "ℹ️ 容器正在运行，无需启动"
    else
        echo "🔄 启动停止的容器 ${CONTAINER_NAME}"
        podman start "${CONTAINER_NAME}"
    fi
else
    echo "🚀 创建新容器 ${CONTAINER_NAME}"
    podman run -d \
      --name "${CONTAINER_NAME}" \
      --init \
      --network host \
      --userns=keep-id \
      -v "${HOME_MOUNT_SRC}:/home/${HOST_USER}" \
      -v "${HOME}/Projects:/Projects" \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      -e DISPLAY="${DISPLAY}" \
      "${IMAGE_NAME}" sleep infinity

    echo "⚙️ 开始执行容器内用户初始化"
    export HOST_USER
    podman exec -i --user root "${CONTAINER_NAME}" bash <<EOF
#!/bin/bash
set -e
NEW_USER="${HOST_USER}"
OLD_USER="ubuntu"

# 判断用户名是否已经修改，避免重复执行报错
if id -u "\${NEW_USER}" >/dev/null 2>&1; then
    echo "✅ 用户 \${NEW_USER} 已存在，跳过初始化"
    exit 0
fi

usermod -l \${NEW_USER} \${OLD_USER}
groupmod -n \${NEW_USER} \${OLD_USER}
usermod -d /home/\${NEW_USER} \${NEW_USER}

usermod -aG sudo \${NEW_USER}
echo "\${NEW_USER} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# 注意：仅首次创建时执行权限修复；重复运行不会走到这里
chown -R \${NEW_USER}:\${NEW_USER} /home/\${NEW_USER}
echo "✅ 用户初始化完成，容器内用户名：\${NEW_USER}"
EOF
fi

echo -e "\n🎉 环境就绪！进入容器命令："
echo "podman exec -it --user \$USER -w /home/\$USER ${CONTAINER_NAME} bash"
```


## 安装codex&claude&opencodex
```bash
HOST_USER="$USER"

echo "========================================"
echo "检查容器 ${CONTAINER_NAME} 状态"
echo "========================================"

# 判断容器是否存在
if ! podman ps -a --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "ERROR: 容器 ${CONTAINER_NAME} 不存在，请先执行容器初始化脚本！"
    exit 1
fi

# 容器停止则启动
if ! podman ps --filter "name=^/${CONTAINER_NAME}$" | grep -q "${CONTAINER_NAME}"; then
    echo "容器未运行，执行 podman start"
    podman start "${CONTAINER_NAME}"
    sleep 1
fi

echo "===== 第一步(root)：基础系统依赖安装（非交互防弹窗） ====="
podman exec -i --user root "${CONTAINER_NAME}" bash <<'INNER_ROOT_EOF'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
APT_FORCE_ARGS="-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
apt update ${APT_FORCE_ARGS}
apt ${APT_FORCE_ARGS} -y install sudo curl ca-certificates
dpkg --configure --force-confdef --force-confold -a
INNER_ROOT_EOF

echo "===== 第二步 独立root执行安装Node.js LTS22，执行完销毁此shell进程 ====="
podman exec -i --user root "${CONTAINER_NAME}" bash <<'INNER_ROOT_EOF'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
INNER_ROOT_EOF

echo "===== 第三步($HOST_USER)：全新shell进程，配置npm环境 + 安装官方AI CLI工具 ====="
# 关键点：全新podman exec，全新shell，拿到容器完整默认PATH，/usr/bin已经在PATH
podman exec -i --user "${HOST_USER}" -w "/home/${HOST_USER}" "${CONTAINER_NAME}" bash <<'INNER_EOF'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
HOME_DIR="$HOME"

# --------------------------
# 【强制校验】独立执行，失败直接退出脚本，不能嵌套进 $(...)
# --------------------------
node -v
npm -v
echo "Node 版本: $(node -v)"
echo "NPM 版本: $(npm -v)"

# --------------------------
# 关键：配置npm用户私有全局目录，解决EACCES
# --------------------------
NPM_USER_GLOBAL="${HOME_DIR}/.npm-global"
mkdir -p "${NPM_USER_GLOBAL}"
npm config set prefix "${NPM_USER_GLOBAL}"

NPM_GLOBAL_BIN="${NPM_USER_GLOBAL}/bin"
PATH_LINE="export PATH=${NPM_GLOBAL_BIN}:\$PATH"
# 精确整行匹配，避免重复写入bashrc
if ! grep -Fxq "${PATH_LINE}" "${HOME_DIR}/.bashrc"; then
    echo "${PATH_LINE}" >> "${HOME_DIR}/.bashrc"
fi
# 当前会话立即生效
export PATH="${NPM_GLOBAL_BIN}:$PATH"
echo "npm全局安装目录配置完成：$(npm config get prefix)"

echo "===== 安装 OpenAI 官方 CLI（openai） ====="
if ! command -v codex &> /dev/null; then
    echo "Install openai official cli..."
    npm install -g @openai/codex
else
    echo "codex cli 已安装，跳过"
fi

echo "===== 安装 Anthropic 官方 Claude CLI ====="
if ! command -v claude &> /dev/null; then
    echo "Install @anthropic-ai/claude official cli..."
    npm install -g @anthropic-ai/claude-code
else
    echo "claude cli 已安装，跳过"
fi

echo "===== npm 全局安装：@bitkyc08/opencodex ====="
if ! command -v opencodex &> /dev/null; then
    npm install -g @bitkyc08/opencodex
else
    echo "@bitkyc08/opencodex 已安装，跳过"
fi

echo "===== 安装结果校验 ====="
which codex || echo "codex 命令未找到！"
which claude || echo "claude 命令未找到！"
which opencodex || echo "opencodex 命令未找到！"

echo ""
echo "✅ 所有 CLI 工具安装完成"
echo "进入容器新开终端务必执行：source ~/.bashrc"
echo ""
echo "临时配置密钥示例："
echo "export OPENAI_API_KEY=sk-xxx"
echo "export ANTHROPIC_API_KEY=sk-ant-xxx"
INNER_EOF
```


## 完成安装
```bash
echo "=====  安装完成后删除临时目录 softwares ====="
# 返回Downloads目录
cd ..
# 删除整个临时softwares目录
rm -rf softwares

echo "===== 清理旧podman‑exec相关函数/alias，配置宿主机 .bashrc 新快捷入口 ====="
ALIAS_NAME="${CONTAINER_NAME}"
BASHRC_FILE="${HOME}/.bashrc"

# 删除旧：同时包含 podman exec -it 与 -w /home/ 的旧alias行
sed -i '/podman exec -it/{/-w \/home\//d}' "${BASHRC_FILE}"
# 同时清理旧的同名shell函数残留（防止多次运行堆积）
sed -i "/^${ALIAS_NAME}() {/,/^}/d" "${BASHRC_FILE}"

# 写入shell函数：实现自动判断容器状态，不存在则start，再exec进入
NEW_FUNC_BLOCK=$(cat <<FUNC_EOF
${ALIAS_NAME}() {
    local ctn_name="${ALIAS_NAME}"
    # 判断容器是否存在
    if ! podman ps -a --filter "name=^/\${ctn_name}\$" | grep -q "\${ctn_name}"; then
        echo "错误：容器 \${ctn_name} 不存在！"
        return 1
    fi
    # 判断是否正在运行
    if ! podman ps --filter "name=^/\${ctn_name}\$" | grep -q "\${ctn_name}"; then
        echo "容器 \${ctn_name} 未运行，正在执行 podman start ..."
        podman start "\${ctn_name}"
    fi
    # 进入容器
    podman exec -it --user "\$USER" -w "/home/\$USER" "\${ctn_name}" bash
}
FUNC_EOF
)

echo "${NEW_FUNC_BLOCK}" >> "${BASHRC_FILE}"

echo "✅ 已在 ${BASHRC_FILE} 设置函数入口：${ALIAS_NAME}"
echo "💡 使用方式：新开host终端，source .bashrc, 然后直接输入命令：${ALIAS_NAME}"
echo "💡 容器停止时会自动执行 podman start，然后进入容器"

echo "===== 全部流程执行完毕，临时目录已清理 ====="
```
