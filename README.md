# ghostwriter

Markdown → Ghost → WeChat 发布管道。写一次，多处发布。

```
markdown → Ghost 博客 → 微信公众号
```

## 功能

- **发布**：Markdown 文件直接发布到 Ghost 博客（Lexical 格式，编辑器可编辑）
- **同步**：已发布的 Ghost 文章同步到微信公众号草稿箱
- **全自动**：发布后一步同步到微信

## 安装

```bash
# 从 PyPI 安装（推荐）
pip install ghostwriter-cli

# 或从源码安装（开发模式）
git clone https://github.com/yinguobing/ghostwriter.git
cd ghostwriter
pip install -e ".[dev]"
```

## 配置

支持两种配置方式（环境变量优先）：

### 方式 1：环境变量（推荐用于 CI/Docker）

```bash
export GHOSTWRITER_GHOST_API_URL="https://yinguobing.com"
export GHOSTWRITER_GHOST_ADMIN_KEY_ID="your_key_id"
export GHOSTWRITER_GHOST_ADMIN_KEY="your_hex_secret"
export GHOSTWRITER_WECHAT_APPID="your_wechat_appid"
export GHOSTWRITER_WECHAT_SECRET="your_wechat_secret"
```

### 方式 2：配置文件（适合本地使用）

```bash
# 交互式设置
ghostwriter config set ghost.api_url https://yinguobing.com
ghostwriter config set ghost.admin_key_id your_key_id
ghostwriter config set ghost.admin_key your_hex_secret
ghostwriter config set wechat.appid your_wechat_appid
ghostwriter config set wechat.secret your_wechat_secret

# 查看当前配置（密钥已脱敏）
ghostwriter config
```

配置文件保存在 `~/.config/ghostwriter/config.json`。

可选字段：
```bash
# 作者映射（Ghost Content API 不可用时的离线回退）
ghostwriter config set authors.<slug> <ghost_author_id>
```

**Ghost Admin API Key 获取：**
Ghost 后台 → Settings → Advanced → Integrations → Add custom integration → 复制 `Admin API Key`（格式为 `key_id:hex_secret`，拆成两段填入）

**微信 AppID/Secret 获取：**
[微信公众平台](https://mp.weixin.qq.com) → 设置与开发 → 基本配置

## 用法

### 列出 Ghost 文章

```bash
ghostwriter list
```

### 发布 Markdown 到 Ghost

```bash
# 直接发布
ghostwriter publish article.md

# 指定标题和标签
ghostwriter publish article.md --title "我的文章" --tags Ghost,开源

# 指定作者（slug，默认 xiaohei）
ghostwriter publish article.md --author guobing

# 先存草稿
ghostwriter publish article.md --draft

# 发布后自动同步到微信
ghostwriter publish article.md --wechat
```

### 同步 Ghost 文章到微信草稿

```bash
# 先列出文章获取 ID
ghostwriter list

# 同步指定文章
ghostwriter <article-id>

# 预览 HTML（不创建草稿）
ghostwriter --preview <article-id>
```

## 管道说明

### Markdown → Ghost（`publish` 命令）

将 Markdown 文件转换为 Ghost 的 **Lexical 格式**（基于 `@tryghost/kg-lexical-html-renderer`），支持：

- 标题（h1~h6）
- 段落、粗体、斜体、行内代码、链接
- 围栏代码块（带语言标记）
- 表格（以 HTML card 渲染）
- 有序/无序列表
- 分割线

转换后的文章在 Ghost 编辑器里可以正常编辑。

### Ghost → 微信（`sync` 命令）

从 Ghost API 获取文章 HTML，经过多层处理管道后推送到微信公众号草稿箱：

1. 图片上传到微信永久素材，替换为 CDN 地址
2. 白名单三层过滤（标签/属性/样式）
3. 代码块保护与恢复
4. 微信不支持的标签转换（table → div, ol/ul → 前缀段落, hr → 分隔线）
5. 默认样式补全

## 项目结构

```
ghostwriter/
├── pyproject.toml          # 项目元数据、构建配置
├── src/ghostwriter/        # 源码包
│   ├── cli.py              # CLI 入口与命令分发
│   ├── config.py           # 配置文件加载
│   ├── ghost.py            # Ghost Admin API 客户端
│   ├── wechat.py           # 微信公众号 API 客户端
│   ├── cleaner.py          # HTML 白名单过滤器
│   ├── pipeline.py         # Ghost → 微信 HTML 处理管道
│   ├── lexical.py          # Markdown → Ghost Lexical 转换器
│   └── normalize.py        # Unicode 标题规范化
├── tests/                  # 单元测试（pytest，74个）
└── docs/                   # 项目页面
```

## 注意事项

- 微信草稿标题限制：Unicode 特殊字符（弯引号、破折号等）会触发 45003 错误，脚本会自动处理
- 作者字段在微信公众号中限制 8 字节
- 代码块使用 `<pre>` + 语言标签的样式方案，微信中可用
- `--wechat` 参数需要在 Ghost API 中能通过 slug 查到刚发布的文章
