# 项目名称
这是用于在ubuntu 24.04上安装开发必需的软件，并在podman中部署AI相关工具的项目。

## 原理
run_md_bash.py 会读取env.md中的用户信息和全局变量，然后读取install_ubuntu.md中的各个bash脚本块，依次执行。

## 功能
- 自动化安装输入法，微信等。
- 在podman中搭建hermes，codex，claude code，opencodex,github cli等AI工具。

## 用法
### 1 填写信息
在一个全新安装的ubuntu 24.04上，首先补充 env.md中的项目，填写或修改 CONTAINER_NAME， GIT_NAME， GIT_EMAIL等。

### 2 用脚本一键安装
在host的终端中执行 
```bash
python3 run_md_bash.py
```
该命令会在host的home目录下，新建一个~/Podman/CONTAINER_NAME的文件夹，作为容器CONTAINER_NAME的home目录，同时将host下~/Projects目录映射到容器内。
在容器内运行hermes等软件，状态会存在~/Podman/CONTAINER_NAME中。
在用npm install安装codex等工具时，设置的npm用户私有全局目录为容器内的{HOME_DIR}/.npm-global，即使删除容器也不需要重新安装codex等工具。

### 3 进入容器
```bash
source .bashrc
```
然后执行CONTAINER_NAME， 就会进入容器内的Home目录内。

### 4 首次启动容器后的设置
#### 4.1 gh首次登陆
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
之后认证信息会保存到host的~/Podman/CONTAINER_NAME/.config/gh/下，下次加载时会自动载入，不需要再次认证。

#### 4.2 opencodex首次登陆
启动服务
```bash
ocx start
```
打开 http://localhost:10100 ，providers -> add provider, 选择paid，填入opencode go的api key。同时，需要删除provider中的openai(codex login)，否则会干扰调用opencode go中的gpt luna模型。需要ctrl + c 关闭，重启服务。

#### 4.3 首次启动codex
在启动codex前，需要在chatgpt官网中登陆，然后在chrome中安装插件 https://github.com/zhishile/codex-auth-helper ，将生成的 auth.json 文件放到 /home/maphysart/Podman/CONTAINER_NAME/.codex 目录下。

#### 4.4 启动claude
```bash
ocx claude
```

#### 4.5 将opencodex服务，提供给局域网内所有机器
##### 在host上
在host上，打开 /home/maphysart/Podman/CONTAINER_NAME/.opencodex/config.json 文件，在port 一行前添加一行，内容为
```code
"hostname":"0.0.0.0",
```
password，已经写入.bashrc，含有OPENCODEX_API_AUTH_TOKEN 的一行。重启ocx服务。

执行下面命令，查看ufw状态
```bash
sudo ufw status
```
如果 ufw 是 active，放行 10100/tcp：
```bash
sudo ufw allow 10100/tcp
```

##### 在局域网内任一台机器上
在以下操作中，都需要将OPENCODEX_API_AUTH_TOKEN替换为env.md中的设置，opencodex_IP替换为开启opencodex服务的机器的ip地址（如果是host自身，则为localhost）

执行下面命令，检查连接情况。
```bash
# 检查连接情况
curl -I -H "x-opencodex-api-key:OPENCODEX_API_AUTH_TOKEN"  http://opencodex_IP:10100/healthz

# 测试对话
curl -X POST http://opencodex_IP:10100/v1/chat/completions -H "Content-Type: application/json" -H "x-opencodex-api-key:OPENCODEX_API_AUTH_TOKEN" -d '{"model":"opencode-go/deepseek-v4-flash","messages":[{"role":"user","content":"hello world，请简单介绍自己"}]}'
```

注意：如果是在安装有opencodex服务的容器的机器上，以下是修改容器的home目录中的内容。
将codex目录下 config.toml.template 中的内容，替换掉 ~/.codex/config.toml 文件中的内容。 

将下面代码，写入~/.bashrc中。
```bash
export ANTHROPIC_BASE_URL="opencodex_IP:10100"
export ANTHROPIC_AUTH_TOKEN="OPENCODEX_API_AUTH_TOKEN"
```
