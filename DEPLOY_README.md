# 新版核心 + 原 Home（最小适配版）

本包以 HKU_CoLearning_KBot_Formal_v8.1_knowledge_rule_fix_v2 原包为准：完整保留核心目录的全部 277 个文件，包括 23 个模型文件、原 .env、API 配置、数据和测试文件。仅修改 6 个文件，补上 Home 所需的 /student 和 /teacher 代理前缀、请求 URL、跳转和 Cookie 路径。没有修改解析、检索、出题、评分算法，也没有恢复旧教师管理功能。

home_app 从旧完整平台直接复制。最外层 .env 也从旧完整平台原样复制；核心 .env 从新版原包原样保留，两者不是同一个文件。没有重置、清空或生成任何 Token。不要将本包作为无密钥的公开源码包分享。

PRESERVATION_CHECK.json 列出核心原文件哈希和 6 个修改文件。模型总计约 439 MB（未压缩）。保留模型不等于已验证向量检索启用：新版原有 requirements、语义依赖和配置均未改变，应在 VM 检查实际 health 状态。

## Ubuntu 部署

将 ZIP 放到 /home/yangjs，执行：

```bash
cd ~
unzip KBot_v81_Core_Home.zip
cd ~/KBot_v81_Core_Home
sudo docker compose config --quiet
sudo env HTTP_PROXY=http://192.168.91.1:7890 HTTPS_PROXY=http://192.168.91.1:7890 NO_PROXY=localhost,127.0.0.1,::1 \
  docker compose --parallel 1 build \
  --build-arg HTTP_PROXY=http://192.168.91.1:7890 \
  --build-arg HTTPS_PROXY=http://192.168.91.1:7890
sudo docker compose up -d
sudo docker compose ps -a
```

代理沿用你之前的地址，需要 Windows 代理仍开启；无需代理时直接 docker compose --parallel 1 build。

在 Ubuntu 浏览器打开 http://127.0.0.1:13000/ ，由 Home 进入两个新版网站。项目名 kbot-v81-home，独立 Docker 数据卷，不覆盖已有运行平台。不运行内层的原始 docker-compose.yml。

包内已有文件完整保留，但本机旧容器的数据不会自动迁移到这套独立 Docker 数据卷。以新部署实际账号和课件状态为准。

## 测试与公网

验证注册/登录、课件上传、出题、提交评分、记录、问答和教师导出。需要 CLI 创建教师时：

```bash
sudo docker compose exec teacher python scripts/create_teacher.py yangjs
```

本包保留新版创建教师脚本，不支持旧版 --admin 参数。不添加旧数学解题独立应用或旧教师 Portal；范围为新版核心 + 旧 Home。

验收后，可以将 Tailscale Funnel 转发到 http://127.0.0.1:13000 。团队最终使用的账号和域名按老师的共享 Gmail 要求配置。

所有常驻服务设为 unless-stopped，migrate 正常应 Exited (0)；Docker 开机启动使用 sudo systemctl enable docker。

## 已完成的检查与限制

- 核心 .env、模型和除 6 个适配文件外的核心文件逐文件 SHA256 对比原 ZIP。
- Flask 冒烟测试：学生静态资源、注册与跳转；教师登录、注册链接、首页与导出路径。
- Node Home 实际启动的代理测试：首页、重定向、请求正文与前缀头。
- 本机未运行 Docker/MySQL、真实外部 AI 或语义模型推理；必须在 VM 完成运行验收。
- 未沿用上一个整合包的算法修改或测试修改，本包不宣称原包全部回归测试通过。
