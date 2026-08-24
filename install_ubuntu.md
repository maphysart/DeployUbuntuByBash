# 执行逻辑说明
1. 更新apt软件源
2. 创建临时目录 `softwares` 并进入该目录
3. 在临时目录下载安装包
4. 安装完成后删除临时目录 `softwares`
5. 安装podman镜像，并进入容器安装AI相关工具


## 更新源，安装必要软件
```bash
# 更新软件源
sudo apt update -y

# 安装必要的软件
sudo apt install -y net-tools gedit synaptic git gedit curl
```


## 安装Chrome
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


## 安装RustDesk
```bash
echo "===== 安装 RustDesk 远程桌面客户端（自动获取最新stable版本deb） ====="

# 检测rustdesk是否已安装
if command -v rustdesk &>/dev/null; then
    echo "✅ 检测到RustDesk已安装，版本: $(rustdesk --version 2>/dev/null || echo "unknown")，跳过安装"
else
    echo "ℹ️ 未检测到RustDesk，获取最新版本并下载deb包"

    # 获取系统架构，转换为rustdesk deb文件名架构标识
    ARCH=$(uname -m)
    if [[ "${ARCH}" == "x86_64" ]]; then
        DEB_ARCH="x86_64"
    elif [[ "${ARCH}" == "aarch64" ]]; then
        DEB_ARCH="aarch64"
    else
        echo "❌ 不支持的CPU架构: ${ARCH}"
        exit 1
    fi

    # 调用github api拿到最新tag版本号
    LATEST_TAG=$(curl -s https://api.github.com/repos/rustdesk/rustdesk/releases/latest | grep -Po '"tag_name": "\K.*?(?=")')
    echo "ℹ️ 获取到最新RustDesk版本: ${LATEST_TAG}"

    DEB_FILENAME="rustdesk-${LATEST_TAG}-${DEB_ARCH}.deb"
    DOWNLOAD_URL="https://github.com/rustdesk/rustdesk/releases/download/${LATEST_TAG}/${DEB_FILENAME}"

    echo "ℹ️ 下载地址: ${DOWNLOAD_URL}"
    wget -q "${DOWNLOAD_URL}"

    # 本地deb安装
    sudo apt install -y "./${DEB_FILENAME}"

    # 校验安装结果
    if command -v rustdesk &>/dev/null; then
        echo "✅ RustDesk 安装校验成功，版本: $(rustdesk --version 2>/dev/null)"
    else
        echo "❌ RustDesk 安装失败，rustdesk命令未找到"
        exit 1
    fi
fi
echo "💡 提示：终端输入 rustdesk 启动；应用菜单打开 RustDesk"
```


## 安装vscode
```bash
echo "===== 安装 Visual Studio Code ====="

# 判断是否已经安装vscode
if command -v code &>/dev/null; then
    echo "✅ 检测到VS Code已安装，版本: $(code --version | head -n1)，跳过安装"
else
    echo "ℹ️ 未检测到VS Code，开始安装"

    # 安装依赖
    
    sudo apt install -y wget gpg apt-transport-https

    # 导入微软GPG密钥
    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --yes --dearmor -o /usr/share/keyrings/microsoft-vscode.gpg

    # 添加vscode apt源
    echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-vscode.gpg] https://packages.microsoft.com/repos/code stable main" \
    | sudo tee /etc/apt/sources.list.d/vscode.list > /dev/null

    # 更新源并安装code
    sudo apt install -y code

    # 校验安装结果
    if command -v code &>/dev/null; then
        echo "✅ VS Code 安装校验成功，版本: $(code --version | head -n1)"
    else
        echo "❌ VS Code 安装失败，code命令未找到"
        exit 1
    fi
fi

echo "💡 提示：终端输入 code 启动编辑器；code . 打开当前目录"
```


