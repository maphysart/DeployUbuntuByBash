import re
import subprocess
import sys
from pathlib import Path


# ===================== 首次运行准备脚本字符串（新增，放在文件最前面） =====================
FIRST_RUN_PREPARE_SCRIPT = """
        #!/bin/bash
        set -euo pipefail
        mkdir -p "$HOME/Downloads/softwares"
        mkdir -p "$HOME/Projects"
        """

# ===================== 在host中每次固定执行的内容 =====================
# 启用 set -euo pipefail，任意命令失败直接终止执行； 进入softwares目录
fixed_action = """
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive
        cd $HOME/Downloads/softwares
        """

def extract_bash_code_blocks(md_content: str) -> list[str]:
    """
          从markdown文本提取 ```bash 包裹的代码块
    """
    pattern = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)
    blocks = pattern.findall(md_content)
    return blocks

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
    # -------- 读取 env.md 配置文件 --------
    env_md_path = Path("./env.md")
    if not env_md_path.exists():
        print(f"❌ 错误：找不到环境配置文件 {env_md_path.resolve()}")
        sys.exit(1)

    # 读取全部文本，作为env_state，原样拼接到每个bash块头部
    env_state = env_md_path.read_text(encoding="utf-8")

    md_file_path = Path("install_ubuntu.md")
    if not md_file_path.exists():
        print(f"错误：找不到文件 {md_file_path.resolve()}")
        sys.exit(1)

    print(f"正在读取Markdown文件：{md_file_path}")
    md_text = md_file_path.read_text(encoding="utf-8")

    bash_blocks = extract_bash_code_blocks(md_text)
    if not bash_blocks:
        print("Markdown中未找到任何 ```bash 代码块！")
        sys.exit(0)

    print(f"一共找到 {len(bash_blocks)} 个bash代码块，准备依次执行")

    for idx, raw_code in enumerate(bash_blocks):
        try:
            # create softwares folder at first run
            if idx == 0:
                run_bash_script(FIRST_RUN_PREPARE_SCRIPT, -1)
            
            code = fixed_action + env_state + raw_code
            run_bash_script(code, idx)
        except Exception as e:
            print(f"\n❌ 执行中断：{str(e)}")
            sys.exit(1)

    print("\n🎉 所有Bash代码块全部执行完毕！")
    
    print("\n" + "="*60)
    print("⚠️ 【重要】当前终端不会自动加载新alias！请手动执行下面命令：")
    print("    source ~/.bashrc")
    print("或者关闭当前终端，新开一个终端窗口。")
    print("="*60)

if __name__ == "__main__":
    main()
