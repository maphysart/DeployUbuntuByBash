import re
import subprocess
import sys
import json
from pathlib import Path

# =================== INSTALLATION CONFIGURATION ===================
FIRST_RUN_PREPARE_SCRIPT_TPL = """
    #!/bin/bash
    set -euo pipefail
    mkdir -p "{DOWNLOAD_ROOT}"
    mkdir -p "{PROJECTS_ROOT}"
"""
FIXED_ACTION_TPL = """
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    cd {DOWNLOAD_ROOT}
"""
# =================== INSTALLATION CONFIGURATION ===================
CONFIG_SAVE_PATH = Path("./.run_md_config.json")


def parse_md_to_modules(md_text: str):
    """
    解析markdown：识别 <!-- @force-run --> 在 ## 上方，标记强制执行模块
    返回：[{"title":"xxx","script":"xxx","force_run":bool}]
    """
    # 匹配 ##标题位置
    section_pattern = re.compile(r"^##\s+(.*)$", re.MULTILINE)
    matches = list(section_pattern.finditer(md_text))
    modules = []

    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start_pos = match.start()
        end_title = match.end()

        # 当前 ## 标题之前的片段，查找 <!-- @force-run -->
        pre_chunk = md_text[:start_pos]
        # 取上一个 ## 之后到当前 ## 之前的内容
        if idx > 0:
            prev_end = matches[idx-1].end()
            pre_chunk = md_text[prev_end:start_pos]

        force_run = bool(re.search(r"<!--\s*@force-run\s*-->", pre_chunk))

        # 本模块内容区间
        if idx + 1 < len(matches):
            end_pos = matches[idx+1].start()
        else:
            end_pos = len(md_text)
        section_content = md_text[end_title:end_pos]

        bash_blocks = re.findall(r"```bash\n(.*?)\n```", section_content, re.DOTALL)
        merged_script = "\n".join(bash_blocks)

        modules.append({
            "title": title,
            "script": merged_script,
            "force_run": force_run
        })
    return modules


def check_module_title_sync(current_modules, saved_modules):
    """对比全部模块title集合，包含强制模块"""
    if saved_modules is None:
        return True, False
    current_titles = {m["title"] for m in current_modules}
    saved_titles = {m["title"] for m in saved_modules}
    if current_titles == saved_titles:
        return True, False
    else:
        return False, True