## 配置git
```bash
test_github_ssh() {
    echo "==== DEBUG ssh 测试开始 ====" >&2
    local out
    out=$(ssh -T \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
        -o ConnectTimeout=10 \
        -i "${SSH_KEY_PATH}" \
        git@github.com 2>&1)
    local ret=$?
    echo "$out" >&2
    echo "==== DEBUG ssh 返回码: $ret ====" >&2

    if echo "$out" | grep -q "successfully authenticated"; then
        return 0
    else
        return 1
    fi
}

echo "=== 1. 安装 git & openssh-client ==="
if command -v git &>/dev/null; then
        echo "=== 检测到 git、gh‑cli 均已安装，跳过安装流程 ==="
        git --version
        echo "✅ git 已是就绪状态"
else
    sudo apt install -y git openssh-client
fi

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

echo "=== 5. 检测 GitHub SSH 连通状态（最多重试3次） ==="
MAX_RETRY=3
RETRY_DELAY=2
ok=1
for ((i=0;i<MAX_RETRY;i++)); do
    if test_github_ssh; then
        ok=0
        break
    fi
    echo "⚠️ GitHub SSH测试失败，等待${RETRY_DELAY}秒后重试 ($((i+1))/${MAX_RETRY})" >&2
    sleep ${RETRY_DELAY}
done

if [[ ${ok} -ne 0 ]]; then
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
    # 用户手工添加公钥之后，再做一轮最多3次重试
    ok=1
    for ((i=0;i<MAX_RETRY;i++)); do
        if test_github_ssh; then
            ok=0
            break
        fi
        echo "⚠️ GitHub SSH测试失败，等待${RETRY_DELAY}秒后重试 ($((i+1))/${MAX_RETRY})" >&2
        sleep ${RETRY_DELAY}
    done
    if [[ ${ok} -ne 0 ]]; then
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

# 预先判断是否已经完成全部配置
SKIP_CONFIG="false"
# locale是否已存在
LOCALE_EXIST=$(locale -a | grep -q 'zh_CN.utf8' && echo "yes" || echo "no")
# 获取当前gnome输入源
CUR_INPUT_SOURCES=$(gsettings get org.gnome.desktop.input-sources sources 2>/dev/null || echo "")
# 获取libpinyin配置
CUR_INIT_CHINESE=$(gsettings get com.github.libpinyin.ibus-libpinyin.libpinyin init-chinese 2>/dev/null || echo "")
CUR_PAGE_SIZE=$(gsettings get com.github.libpinyin.ibus-libpinyin.libpinyin lookup-table-page-size 2>/dev/null || echo "")

if [[ "$USER" != "root" ]] && \
   [[ "${LOCALE_EXIST}" == "yes" ]] && \
   [[ "${CUR_INPUT_SOURCES}" == "[('ibus', 'libpinyin')]" ]] && \
   [[ "${CUR_INIT_CHINESE}" == "false" ]] && \
   [[ "${CUR_PAGE_SIZE}" == "9" ]] && \
   dpkg -s ibus-libpinyin &>/dev/null; then
    echo "✅ 检测到中文locale、ibus‑libpinyin输入法及配置均已完成，跳过全部配置步骤"
    SKIP_CONFIG="true"
fi

if [[ "${SKIP_CONFIG}" != "true" ]]; then
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


if [ -f "${DESKTOP_FILE}" ]; then
    echo "✅ v2rayN自启文件已存在，跳过配置操作"
else
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
fi
```


## 安装moonlight
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

echo "===== Ubuntu24.04 Moonlight‑Qt 部署开始 ====="
# 检测【用户级别】Moonlight是否已安装
if flatpak list --app | grep -q 'com.moonlight_stream.Moonlight'; then
    echo "检测到 Moonlight‑Qt 已经安装，跳过安装步骤"
else
    echo "开始安装 Moonlight‑Qt (flatpak)"
    flatpak install --user -y flathub com.moonlight_stream.Moonlight

    # 校验用户级别安装结果
    if flatpak list --user | grep -q "com.moonlight_stream.Moonlight"; then
        echo "✅ Moonlight【用户级】安装校验成功"
    else
        echo "❌ Moonlight安装失败，当前用户下未检测到 com.moonlight_stream.Moonlight"
        exit 1
    fi
fi

