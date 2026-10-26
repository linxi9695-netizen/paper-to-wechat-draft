# paper-to-wechat-draft

> 把一篇学术论文 PDF，一键变成可以直接发布到微信公众号 / 秀米的排版草稿。

无需手动截图、无需手动翻译图注：脚本自动按 **300 DPI** 高清裁剪全部图表（且不把英文图注截进图里）、生成**通篇内联样式**的 `wechat_article.html`，可选用大模型自动生成中文译题、核心速览、量化结论与每图导读，并支持推送到微信公众号草稿箱。

---

## ⚡ 最快上手（复制即用）

**① 一条完整安装命令**（以 Codex 为例，其它平台见下文「作为 Agent Skill 调用」）：

```bash
git clone https://github.com/linxi9695-netizen/paper-to-wechat-draft.git ~/.codex/skills/paper-to-wechat-draft && pip install -r ~/.codex/skills/paper-to-wechat-draft/requirements.txt
```

**② 一条给 Agent 的示例指令**：

> 使用 paper-to-wechat-draft 技能，把这篇论文 PDF 转成公众号草稿：只保留插图、不要表格，按“摘要 → 引言 → 图表 → 结论 → 参考文献 → 版权声明”排版，图表截图不要截进论文正文文字。

## 📝 完整使用提示词（直接复制给 Agent）

```text
使用 paper-to-wechat-draft 技能，把这篇论文 PDF 转成公众号草稿：
1. 只保留插图、不要表格；
2. 结构按“摘要 → 引言 → 图表 → 结论 → 参考文献 → 版权声明”排版；
3. 摘要为原文摘要的完整中文翻译，关键数据加粗；引言分 2~3 段；结论分条、关键数字加粗；
4. 图表只放全部插图，每张仅“居中灰字图注”，不写逐图导读；
5. 图表截图不要截进论文正文文字；
6. 最终输出：内联样式的 wechat_article.html + 300 DPI 的 crops/ 截图文件夹。
```

> 想“精读模式”只保留部分核心图表，可在这条提示词后补一句：“只保留核心图表并重新编号”。

## ✨ 功能亮点

- **首页抬头截图**：自动裁剪论文第 1 页「Full Length Article / 标题 / 作者 / 单位」作为文章头图 `header.png`。
- **图表全量高清截图**：识别 `Fig.` / `Figure` / `Table` / `图` / `表` 图注，按 300 DPI 连同图注区域裁剪；插图不含英文图注、表格不含英文表题；边界由矢量+位图动态连通域聚类计算，不写死高度，避免“切顶/切边”。
- **不漏图不跳号**：支持跨行图注，按号升序输出并打印检测清单，断号自动提示。
- **内联样式 HTML**：单 `<section>` 容器、通篇 `style="..."`，微信/秀米复制粘贴不乱版；图片本地预览用 Base64 内联，永不“丢图”。
- **大模型中文成品（可选）**：配置 DeepSeek/OpenAI 密钥后，自动生成中文译题、150~250 字核心速览、3 条量化结论、引言三段式、每图中文图注与导读。
- **微信草稿箱推送（可选）**：`uploadimg` 换 `mmbiz.qpic.cn` 链接 → `draft/add` 推草稿箱并返回 `media_id`。
- **精读模式**：`--items` 只选核心图表 + `--renumber` 重新编号，产出简洁的深度精读版。

## 🚀 快速安装（3 步）

```bash
# 1. 克隆仓库
git clone https://github.com/linxi9695-netizen/paper-to-wechat-draft.git paper-to-wechat-draft
cd paper-to-wechat-draft

# 2. 安装依赖（Python 3.9+）
pip install -r requirements.txt

# 3. （可选）配置密钥
cp .env.example .env   # 填入 WECHAT_APP_ID / DEEPSEEK_API_KEY 等
```

## 🖥 命令行使用

```bash
# 基础：裁剪全部图表 + 生成脚手架 HTML
python scripts/wechat_draft_helper.py --pdf 论文.pdf --out-dir crops --html wechat_article.html

# 精读模式（推荐）：只选核心图表，并重新编号
python scripts/wechat_draft_helper.py --pdf 论文.pdf \
  --items fig_1,fig_2,fig_4,fig_7,fig_9,table_4,fig_13 --renumber

# 大模型中文成品：自动翻译图注、生成速览/结论/导读
python scripts/wechat_draft_helper.py --pdf 论文.pdf --items fig_1,fig_2,table_4 --renumber --llm

# 推送草稿箱：自动上传图片换微信图床链接，并创建草稿
python scripts/wechat_draft_helper.py --pdf 论文.pdf --publish --thumb cover.jpg
```

产物：

- `wechat_article.html` —— 可直接复制粘贴的成品
- `crops/` —— `header.png` + `fig_XX.png` + `table_XX.png` 高清截图
- `manifest.json` —— 结构化抽取结果（图号清单、英文原注、文件路径）

## 🤖 作为 Agent Skill 调用

本仓库是一个标准的 Agent Skill，可被 Codex / Claude Code / Cursor 等加载：

| 平台 | 安装方式 |
| --- | --- |
| **Codex** | 将本目录放入 `~/.codex/skills/paper-to-wechat-draft`（或项目内 `skills/`），Skill 的 `SKILL.md` 会自动被识别 |
| **Claude Code** | 放入 `~/.claude/skills/paper-to-wechat-draft`，或写入项目级 `.claude/skills/` |
| **Cursor** | 作为项目规则：把 `SKILL.md` 内容复制进 `.cursor/rules/`，或直接让 Agent 执行 `scripts/wechat_draft_helper.py` |

