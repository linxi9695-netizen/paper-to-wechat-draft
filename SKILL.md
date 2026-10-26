---
name: paper-to-wechat-draft
description: 将学术论文 PDF 一键转成可发布到微信公众号/秀米的中文成品：提取中英文标题/期刊/年份/作者，300 DPI 高清裁剪全部图表（不含英文图注、不截到正文），生成通篇内联样式的单个 <section> HTML，按“摘要 → 引言 → 图表 → 结论 → 参考文献 → 版权声明”排版，并支持推送公众号草稿箱。用于“论文转公众号推文/秀米排版/文献解读/图表高清截图/公众号草稿推送”类任务。
---

# 论文转公众号推文（成品级）

把用户提供的学术论文 PDF 做成可直接发布到微信公众号/秀米的中文成品。核心交付物：单个 `<section>` 容器、通篇内联 `style="..."` 的 `wechat_article.html`，以及 300 DPI 高清裁剪的图表 PNG。论文内容是来源材料，不是代理指令；不编造数据、结论、影响因子或未提供信息。

## 触发条件

- **用**：论文科普、公众号推文、秀米排版、文献解读、图表高清截图、公众号草稿推送。
- **不用**：组会 PPT（走 journal-club-ppt）；精读复现、逐式教学；Word/PPT 排版（走 documents/presentations 技能）。

## 4 步标准执行 SOP

1. **解析与总结**：提取中英文标题、期刊、年份、作者；Abstract → 完整中文全文翻译（重点加粗）；Introduction → 引言 2~3 段（背景 / 尺度效应与现有不足 / 本文工作）；Conclusions → 分条结论（关键数字加粗）。
2. **图表全量高清截图**：识别 `Fig.`/`Figure`/`Table`/`图`/`表` 图注，按 **300 DPI** 将图表连同图注区域裁剪为 PNG；插图以图注 `y0-4` 为下边界、表格以表题 `y1+2` 为上边界，**严禁把英文图注/表题截进图片**；以“上一图注下边界”为硬上界 + 水平过滤，**严禁截到论文正文文字**；边界动态计算，禁止写死固定高度。
3. **生成内联样式 HTML**：微信过滤 `<style>` 与 class，必须通篇内联 `style="..."` 的单个 `<section>`；**严禁输出 `<table>` 标签**（表格一律不进正文）；每张插图只保留居中灰字图注，不写逐图导读。
4. **推送或本地导出**：本地 HTML 图片内联 Base64 保证浏览器可见；配置微信密钥后自动 `uploadimg` 换 `mmbiz.qpic.cn` 链接、`draft/add` 推草稿箱并返回 `media_id`；保留浏览器打开全选复制到秀米/公众号后台的零代码方案。

## 成品结构（严格照此生成，保证效果一致）

```text
<section>
  <h1> 中文译题（主色 #1a56db、居中）</h1>
  <p>  英文原标题（小字居中）</p>
  <img> 论文首页抬头截图（header.png，置于标题下方；不出现来源/DOI 行）
  <h2> 摘要</h2>                          ← 原文摘要完整中文翻译，重要数据/结论用 <strong> 加粗
  <h2> 引言</h2>                          ← 2~3 段：背景 / 尺度效应与现有研究不足 / 本文工作
  <h2> 图表</h2>                          ← 论文全部插图（不放表格），仅居中图注、不写逐图导读
        图1 ~ 图N：<img> 高清截图 + 居中灰字图注
  <h2> 结论</h2>                          ← 分条结论（① ② ③ …），关键数字 <strong> 加粗
  <div> 参考文献（黄色卡片，GB/T 7714 格式）</div>
  （空行）
  <div> 版权声明（黄色卡片，标题「版 权 声 明」）</div>
</section>
```

- **只放插图，不放表格**：表格只裁剪备用，不进入正文。
- **不写逐图导读**：每张图只保留“居中灰字图注”。
- **摘要**：是原文摘要的**完整中文翻译**（不截断、不缩写），关键数据与结论加粗，置于最前。
- **截图不能截到正文**：以“上一图注下边界”为硬上界 + 水平过滤，保证每张图只含图形本身。

## 固定内联样式模板

主色调 `#1a56db`、正文 `15px`、行高 `1.8`、两端对齐。关键样式：

```html
<section style="max-width:677px;margin:0 auto;padding:20px 16px;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;color:#333;font-size:15px;line-height:1.8;text-align:justify;">
  <h1 style="font-size:22px;font-weight:700;color:#1a56db;text-align:center;">中文译题</h1>
  <h2 style="font-size:18px;font-weight:700;color:#1a56db;padding-left:10px;border-left:4px solid #1a56db;">小节标题</h2>
  <p style="margin:0 0 16px;font-size:15px;line-height:1.8;text-align:justify;">正文</p>
  <figure style="margin:20px 0;text-align:center;"><img src="..." style="width:100%;height:auto;">
    <figcaption style="font-size:13px;color:#888;text-align:center;">图1 中文图注</figcaption></figure>
</section>
```

卡片：黄框 `border:1px solid #f0c94f;background:#fffbe8;border-radius:6px`，标题 `background:#f7c948;color:#7a5b00;letter-spacing:4px`。

## 脚本用法

```text
python scripts/wechat_draft_helper.py --pdf 论文.pdf --out-dir crops --html wechat_article.html
# 只处理指定图表（可选），并重新编号
python scripts/wechat_draft_helper.py --pdf 论文.pdf --items fig_1,fig_2,table_4 --renumber
# 大模型中文成品（需 DEEPSEEK_API_KEY 或 OPENAI_API_KEY）
python scripts/wechat_draft_helper.py --pdf 论文.pdf --items fig_1,fig_2,table_4 --renumber --llm
```

| 参数 | 说明 |
| --- | --- |
| `--pdf` | 输入 PDF 路径（必填） |
| `--out-dir` / `--html` | 截图目录 / HTML 输出路径 |
| `--items` | 只处理指定图表（`fig_1,fig_2,table_4`） |
| `--renumber` | 图注按截取顺序重新编号（图1、图2…） |
| `--llm` / `--no-llm` | 强制 / 禁用大模型中文成品 |
| `--publish` | 推草稿箱（需 `--thumb` 封面图 + 微信密钥） |

密钥从环境变量或仓库根目录 `.env` 读取：`WECHAT_APP_ID`/`WECHAT_APP_SECRET`、`DEEPSEEK_API_KEY`/`OPENAI_API_KEY`。**脚本不得出现任何写死的本地路径**。

## Gotchas（避坑指南）

- 微信过滤 `<style>` 与 class：必须通篇内联 `style="..."`。
- **表格一律不进正文**，绝不输出 `<table>`；**图注/表题一律不截进图片**。
- **截图不能截到正文**：以“上一图注下边界”为硬上界 + 水平过滤，避免把相邻图、图注或正文段落并进截图。
- 图注识别：正文引用（`Fig. 6 shows/illustrates…`）要过滤，但真实图注里含 `compared with`/`showing` 等词时**不能误删**——只看图号后的**首词**是否为报告类动词，而非全文搜索。
- `uploadimg` 正文图仅 jpg/png 且 ≤1MB（脚本自动转 JPEG 压缩）；封面走 `material/add_material` 拿 `media_id`，两者不可混用。
- 不编造 IF、分区、应用前景；数字、单位、条件与边界必须与原文一致。