echo "===== Moonlight部署脚本执行完毕 ====="
echo "【注意】配对操作需要手动在脚本外部执行，示例命令："
echo "flatpak run com.moonlight_stream.Moonlight pair ${SUNSHINE_IP}"
echo "打开浏览器访问 https://${SUNSHINE_IP}:47990 输入PIN码完成配对"
echo "配对完成后串流示例："
echo "flatpak run com.moonlight_stream.Moonlight stream ${SUNSHINE_IP} --resolution 1920x1080 --fps 60"
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
    flatpak install --user -y flathub com.tencent.WeChat

    # 校验用户级别安装结果
    if flatpak list --user | grep -q "com.tencent.WeChat"; then
        echo "✅ 微信(com.tencent.WeChat)【用户级】安装校验成功"
    else
        echo "❌ 微信安装失败，当前用户下未检测到 com.tencent.WeChat"
        exit 1
    fi
fi

echo "💡 提示：注销会话后，应用菜单可以找到WeChat；命令行启动：flatpak run --user com.tencent.WeChat"
```


## 安装Podman&Podman desktop
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
echo "===== 宿主机预处理：podman.socket 与 linger 配置 ====="
# 1. 检测podman rootless socket是否存在，不存在则启用podman.socket
SOCKET_PATH="/run/user/$UID/podman/podman.sock"
if [ ! -S "${SOCKET_PATH}" ]; then
    echo "ℹ️ podman socket ${SOCKET_PATH} 不存在，执行 systemctl --user enable --now podman.socket"
    systemctl --user enable --now podman.socket
    sleep 1
else
    echo "✅ podman socket 已存在 ${SOCKET_PATH}"
fi

# 2. 检查 linger 状态，没有开启则开启
LINGER_STATUS=$(loginctl show-user "$USER" --property=Linger | cut -d'=' -f2)
echo "ℹ️ 当前用户 linger 状态: ${LINGER_STATUS}"
if [[ "${LINGER_STATUS}" != "yes" ]]; then
    echo "⚠️ Linger未开启，执行 sudo loginctl enable-linger $USER"
    sudo loginctl enable-linger "$USER"
else
    echo "✅ linger 已经开启"
fi

# ========== 配置区 ==========
HOST_USER="$USER"
HOME_MOUNT_SRC="${PODMAN_ROOT}/${CONTAINER_NAME}"
# ===========================

# 1. 创建宿主机目录并修正权限
mkdir -p "${HOME_MOUNT_SRC}"
chown -R "${HOST_USER}:${HOST_USER}" "${HOME_MOUNT_SRC}"
chmod -R u+rwX "${HOME_MOUNT_SRC}"

# 2. 判断容器是否存在, 没有的话就新建并启动
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
      -v "${PROJECTS_ROOT}:/Projects" \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      -v "${SSH_AUTH_SOCK}:/ssh-agent.sock:ro" \
      -e SSH_AUTH_SOCK=/ssh-agent.sock \
      -v "/run/user/$UID/podman/podman.sock:/run/user/$UID/podman/podman.sock" \
      -e CONTAINER_HOST="unix:///run/user/$UID/podman/podman.sock" \
      -e DISPLAY="${DISPLAY}" \
      "${CONTAINER_IMAGE}" sleep infinity

    echo "⚙️ 开始执行容器内用户初始化"
    export HOST_USER
    podman exec -i --user root "${CONTAINER_NAME}" bash <<INNER_ROOT_EOF
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

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
INNER_ROOT_EOF
fi

echo -e "\n容器就绪，首次apt update"
podman exec -i --user root "${CONTAINER_NAME}" bash <<INNER_ROOT_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    apt update
    apt install -y sudo curl ca-certificates iproute2 podman
    dpkg --configure --force-confdef --force-confold -a

INNER_ROOT_EOF
```


