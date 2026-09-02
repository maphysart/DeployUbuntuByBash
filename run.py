import re
import subprocess
import sys
import json
import shutil
from pathlib import Path

# =================== CONFIG ===================
CONFIG_SAVE_PATH = Path("./.run_md_config.json")
OUTPUT_DIR = Path("./output")

# shebang必须永远脚本第一行
SHELL_SHEBANG = "#!/bin/bash"

# host脚本：不再包含mkdir/cd，移到Install的md内部，不需要format填充
SHELL_HOST_BODY = """set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
"""

# container脚本：去掉#!/bin/bash
SHELL_CONTAINER_BODY = """set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
APT_OPTS="-o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\""
"""

HOST_POSTINSTALL_SCRIPT = """
[[ECHO_BEGIN]]
✅ 容器基础环境（sudo、curl、podman等）root预安装完成！

需要在宿主机执行
source ~/.bashrc

📋 如果要进入容器安装，需要执行以下步骤：

1. 复制生成的容器脚本到容器内home目录：
cp ./output/2.InstallInContainer.sh {HOST_PODMAN_PATH}/{CONTAINER_NAME}/

2. 进入容器：
{CONTAINER_NAME}

3. 【容器内终端中】执行容器业务安装脚本（容器已配置免密sudo）：
chmod +x ./2.InstallInContainer.sh && ./2.InstallInContainer.sh
[[ECHO_END]]
"""


def process_echo_marked_script(text: str) -> str:
    """
    解析带有 [[ECHO_BEGIN]] / [[ECHO_END]] 标记的脚本文本
    标记区间内：每行转为echo打印语句
    标记区间外：原样保留，作为可执行bash代码
    标记本身会被丢弃，不输出到结果。
    """
    result_lines = []
    in_echo_block = False

    for raw_line in text.splitlines():
        line = raw_line
        # 检测开始标记
        if line.strip() == "[[ECHO_BEGIN]]":
            in_echo_block = True
            continue
        # 检测结束标记
        if line.strip() == "[[ECHO_END]]":
            in_echo_block = False
            continue

        if in_echo_block:
            # 在echo块内部：转为echo语句
            if not line.strip():
                # 空行输出echo ""
                result_lines.append('echo ""')
            else:
                escaped = line.replace('"', '\\"')
                result_lines.append(f'echo "{escaped}"')
        else:
            # 不在echo块：原样写入，直接作为bash执行代码
            result_lines.append(line)

    return "\n".join(result_lines)


def parse_md_to_modules(md_text: str):
    """
    解析markdown：识别 <!-- @force-run --> 在 ## 上方，标记强制执行模块
    返回：[{"title":"xxx","script":"xxx","force_run":bool}]
    """
    section_pattern = re.compile(r"^##\s+(.*)$", re.MULTILINE)
    matches = list(section_pattern.finditer(md_text))
    modules = []
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start_pos = match.start()
        end_title = match.end()
        pre_chunk = md_text[:start_pos]
        if idx > 0:
            prev_end = matches[idx - 1].end()
            pre_chunk = md_text[prev_end:start_pos]
        force_run = bool(re.search(r"<!--\s*@force-run\s*-->", pre_chunk))
        if idx + 1 < len(matches):
            end_pos = matches[idx + 1].start()
        else:
            end_pos = len(md_text)
        section_content = md_text[end_title:end_pos]
        bash_blocks = re.findall(r"```bash\n(.*?)\n```", section_content, re.DOTALL)
        merged_script = "\n".join(bash_blocks)
        modules.append(
            {"title": title, "script": merged_script, "force_run": force_run}
        )
    return modules


def check_single_file_title_sync(current_modules, saved_file_modules):
    """单md文件title校验：返回是否需要重置该文件的选择 True=需要重置"""
    if saved_file_modules is None:
        return False
    curr_titles = {m["title"] for m in current_modules}
    saved_titles = {m["title"] for m in saved_file_modules}
    return curr_titles != saved_titles


