# KBOT — 新版核心与 Home 入口

基于 `HKU_CoLearning_KBot_Formal_v8.1_knowledge_rule_fix_v2`，加入旧平台的 `home_app`。核心目录名保留为 `HKU_CoLearning_KBot_Formal_v8.0.13`，只补了统一入口的代理路径适配。

## 获取代码和模型

先安装 Git、Git LFS 和 Docker Compose，然后：

```bash
git lfs install
git clone https://github.com/song39592/KBOT.git
cd KBOT
git lfs pull
```

模型权重通过 Git LFS 管理，约 438 MB。不要仅使用网页 Download ZIP 来代替完整克隆。模型存在不代表语义检索已启用，相关依赖在核心目录的 `requirements-semantic.txt`；默认 Dockerfile 仍采用上游普通依赖，未擅自改动。

## 私有配置

真实 `.env`、API Token、用户数据库、上传课件和日志不进入 Git。已有部署可通过私密渠道将配置复制到对应位置；新部署可使用示例：

```bash
cp .env.example .env
cp HKU_CoLearning_KBot_Formal_v8.0.13/.env.example HKU_CoLearning_KBot_Formal_v8.0.13/.env
```

修改外层 `.env` 的 `MYSQL_ROOT_PASSWORD`（建议使用随机十六进制密码），以及核心 `.env` 的应用密钥、知识库读写密钥和自己的 Coze 配置。不使用 Coze 时设置 `COZE_ENABLED=false`。不要提交实际配置文件。

## Ubuntu / Docker 部署

在仓库最外层运行，不使用核心目录内的独立 Compose 示例：

```bash
chmod 644 HKU_CoLearning_KBot_Formal_v8.0.13/migrations/mysql_init.sql
sudo docker compose config --quiet
sudo docker compose --parallel 1 build
sudo docker compose up -d
sudo docker compose ps -a
```

VM 浏览器入口：http://127.0.0.1:13000/ 。数据库迁移服务 `migrate` 显示 `Exited (0)` 为正常。

教师账号可按新版方式创建：

```bash
sudo docker compose exec teacher python scripts/create_teacher.py your_username
```

需要代理时按各自网络配置 Docker 和构建代理，不要照搬其他电脑的 IP。Tailscale 设备身份与认证状态不放进代码仓库；公网入口应按团队账号单独部署。

## 同学之间同步

```bash
git pull --ff-only
git lfs pull
```

修改代码建议使用自己的分支，再通过 Pull Request 合并。更新代码后重新构建并启动对应服务；不要执行 `docker compose down -v` 来更新代码，因为会删除数据卷。

## 范围与验证

保留上游模型、解析、检索、出题和评分实现，仅对 6 个后端/模板文件补统一入口兼容；Home 来自旧完整平台。不包含旧独立数学解题应用或旧教师管理扩展。该最小适配版已在 Ubuntu VirtualBox 上由部署者完成页面、课程练习、公网和重启验收；真实 AI 与语义索引状态需在各自环境单独确认。