## 安装git&git cli
```bash
HOST_USER="$USER"

podman exec -i --user root "${CONTAINER_NAME}" bash <<INNER_ROOT_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    # 检查git与gh是否全部已安装
    if command -v git &>/dev/null && command -v gh &>/dev/null; then
        echo "=== 检测到 git、gh‑cli 均已安装，跳过安装流程 ==="
        git --version
        gh --version
        echo "✅ root端：git + gh‑cli 已是就绪状态"
    else
        echo "=== apt 更新，安装 git、ca‑certificates、curl、gnupg ==="
        apt install -y git ca-certificates curl gnupg

        echo "=== 配置 GitHub CLI apt源 ==="
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
        chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg

        echo "deb [arch=\$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list

        # 更新apt索引（新增，添加gh源之后必须update）
        apt install -y gh

        echo "=== 版本检查 ==="
        git --version
        gh --version

        echo "✅ root端：git + gh‑cli 安装完成"
    fi

INNER_ROOT_EOF

podman exec -i --user "${HOST_USER}" "${CONTAINER_NAME}" bash <<INNER_USER_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    test_github_ssh_podman() {
        echo "==== podman DEBUG ssh 测试开始 ====" >&2
        local out
        out=\$(ssh -T \
            -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile="\${HOME}/.ssh/known_hosts" \
            -o ConnectTimeout=10 \
            git@github.com 2>&1)
        local ret=\$?
        echo "\$out" >&2
        echo "==== DEBUG ssh 返回码: \$ret ====" >&2

        if echo "\$out" | grep -q "successfully authenticated"; then
            return 0
        else
            return 1
        fi
    }
    echo "容器内 SSH_AUTH_SOCK = \${SSH_AUTH_SOCK:-未设置}"

    MAX_RETRY=3
    RETRY_DELAY=2
    ok=1
    for ((i=0;i<MAX_RETRY;i++)); do
        if test_github_ssh_podman ; then
            ok=0
            break
        fi
        echo "⚠️ GitHub SSH测试失败，等待\${RETRY_DELAY}秒后重试 (\$((i+1))/\${MAX_RETRY})" >&2
        sleep \${RETRY_DELAY}
    done

    if [[ \${ok} -ne 0 ]]; then
        echo "ERROR: 容器内经过\${MAX_RETRY}次重试，仍然无法连通GitHub SSH，请检查socket挂载、宿主机ssh‑agent是否加载私钥、网络连接" >&2
        exit 1
    fi

    echo "容器内：GitHub SSH测试通过"
INNER_USER_EOF
```


## 安装codex&claude&opencodex
```bash
HOST_USER="$USER"

echo "===== 第1步 独立root执行安装Node.js LTS22，执行完销毁此shell进程 ====="
podman exec -i --user root "${CONTAINER_NAME}" bash <<INNER_ROOT_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    if command -v node &>/dev/null; then
        echo "=== 检测到 node 已安装，跳过安装流程 ==="
    else
        curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
        apt install -y nodejs
    fi
INNER_ROOT_EOF

echo "===== 第2步($HOST_USER)：全新shell进程，配置npm环境 + 安装官方AI CLI工具 ====="
# 关键点：全新podman exec，全新shell，拿到容器完整默认PATH，/usr/bin已经在PATH
podman exec -i --user "${HOST_USER}" -w "/home/${HOST_USER}" "${CONTAINER_NAME}" bash <<INNER_USER_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    HOME_DIR="\${HOME}"

    # --------------------------
    # 【强制校验】独立执行，失败直接退出脚本，不能嵌套进 \$(...)
    # --------------------------
    node -v
    npm -v
    echo "Node 版本: \$(node -v)"
    echo "NPM 版本: \$(npm -v)"

    # --------------------------
    # 关键：配置npm用户私有全局目录，解决EACCES
    # --------------------------
    NPM_USER_GLOBAL="\${HOME_DIR}/.npm-global"
    mkdir -p "\${NPM_USER_GLOBAL}"
    npm config set prefix "\${NPM_USER_GLOBAL}"

    NPM_GLOBAL_BIN="\${NPM_USER_GLOBAL}/bin"

    # 容器内：拼接最终写入.bashrc的行；单引号'$PATH'保留字面$PATH符号
    FINAL_PATH_LINE=\$(printf 'export PATH=%s:\$PATH' "\${NPM_GLOBAL_BIN}")

    # 精确整行匹配，避免重复写入bashrc
    if ! grep -Fxq "\${FINAL_PATH_LINE}" "\${HOME_DIR}/.bashrc"; then
        printf "%s\n" "\${FINAL_PATH_LINE}" >> "\${HOME_DIR}/.bashrc"
    fi
    # 当前会话立即生效（脚本内部会话，这里允许展开$PATH）
    export PATH="\${NPM_GLOBAL_BIN}:\$PATH"
    echo "npm全局安装目录配置完成：\$(npm config get prefix)"

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
INNER_USER_EOF
```