def save_profile(mode: str, file_entries: list):
    """
    保存profile，mode: install / uninstall
    file_entries: [{"filename":"xxx.md","enabled":bool,"modules":[...]}]
    force‑run模块强制selected=True
    """
    payload = {}
    if CONFIG_SAVE_PATH.exists():
        try:
            with open(CONFIG_SAVE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            payload = {}
    if "profiles" not in payload:
        payload["profiles"] = {}
    profile_data = []
    for fe in file_entries:
        mod_list = []
        for m in fe["modules"]:
            if m.get("force_run"):
                mod_list.append({"title": m["title"], "selected": True})
            else:
                mod_list.append({"title": m["title"], "selected": m["selected"]})
        profile_data.append(
            {"filename": fe["filename"], "enabled": fe["enabled"], "modules": mod_list}
        )
    payload["profiles"][mode] = {"file_entries": profile_data}
    with open(CONFIG_SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_profile(mode: str):
    """读取指定mode的profile；返回 None / {"file_entries":[...]}"""
    if not CONFIG_SAVE_PATH.exists():
        return None
    try:
        with open(CONFIG_SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        prof = data.get("profiles", {}).get(mode)
        return prof
    except Exception:
        return None


def parse_env_text(env_text: str):
    env = {}
    for line in env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def gen_env_export_lines(env_dict: dict):
    """
    HOST_*_PATH → 仅host脚本
    CONTAINER_*_PATH → 仅container脚本
    其余变量两边都导出
    """
    host_lines = []
    container_lines = []
    for k, v in env_dict.items():
        is_host_path = k.startswith("HOST_") and k.endswith("_PATH")
        is_container_path = k.startswith("CONTAINER_") and k.endswith("_PATH")
        if is_host_path:
            host_lines.append(f'export {k}="{v}"')
        elif is_container_path:
            container_lines.append(f'export {k}="{v}"')
        else:
            host_lines.append(f'export {k}="{v}"')
            container_lines.append(f'export {k}="{v}"')
    return host_lines, container_lines


def dialog_checklist(title_text, items):
    """
    items: [{"label":"xxx","selected":bool,"obj":obj}]
    返回：(cancel:bool, result_items: list)
    """
    dialog_args = ["dialog", "--checklist", title_text, "20", "85", "12"]
    for idx, it in enumerate(items):
        status = "on" if it["selected"] else "off"
        dialog_args.append(str(idx))
        dialog_args.append(it["label"])
        dialog_args.append(status)
    try:
        with open("/dev/tty", "r") as tty_in, open("/dev/tty", "w") as tty_out:
            proc = subprocess.Popen(
                dialog_args,
                stdin=tty_in,
                stdout=tty_out,
                stderr=subprocess.PIPE,
                text=True,
            )
            _, stderr_data = proc.communicate()
            ret = proc.returncode
    except OSError:
        print("\n❌ dialog调用异常")
        sys.exit(1)
    if ret == 1:
        return True, items
    if ret != 0:
        print(f"\n❌ dialog返回码 {ret}，退出程序")
        sys.exit(1)
    picked_pos = set()
    picked_str = stderr_data.strip()
    if picked_str:
        picked_pos = set(int(x) for x in picked_str.split())
    for idx, it in enumerate(items):
        it["selected"] = idx in picked_pos
    return False, items


def check_container_running(ctn_name: str):
    """检查容器是否存在并且running，仅用于输出提示文案"""
    ret_exists = subprocess.run(
        ["podman", "ps", "-a", "--filter", f"name=^/{ctn_name}$"],
        capture_output=True,
        text=True,
    )
    if ctn_name not in ret_exists.stdout:
        return False
    ret_run = subprocess.run(
        ["podman", "ps", "--filter", f"name=^/{ctn_name}$"],
        capture_output=True,
        text=True,
    )
    return ctn_name in ret_run.stdout


def main():
    # ========== 前置检查 dialog ==========
    if subprocess.run(["which", "dialog"], capture_output=True).returncode != 0:
        print("❌ 未检测到 dialog 工具！")
        print("请先安装 dialog：")
        print("  sudo apt install dialog")
        print("安装完成后再重新运行 python3 run.py")
        sys.exit(1)

    print("========================================")
    print("请选择执行模式：")
    print("  1) install   安装流程 (默认回车)")
    print("  2) uninstall  清理流程")
    print("========================================")
    try:
        user_input = input("请输入选项数字 [1/2]，回车默认选1: ").strip()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户 Ctrl+C 退出程序")
        sys.exit(130)
    if user_input == "" or user_input == "1":
        mode = "install"
        scan_dir = Path("./Install")
    elif user_input == "2":
        mode = "uninstall"
        scan_dir = Path("./Uninstall")
    else:
        print(f"❌ 无效输入 {user_input}")
        sys.exit(1)

    # 仅保证output目录存在，**不再整体删除output目录，保留目录内其他旧脚本**
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 读取.env
    env_path = Path("./.env")
    if not env_path.exists():
        print(f"❌ .env 文件不存在 {env_path.resolve()}")
        sys.exit(1)
    env_text = env_path.read_text(encoding="utf-8")
    env_dict = parse_env_text(env_text)
    CONTAINER_NAME = env_dict.get("CONTAINER_NAME", "")
    HOST_DOWNLOAD_PATH = env_dict.get("HOST_DOWNLOAD_PATH", "")
    HOST_PROJECTS_PATH = env_dict.get("HOST_PROJECTS_PATH", "")

    # 扫描md文件，按文件名数字前缀排序
    md_files = list(scan_dir.glob("*.md"))

    def sort_key(p: Path):
        stem = p.stem
        dot_pos = stem.find(".")
        if dot_pos > 0:
            try:
                return int(stem[:dot_pos])
            except ValueError:
                return 9999
        return 9999

    md_files.sort(key=sort_key)
    if len(md_files) == 0:
        print(f"\nℹ️ 目录 {scan_dir.resolve()} 中未找到任何md脚本文件，无需处理")
        print("\n🎉 全部处理完成！")
        sys.exit(0)

    # 读取profile
    profile = load_profile(mode)
    saved_file_entries = profile.get("file_entries", []) if profile else []
    saved_by_filename = {fe["filename"]: fe for fe in saved_file_entries}

    work_file_entries = []
    for md_path in md_files:
        fname = md_path.name
        md_text = md_path.read_text(encoding="utf-8")
        curr_modules = parse_md_to_modules(md_text)
        if len(curr_modules) == 0:
            print(f"⚠️ {fname} 未解析到##模块，跳过")
            continue
        saved_fe = saved_by_filename.get(fname)
        need_reset_this_file = check_single_file_title_sync(
            curr_modules, saved_fe["modules"] if saved_fe else None
        )

        # 初始化enabled
        if saved_fe is not None and not need_reset_this_file:
            enabled = bool(saved_fe.get("enabled", True))
        else:
            enabled = True

        selections = []
        for m in curr_modules:
            sm = None
            if saved_fe and not need_reset_this_file:
                for s in saved_fe["modules"]:
                    if s["title"] == m["title"]:
                        sm = s
                        break
            if m["force_run"]:
                sel = True
            else:
                if need_reset_this_file or sm is None:
                    sel = True
                else:
                    sel = bool(sm["selected"])
            selections.append(
                {
                    "title": m["title"],
                    "script": m["script"],
                    "force_run": m["force_run"],
                    "selected": sel,
                }
            )
        work_file_entries.append(
            {
                "filename": fname,
                "md_path": md_path,
                "enabled": enabled,
                "modules": selections,
            }
        )

    # ========== 第一级dialog：选择md文件总开关 ==========
    file_dialog_items = []
    for fe in work_file_entries:
        file_dialog_items.append(
            {"label": fe["filename"], "selected": fe["enabled"], "obj": fe}
        )
    cancel, file_dialog_items = dialog_checklist(
        "【第一级】选择要启用的md文件", file_dialog_items
    )
    if cancel:
        print("\n⚠️ 用户取消选择，程序退出")
        sys.exit(0)
    for it in file_dialog_items:
        it["obj"]["enabled"] = it["selected"]

    # ========== 遍历每个启用的md，弹出第二级dialog，仅普通非force‑run模块 ==========
    for fe in work_file_entries:
        if not fe["enabled"]:
            continue
        # 分离force_run模块与普通模块
        all_mods = fe["modules"]
        normal_mods = [m for m in all_mods if not m["force_run"]]
        force_mods = [m for m in all_mods if m["force_run"]]
        # force_mods 固定selected=True，不进UI
        for fm in force_mods:
            fm["selected"] = True
        if len(normal_mods) == 0:
            print(f"\nℹ️ 文件 {fe['filename']}：全部为force‑run强制模块，跳过二级选择")
            continue
        # 弹出二级dialog
        second_items = []
        for nm in normal_mods:
            second_items.append(
                {"label": nm["title"], "selected": nm["selected"], "obj": nm}
            )
        title = f"【第二级】调整 {fe['filename']} 内部普通模块（force‑run模块自动执行，不显示）"
        cancel, second_items = dialog_checklist(title, second_items)
        if cancel:
            print("\n⚠️ 用户取消选择，程序退出")
            sys.exit(0)

    # 保存当前选择
    save_profile(mode, work_file_entries)

    # ========== 判断是否任何md都没有被选中 ==========
    any_enabled = any(fe["enabled"] for fe in work_file_entries)
    if not any_enabled:
        print("\nℹ️ 没有选中任何md文件，不生成任何脚本。output目录为空。")
        print("\n🎉 全部处理完成！")
        sys.exit(0)

    host_export_lines, container_export_lines = gen_env_export_lines(env_dict)
    generated_list = []

    # ========== 逐个处理md文件，全部输出到output，不再自动执行 ==========
    for fe in work_file_entries:
        fname = fe["filename"]
        md_path = fe["md_path"]
        if not fe["enabled"]:
            print(f"\nℹ️ {fname} 未启用，跳过")
            continue

        # 收集本文件选中模块脚本
        script_parts = []
        for m in fe["modules"]:
            if m["selected"] and m["script"].strip():
                script_parts.append(m["script"])

        # 边界条件：即使普通模块全部取消，只要force‑run存在，script_parts非空就生成脚本
        if len(script_parts) == 0:
            print(f"\nℹ️ {fname}：没有任何选中模块，跳过生成脚本")
            continue

        out_sh_name = Path(fname).stem + ".sh"
        out_sh_path = OUTPUT_DIR / out_sh_name

        # 判断Host / Container，用于选择头部与输出提示
        is_host = fname.endswith("Host.md")
        is_container = fname.endswith("Container.md")

        # --- 组装脚本头部打印信息块 ---
        info_lines = []
        info_lines.append(f'echo "===== 脚本文件名：{out_sh_name} ====="')
        info_lines.append('echo "    已启用模块列表："')
        for m in fe["modules"]:
            if m["selected"]:
                escaped_title = m["title"].replace('"', '\\"')
                info_lines.append(f'echo "        {escaped_title}"')
        info_echo_block = "\n".join(info_lines)

        if is_host:
            body_part = SHELL_HOST_BODY
            export_lines_this = host_export_lines
        elif is_container:
            body_part = SHELL_CONTAINER_BODY
            export_lines_this = container_export_lines
        else:
            print(f"\n⚠️ {fname} 文件名不以Host.md/Container.md结尾，跳过")
            continue

        # 脚本组装顺序：shebang → export → body_part → info打印块 → 业务脚本
        full_text = SHELL_SHEBANG + "\n"
        full_text += "\n".join(export_lines_this)
        full_text += "\n\n"
        full_text += body_part
        full_text += "\n\n"
        full_text += info_echo_block
        full_text += "\n\n"
        full_text += "\n\n# ========== 业务脚本 ==========\n".join(script_parts)

        # ==========新增：host脚本末尾追加postinstall提示文本 ==========
        if is_host:
            rendered_post = HOST_POSTINSTALL_SCRIPT.format(
                CONTAINER_NAME=CONTAINER_NAME.strip('"'),
                HOST_PODMAN_PATH=env_dict.get("HOST_PODMAN_PATH", "$HOME/Podman").strip(
                    '"'
                ),
            )

            # 处理标记：echo块转echo语句，其余原样保留可执行shell
            final_script_fragment = process_echo_marked_script(rendered_post)

            full_text += "\n\n"
            full_text += "#" + "=" * 80 + "\n"
            full_text += "# === post‑install片段（含标记自动转换echo打印） ===\n"
            full_text += final_script_fragment
            full_text += "\n"
            full_text += "#" + "=" * 80 + "\n"

        # 如果该脚本旧文件存在，只删除这单个脚本，保留output目录下其他脚本
        if out_sh_path.exists():
            out_sh_path.unlink()
        out_sh_path.write_text(full_text, encoding="utf-8")
        out_sh_path.chmod(0o755)
        generated_list.append((out_sh_name, is_host, is_container))

    # ========== 输出用户操作指引 ==========
    print("\n" + "=" * 70)
    print(f"✅ 脚本全部生成至目录：{OUTPUT_DIR.resolve()}")
    # ========== 输出用户操作指引 ==========
    print("\n" + "=" * 70)
    print(f"✅ 脚本全部生成至目录：{OUTPUT_DIR.resolve()}")
    for sh_name, is_host, is_container in generated_list:
        print(f"\n--- 输出到 output/{sh_name} ---")
    print("=" * 70)

    print("\n🎉 全部处理完成！")
    if mode == "install":
        rendered_post = HOST_POSTINSTALL_SCRIPT.format(
            CONTAINER_NAME=CONTAINER_NAME.strip('"'),
            HOST_PODMAN_PATH=env_dict.get("HOST_PODMAN_PATH", "$HOME/Podman").strip(
                '"'
            ),
        )
        print(rendered_post)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Ctrl+C，程序已退出")
        sys.exit(130)
