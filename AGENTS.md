# 学术文献转公众号/秀米草稿

本目录用于把学术论文 PDF 转成微信公众号/秀米排版草稿。实现入口见 `skills/paper-to-wechat-draft/`（SKILL.md + scripts/wechat_draft_helper.py）。

## Skill Rule: 学术文献转公众号/秀米草稿 (paper-to-wechat-draft)

当用户要求“总结文献发公众号”、“把论文排版成公众号草稿”或处理学术 PDF 排版时，严格执行以下约束：

1. **输出双交付物**：必须同时生成【全部使用内联样式的 `wechat_article.html` 文件】与【裁剪后的图表 PNG 文件夹】，严禁仅在对话框输出纯 Markdown 文本。
2. **图表全截图原则（适配秀米与微信编辑器）**：
   - 严禁使用 `page.get_images()` 提取碎裂的原始位图，必须使用 `page.get_pixmap(dpi=300, clip=rect)` 对页面区域进行渲染裁剪。
   - 论文中的所有表格（Table 1, Table 2...）必须与插图（Fig. 1, Fig. 2...）一样裁剪为 PNG 图片插入正文，**严禁在 HTML 中编写 `<table>` 标签**，确保在秀米与手机端微信中版式 100% 不变形。
3. **正文写作结构**：
   - **顶部信息卡**：中文译题、英文原标题、发表期刊与年份。
   - **01 核心速览（基于 Abstract）**：1段通俗研究背景与方法概述 + 3条带具体百分比/指标数据的核心结论。
   - **02 研究背景与痛点（基于 Introduction）**：拆解现有工程/算法瓶颈，说明本文如何解决。
   - **03 核心图表逐一精读**：按原文图表顺序，遵循“一段中文导读 + 一张高清原图/原表截图 + 居中图注说明”的排版节奏。
4. **微信内联 CSS 铁律**：所有 HTML 标签必须自带 `style="..."` 属性，不使用任何 `<style>` 标签、外部 CSS 或 Tailwind 类名。

## 执行入口

- 技能规范：`skills/paper-to-wechat-draft/SKILL.md`
- 自动化脚本：`skills/paper-to-wechat-draft/scripts/wechat_draft_helper.py`
  - 本地生成（路线 B）：`python skills/paper-to-wechat-draft/scripts/wechat_draft_helper.py --pdf 论文.pdf --out-dir crops --html wechat_article.html`
  - 可选 API 推送（路线 A，需已认证公众号）：追加 `--publish`（读 `WECHAT_APP_ID`/`WECHAT_APP_SECRET`）