加载后，只需对 Agent 说一句：

> 把这篇论文 PDF 转成公众号草稿，精读模式，只留核心图表并重新编号。

Agent 会按 `SKILL.md` 固化好的标准执行，产出与调试版一致的效果。

## 🌐 通用版提示词（可粘贴为 System Prompt，适用于任意 Agent）

不依赖 SKILL.md 自动发现的平台（ChatGPT Work / DeepSeek harness / 通用 Agent 等），把下面整段贴进「系统提示 / 自定义指令」即可：

```text
# 角色：学术论文转公众号/秀米草稿助手（paper-to-wechat-draft）

当用户要求“论文转公众号推文 / 把论文排版成公众号草稿 / 文献解读 / 图表截图 / 推公众号草稿箱”时，严格按以下标准执行。

## 一、先跑脚本
1. 确保已安装依赖：pip install -r requirements.txt
2. 提取并裁剪图表：
   python scripts/wechat_draft_helper.py --pdf 论文.pdf --out-dir crops --html wechat_article.html
   （精读模式可选：--items fig_1,fig_2 --renumber）

## 二、成品结构（按此排版）
- 单个 <section> 容器，通篇内联 style="..."。
- 标题（中文译题，主色 #1a56db 居中）→ 英文原标题（小字）→ 首页抬头截图 header.png（置于标题下，不出现来源/DOI 行）。
- 摘要：原文摘要的完整中文翻译，重要数据/结论用 <strong> 加粗。
- 引言：2~3 段（背景 / 尺度效应与现有不足 / 本文工作）。
- 图表：论文全部插图（不放表格），每张仅“居中灰字图注”，不写逐图导读。
- 结论：分条结论（①②③…），关键数字 <strong> 加粗。
- 文末：【参考文献】黄色卡片（GB/T 7714 格式）→（空行）→【版权声明】黄色卡片（标题“版 权 声 明”）。

## 三、图表截图铁律
- 300 DPI，用 page.get_pixmap(dpi=300, clip=rect) 渲染裁剪，严禁用 page.get_images() 提取碎裂位图。
- 插图以图注 y0-4 为下边界、表格以表题 y1+2 为上边界，英文图注/表题一律不截进图。
- 以“上一图注下边界”为硬上界 + 水平过滤，不把相邻图/图注/正文截进图。
- 表格一律不进入正文，绝不输出 <table> 标签。

## 四、微信内联 CSS 铁律
- 所有标签自带 style="..."，禁用 <style>、外部 CSS、Tailwind 类名。
- 主色 #1a56db、正文 15px、行高 1.8、两端对齐。

## 五、避坑
- 不编造数据/IF/分区；数字、单位、条件与原文一致。
- 图注识别：正文“Fig. 6 shows…”要过滤，但真实图注含“compared with”不能误删（只看图号后首词是否为报告类动词）。
- 本地 HTML 图片用 Base64 内联；配置 WECHAT_APP_ID/SECRET 时，用 uploadimg 换 mmbiz.qpic.cn，再 draft/add 推草稿箱。

## 六、最终交付
- wechat_article.html（内联样式，可直接复制进公众号/秀米）
- crops/ 高清截图文件夹
```

## 🔑 微信公众号草稿箱自动推送配置

1. 在公众号后台「设置与开发 → 基本配置」获取 **AppID** 与 **AppSecret**，并把运行机器的公网 IP 加入「IP 白名单」。
2. 需使用**已微信认证**的公众号（认证订阅号或服务号；个人订阅号无法认证，无此接口权限）。
3. 在仓库根目录 `.env` 中填写：

```dotenv
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret

# 可选：大模型翻译（DeepSeek 为 OpenAI 兼容接口）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

4. 运行：

```bash
python scripts/wechat_draft_helper.py --pdf 论文.pdf --publish --thumb cover.jpg
```

脚本会：上传所有截图 → 换 `mmbiz.qpic.cn` 链接 → 生成 `wechat_article.wechat.html` → 创建草稿并返回 `media_id`。

> **零代码方案**（任何账号类型都适用）：直接双击打开 `wechat_article.html`，`Ctrl+A` 全选复制，粘贴到公众号后台编辑器或秀米即可。

## 📁 目录结构

```
paper-to-wechat-draft/
├── SKILL.md                    # Agent Skill 规范（触发词 + 执行标准 + 避坑指南）
├── README.md
├── requirements.txt
├── .env.example                # 密钥示例（复制为 .env 后填写）
├── .gitignore
├── agents/
│   └── openai.yaml             # Codex 界面元数据
└── scripts/
    └── wechat_draft_helper.py  # 核心自动化脚本
```

## ❓ 常见问题

- **图片复制到公众号后丢失？** 本地 HTML 已用 Base64 内联图片，浏览器打开必然可见；要 100% 在公众号显示，请配置微信密钥走 `uploadimg` 换 `mmbiz.qpic.cn` 链接。
- **个别图被切顶/切边？** 脚本按图注坐标 + 页面矢量边界动态裁剪；若极端排版仍不理想，可调整 `figure_crop_region` 中的聚类阈值（`seed_thr` / `adj_thr`）。
- **只想要某几张图？** 用 `--items fig_1,fig_3,table_2` 精读模式。
- **如何不依赖大模型？** 不配置 `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` 即可，脚本只输出英文图注脚手架，由你的 Agent 手动补中文。

## 📄 License

MIT