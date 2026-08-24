import re
import subprocess
import sys
from pathlib import Path

# =================== INSTALLATION CONFIGURATION ===================
'''
首次运行准备脚本字符串（新增，放在文件最前面）
后续读取env.md后再替换路径变量
'''
FIRST_RUN_PREPARE_SCRIPT_TPL = """
    #!/bin/bash
    set -euo pipefail
    mkdir -p "{DOWNLOAD_ROOT}"
    mkdir -p "{PROJECTS_ROOT}"
"""

'''
在每个脚本块前，固定执行的内容
后续读取env.md后再替换路径变量
'''
# 启用 set -euo pipefail，任意命令失败直接终止执行； 进入softwares目录
FIXED_ACTION_TPL = """
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    cd {DOWNLOAD_ROOT}
"""
# =================== INSTALLATION CONFIGURATION ===================


def extract_bash_code_blocks(md_content: str) -> list[str]:
    """
          从markdown文本提取 ```bash 包裹的代码块
    """
    pattern = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)
    blocks = pattern.findall(md_content)
    return blocks

def parse_env_text(env_text: str):
    """简单解析env.md文本，提取key=value"""
    env = {}
    for line in env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def run_bash_script(code: str, block_idx: int):
    print(f"\n========== 开始执行 Bash 块 {block_idx + 1} ==========")

    proc = subprocess.Popen(
        ["bash"],
        stdin=subprocess.PIPE,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True
    )
    # 将代码送入bash标准输入
    proc.communicate(input=code)
    ret_code = proc.returncode

    if ret_code != 0:
        raise RuntimeError(f"Bash代码块执行失败！返回码: {ret_code}")

    print(f"\n✅ 第 {block_idx + 1} 个代码块执行完成\n")

def main():   
    # 交互选择数字，1=install(默认), 2=clean
    print("========================================")
    print("请选择执行模式：")
    print("  1) install  执行安装流程 (默认，直接回车选择此项)")
    print("  2) clean    执行清理流程")
    print("========================================")
    user_input = input("请输入选项数字 [1/2]，回车默认选 1: ").strip()

    if user_input == "" or user_input == "1":
        mode = "install"
    elif user_input == "2":
        mode = "clean"
    else:
        print(f"❌ 无效输入: {user_input}，仅允许输入 1 或 2，退出程序")
        sys.exit(1)
    
    # -------- 读取 env.md 配置文件 --------
    env_md_path = Path("./env.md")
    if not env_md_path.exists():
        print(f"❌ 错误：找不到环境配置文件 {env_md_path.resolve()}")
        sys.exit(1)

    # 读取全部文本，作为env_state，原样拼接到每个bash块头部
    env_state = env_md_path.read_text(encoding="utf-8")

    # 取出路径变量
    env_dict = parse_env_text(env_state)
    PROJECTS_ROOT = env_dict["PROJECTS_ROOT"]
    DOWNLOAD_ROOT = env_dict["DOWNLOAD_ROOT"]
    PODMAN_ROOT = env_dict["PODMAN_ROOT"]

    # 根据模式选择md文件
    if mode == "install":
        md_file_path = Path("install_ubuntu.md")
        # install模式才填充INSTALLATION CONFIGURATION模板
        FIRST_RUN_PREPARE_SCRIPT = FIRST_RUN_PREPARE_SCRIPT_TPL.format(
            DOWNLOAD_ROOT=DOWNLOAD_ROOT,
            PROJECTS_ROOT=PROJECTS_ROOT
        )
        FIXED_ACTION = FIXED_ACTION_TPL.format(
            DOWNLOAD_ROOT=DOWNLOAD_ROOT
        )
    if mode == "clean":
        md_file_path = Path("clean_ubuntu.md")
        # clean模式不使用这两个模板，置为None
        FIRST_RUN_PREPARE_SCRIPT = None
        FIXED_ACTION = None

    if not md_file_path.exists():
        print(f"错误：找不到文件 {md_file_path.resolve()}")
        sys.exit(1)

    print(f"\n✅ 已选择模式: [{mode}] 正在读取Markdown文件：{md_file_path}")
    md_text = md_file_path.read_text(encoding="utf-8")
    bash_blocks = extract_bash_code_blocks(md_text)
    if not bash_blocks:
        print("Markdown中未找到任何 ```bash 代码块！")
        sys.exit(0)
    print(f"一共找到 {len(bash_blocks)} 个bash代码块，准备依次执行")

    for idx, raw_code in enumerate(bash_blocks):
        try:
            if mode == "install":
                # install模式：首次块执行初始化脚本
                if idx == 0:
                    run_bash_script(env_state + FIRST_RUN_PREPARE_SCRIPT, -1)
                # install：拼接 env_state + FIXED_ACTION + raw_code
                code = env_state + FIXED_ACTION + raw_code
                run_bash_script(code, idx)
            if mode == "clean":
                # clean模式：不执行初始化，不追加fixed_action，仅 env_state + raw_code
                code = env_state + raw_code
                run_bash_script(code, idx)
        except Exception as e:
            print(f"\n❌ 执行中断：{str(e)}")
            sys.exit(1)

    print("\n🎉 所有Bash代码块全部执行完毕！")

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
    main()