## 配置opencodex
原先设计是，启动ocx start，生成配置文件config.json，然后在前面添加"hostname":"0.0.0.0", 然后把OPENCODEX_API_AUTH_TOKEN
写入容器内的 .bashrc中，从而让opencodex 为整个局域网内的机器提供服务。但是ocx start并不能生成config.json，用户只能手动配置

```bash
echo "===== 修改配置让opencodex监听局域网 ====="
podman exec -i --user "${USER}" "${CONTAINER_NAME}" bash <<INNER_USER_EOF
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    # 宿主机侧直接展开，把真实token嵌入脚本文本
    NEW_TOKEN_VALUE=${OPENCODEX_API_AUTH_TOKEN}

    # 容器内变量，全部加反斜杠，延迟在容器内解析
    BASHRC_FILE="\${HOME}/.bashrc"
    SEARCH_PREFIX="export OPENCODEX_API_AUTH_TOKEN="

    echo "DEBUG: target token value: \${NEW_TOKEN_VALUE}"
    echo "DEBUG: bashrc file: \${BASHRC_FILE}"

    # 原地替换：匹配以 SEARCH_PREFIX 开头的整行，直接替换为带引号的完整行
    sed -i "s|^\${SEARCH_PREFIX}.*|\${SEARCH_PREFIX}\"\${NEW_TOKEN_VALUE}\"|" "\${BASHRC_FILE}"

    # 如果上一步没有匹配到任何行（没有被替换），则追加写入
    if ! grep -q "^\${SEARCH_PREFIX}" "\${BASHRC_FILE}"; then
        echo "\${SEARCH_PREFIX}\"\${NEW_TOKEN_VALUE}\"" >> "\${BASHRC_FILE}"
    fi

    # 校验输出结果
    echo "===== 校验结果 ====="
    grep "^export OPENCODEX_API_AUTH_TOKEN=" "\${BASHRC_FILE}"

INNER_USER_EOF
```


## 安装完成善后
```bash
echo "=====  安装完成后删除下载目录 softwares ====="
cd ~
# 删除整个临时softwares目录, `:?`防止变量为空造成灾难性
rm -rf "${DOWNLOAD_ROOT:?}"

echo "===== 配置宿主机 .bashrc 容器快捷入口 ====="
ALIAS_NAME="${CONTAINER_NAME}"
BASHRC_FILE="${HOME}/.bashrc"

# 删除旧的【PodmanAI标记包裹】整块内容（含首尾注释标记）
sed -i '/# >>> PodmanAI: auto‑generated block start >>>/,/# <<< PodmanAI: auto‑generated block end <<</d' "${BASHRC_FILE}"

# 准备待写入的函数代码块
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

# 逻辑：仅当文件最后一行不为空时，才追加一个空行做间隔
LAST_LINE=$(tail -n1 "${BASHRC_FILE}")
APPEND_BLANK=""
if [[ -n "${LAST_LINE}" ]]; then
    APPEND_BLANK=$'\n'
fi

# 写入：条件空行 + 开始标记 + 函数 + 结束标记
{
    printf "%s" "${APPEND_BLANK}"
    echo "# >>> PodmanAI: auto‑generated block start >>>"
    echo "${NEW_FUNC_BLOCK}"
    echo "# <<< PodmanAI: auto‑generated block end <<<"
} >> "${BASHRC_FILE}"

echo "✅ 已在 ${BASHRC_FILE} 设置函数入口：${ALIAS_NAME}"
echo "💡 使用方式：新开host终端，source .bashrc, 然后直接输入命令：${ALIAS_NAME}"
echo "💡 容器停止时会自动执行 podman start，然后进入容器"
echo "💡 如需手动清除该自动生成块，执行：sed -i '/# >>> PodmanAI: auto‑generated block start >>>/,/# <<< PodmanAI: auto‑generated block end <<</d' ~/.bashrc"

echo "===== 全部流程执行完毕，临时目录已清理 ====="
```