def save_config(md_filename: str, module_selections: list[dict]):
    """
    保存全部模块；force_run模块强制selected=True；普通模块保存用户选择
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

    out_list = []
    for sel in module_selections:
        if sel.get("force_run"):
            out_list.append({"title": sel["title"], "selected": True})
        else:
            out_list.append({"title": sel["title"], "selected": sel["selected"]})

    payload["profiles"][md_filename] = {"modules": out_list}
    with open(CONFIG_SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_config(target_md_filename: str):
    if not CONFIG_SAVE_PATH.exists():
        return None
    try:
        with open(CONFIG_SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        profiles = data.get("profiles", {})
        entry = profiles.get(target_md_filename)
        if entry is None:
            return None
        return entry["modules"]
    except Exception:
        return None


def run_bash_script(code: str, block_idx: int, module_title: str):
    print(f"\n========== 执行模块 [{module_title}] Bash 块 {block_idx + 1} ==========")
    proc = subprocess.Popen(
        ["bash"],
        stdin=subprocess.PIPE,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True
    )
    proc.communicate(input=code)
    ret_code = proc.returncode
    if ret_code != 0:
        raise RuntimeError(f"模块 [{module_title}] 执行失败！返回码: {ret_code}")
    print(f"\n✅ 模块 [{module_title}] 执行完成\n")


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


def fallback_text_select(modules, selections):
    """降级文本模式：传入的已经过滤掉force‑run模块"""
    print("\n========================================")
    print("【降级文本模式】模块选择")
    print("回车=沿用现有；编号逗号分隔例如 0,2；all全选；none全取消")
    print("========================================\n")
    for i, sel in enumerate(selections):
        mark = "[*]" if sel["selected"] else "[ ]"
        print(f"  {i:2d} {mark}  {sel['title']}")
    user_input = input("\n输入选择，回车沿用状态: ").strip()
    if not user_input:
        return selections
    new_idx = set()
    if user_input.lower() == "all":
        new_idx = set(range(len(modules)))
    elif user_input.lower() == "none":
        new_idx = set()
    else:
        try:
            parts = [int(x.strip()) for x in user_input.split(",")]
            for num in parts:
                if 0 <= num < len(modules):
                    new_idx.add(num)
        except ValueError:
            print("⚠️ 输入解析失败，沿用原有选择")
            return selections
    for idx, sel in enumerate(selections):
        sel["selected"] = idx in new_idx
    return selections


def dialog_multi_select(modules, selections):
    """dialog选择：传入的已经过滤掉force‑run模块"""
    dialog_args = ["dialog", "--checklist", "请勾选要执行的模块（空格勾选，Tab切换OK确认）", "20", "75", "12"]
    for idx, sel in enumerate(selections):
        status = "on" if sel["selected"] else "off"
        dialog_args.append(str(idx))
        dialog_args.append(sel["title"])
        dialog_args.append(status)

    try:
        with open("/dev/tty", "r") as tty_in, open("/dev/tty", "w") as tty_out:
            proc = subprocess.Popen(
                dialog_args,
                stdin=tty_in,
                stdout=tty_out,
                stderr=subprocess.PIPE,
                text=True
            )
            _, stderr_data = proc.communicate(timeout=30)
            ret = proc.returncode
    except FileNotFoundError:
        print("\n⚠️ 未找到dialog工具，切换到文本选择模式")
        return fallback_text_select(modules, selections)
    except subprocess.TimeoutExpired:
        print("\n⚠️ dialog超时卡住，降级到文本模式")
        proc.kill()
        proc.wait()
        return fallback_text_select(modules, selections)
    except OSError:
        print("\n⚠️ 当前终端不支持dialog TUI，切换文本模式")
        return fallback_text_select(modules, selections)

    if ret == 1:
        print("\n⚠️ 用户取消选择，程序退出")
        sys.exit(0)
    if ret != 0:
        print(f"\n⚠️ dialog返回码 {ret}，降级到文本模式")
        return fallback_text_select(modules, selections)

    picked_index_str = stderr_data.strip()
    picked_idx_set = set()
    if picked_index_str:
        picked_idx_set = set(int(x) for x in picked_index_str.split())
    for idx, sel in enumerate(selections):
        sel["selected"] = idx in picked_idx_set
    return selections


def main():
    print("========================================")
    print("请选择执行模式：")
    print("  1) install  执行安装流程 (默认，直接回车选择此项)")
    print("  2) clean    执行清理流程")
    print("========================================")
    try:
        user_input = input("请输入选项数字 [1/2]，回车默认选 1: ").strip()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户 Ctrl+C 退出程序")
        sys.exit(130)

    if user_input == "" or user_input == "1":
        mode = "install"
    elif user_input == "2":
        mode = "clean"
    else:
        print(f"❌ 无效输入: {user_input}，仅允许输入 1 或 2，退出程序")
        sys.exit(1)

    env_md_path = Path("./.env")
    if not env_md_path.exists():
        print(f"❌ 错误：找不到环境配置文件 {env_md_path.resolve()}")
        sys.exit(1)
    env_state = env_md_path.read_text(encoding="utf-8")
    env_dict = parse_env_text(env_state)
    PROJECTS_ROOT = env_dict["PROJECTS_ROOT"]
    DOWNLOAD_ROOT = env_dict["DOWNLOAD_ROOT"]
    PODMAN_ROOT = env_dict["PODMAN_ROOT"]

    if mode == "install":
        md_file_path = Path("install_ubuntu.md")
        FIRST_RUN_PREPARE_SCRIPT = FIRST_RUN_PREPARE_SCRIPT_TPL.format(
            DOWNLOAD_ROOT=DOWNLOAD_ROOT,
            PROJECTS_ROOT=PROJECTS_ROOT
        )
        FIXED_ACTION = FIXED_ACTION_TPL.format(
            DOWNLOAD_ROOT=DOWNLOAD_ROOT
        )
    else:
        md_file_path = Path("clean_ubuntu.md")
        FIRST_RUN_PREPARE_SCRIPT = None
        FIXED_ACTION = None

    if not md_file_path.exists():
        print(f"错误：找不到文件 {md_file_path.resolve()}")
        sys.exit(1)

    md_text = md_file_path.read_text(encoding="utf-8")
    modules = parse_md_to_modules(md_text)
    if len(modules) == 0:
        print("❌ md文件未解析到任何 ## 模块")
        sys.exit(0)

    md_filename = str(md_file_path.name)
    saved_modules = load_config(md_filename)

    _, need_reset = check_module_title_sync(modules, saved_modules)
    if need_reset:
        print(f"\n⚠️ 检测到Markdown模块标题发生变更，删除旧配置文件 {CONFIG_SAVE_PATH.name}，全部模块恢复为【默认勾选】")
        CONFIG_SAVE_PATH.unlink(missing_ok=True)
        saved_modules = None

    # 初始化全部模块的 selections
    selections = []
    for m in modules:
        saved_item = None
        if saved_modules is not None:
            for sm in saved_modules:
                if sm["title"] == m["title"]:
                    saved_item = sm
                    break
        if m["force_run"]:
            selected = True
        else:
            selected = bool(saved_item["selected"]) if saved_item is not None else True
        selections.append({"title": m["title"], "selected": selected, "force_run": m["force_run"]})

    # 提取普通（非强制）模块给UI交互
    ui_indices = [i for i, s in enumerate(selections) if not s["force_run"]]
    ui_selections = [selections[i] for i in ui_indices]

    if len(ui_selections) > 0:
        ui_selections = dialog_multi_select(modules, ui_selections)
        # 将UI选择结果回填回总selections
        for ui_pos, real_idx in enumerate(ui_indices):
            selections[real_idx]["selected"] = ui_selections[ui_pos]["selected"]
    else:
        print("\nℹ️ 当前md没有可选择模块，全部模块为强制执行")

    # 保存配置（内部自动把force_run强制写selected=True）
    save_config(md_filename, selections)

    # 组装最终执行列表，保持md原始顺序
    run_modules = []
    for idx, mod in enumerate(modules):
        sel_info = selections[idx]
        if sel_info["selected"]:
            run_modules.append(mod)

    if len(run_modules) == 0:
        print("\n⚠️ 没有选中任何模块，程序直接退出")
        sys.exit(0)

    print(f"\n✅ 将要执行 {len(run_modules)} 个模块")
    for m in run_modules:
        note = "【强制】" if m["force_run"] else ""
        print(f"    · {m['title']} {note}")

    try:
        input("\n按回车确认开始执行 ...")
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户 Ctrl+C 退出程序")
        sys.exit(130)

    if mode == "install":
        print("\n---------- 执行全局目录初始化 ----------")
        run_bash_script(env_state + FIRST_RUN_PREPARE_SCRIPT, -1, "全局初始化")

    for block_idx, mod in enumerate(run_modules):
        raw_script = mod["script"]
        if mode == "install":
            code = env_state + FIXED_ACTION + raw_script
        else:
            code = env_state + raw_script
        try:
            run_bash_script(code, block_idx, mod["title"])
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断执行，程序退出")
            sys.exit(130)
        except Exception as e:
            print(f"\n❌ 执行中断：{str(e)}")
            sys.exit(1)

    print("\n🎉 所有选中模块全部执行完毕！")
    if mode == "install":
        print("\n" + "="*60)
        print("⚠️ 【重要】当前终端不会自动加载新alias！请手动执行下面命令：")
        print("    source ~/.bashrc")
        print("或者关闭当前终端，新开一个终端窗口。")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("完成清理")
        print("="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Ctrl+C，程序已退出")
        sys.exit(130)
