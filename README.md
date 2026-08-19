# 项目名称
这是用于在ubuntu 24.04上安装开发必需的软件，并在podman中部署AI相关工具的项目。

## 原理
run_md_bash.py 会读取env.md中的用户信息和全局变量，然后读取install_ubuntu.md中的各个bash脚本块，依次执行。

## 功能
- 自动化安装输入法，微信等。
- 在podman中搭建hermes，codex，claude code，opencodex等AI工具。

## 用法
1. 在一个全新安装的ubuntu 24.04上，首先补充 env.md中的项目。
2. 在终端中执行 
```bash
python3 run_md_bash.py
```
