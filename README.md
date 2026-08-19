# 项目名称
这是用于在ubuntu 24.04上安装开发必需的软件，并在podman中部署AI相关工具的项目。

## 原理
run_md_bash.py 会读取env.md中的用户信息和全局变量，然后读取install_ubuntu.md中的各个bash脚本块，依次执行。

## 功能
- 自动化安装输入法，微信等。
- 在podman中搭建hermes，codex，claude code，opencodex,github cli等AI工具。

## 用法
1. 在一个全新安装的ubuntu 24.04上，首先补充 env.md中的项目，填写或修改 CONTAINER_NAME， GIT_NAME， GIT_EMAIL等。

2. 在host的终端中执行 
```bash
python3 run_md_bash.py
```
该命令会在host的home目录下，新建一个~/Podman/CONTAINER_NAME的文件夹，作为容器CONTAINER_NAME的home目录，同时将host下~/Projects目录映射到容器内。
在容器内运行hermes等软件，状态会存在~/Podman/CONTAINER_NAME中。
在用npm install安装codex等工具时，设置的npm用户私有全局目录为容器内的{HOME_DIR}/.npm-global，即使删除容器也不需要重新安装codex等工具。

3. 在host的终端中，执行
```bash
source .bashrc
```
然后执行CONTAINER_NAME， 就会进入容器内的Home目录内。

第一次在ubuntu上部署时，需要在进入容器后，执行，
```bash
gh auth login
```
流程选择：
What account do you want to log into? GitHub.com
What is your preferred protocol for Git operations? SSH
How would you like to authenticate GitHub CLI? Login with a web browser
复制设备码，浏览器打开网页完成授权。
登录完成后查看当前身份：
```bash
gh auth status
gh api user
```
之后认证信息会保存到host的~/Podman/aistack/.config/gh/下，下次加载时会自动载入，不需要再次认证。

