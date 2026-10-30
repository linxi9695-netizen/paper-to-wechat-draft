#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wechat_draft_helper.py — 学术论文 PDF -> 微信公众号/秀米成品（可开源版）。

功能：
  1. crop_paper_header：裁剪论文首页“抬头”（标题/作者/单位）为 header.png；
  2. 300 DPI 高清裁剪全部图表（插图不含英文图注、表格不含英文表题），边界由
     get_drawings() + get_image_info() 动态连通域聚类计算，避免切顶/切边；
  3. 宽松识别 Fig./Figure/Table/图/表 图注（支持跨行），按号升序并打印清单、断号提示；
  4. HTML 内联 Base64 预览；配置微信密钥时自动 uploadimg 换 mmbiz.qpic.cn；
  5. 文末内联样式【参考文献】与【版权声明】卡片；
  6. 可选大模型（DeepSeek/OpenAI 兼容接口）自动生成中文译题、速览、量化结论、背景三段式、
     每图中文图注与导读，实现“一条命令出中文成品”。

依赖：PyMuPDF、requests、python-dotenv、openai（后两者可选）。

用法：
  python scripts/wechat_draft_helper.py --pdf 论文.pdf --out-dir crops --html wechat_article.html
  # 精读模式：只选部分图表并重新编号
  python scripts/wechat_draft_helper.py --pdf 论文.pdf --items fig_1,fig_2,fig_4,table_4 --renumber
"""

from __future__ import annotations

import argparse
import base64
import html as html_lib
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

DPI = 300
WEB_DPI = 144  # 内联预览用的小尺寸渲染

SECTION_STYLE = ("max-width:677px;margin:0 auto;padding:20px 16px;"
                 "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
                 "'Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#333333;"
                 "font-size:15px;line-height:1.8;text-align:justify;box-sizing:border-box;")
H1_STYLE = "font-size:22px;font-weight:700;color:#1a56db;text-align:center;line-height:1.4;margin:0 0 8px;"
EN_TITLE_STYLE = "font-size:15px;color:#666666;text-align:center;margin:0 0 14px;font-weight:600;"
SRC_STYLE = "font-size:13px;color:#999999;text-align:center;margin:0 0 24px;"
DIGEST_BOX_STYLE = ("background:#f0f5ff;border-radius:8px;padding:16px 18px;margin:0 0 20px;"
                    "font-size:14px;line-height:1.8;color:#1f3a6b;")
H2_STYLE = ("font-size:18px;font-weight:700;color:#1a56db;margin:28px 0 12px;"
            "padding-left:10px;border-left:4px solid #1a56db;line-height:1.5;")
P_STYLE = "margin:0 0 16px;font-size:15px;line-height:1.8;text-align:justify;"
GUIDE_STYLE = "font-size:14px;color:#444444;margin:0 0 12px;text-align:justify;"
FIGURE_STYLE = "margin:20px 0;text-align:center;"
IMG_STYLE = "width:100%;height:auto;border-radius:4px;"
FIGCAP_STYLE = "font-size:13px;color:#888888;margin-top:8px;text-align:center;"
FILENAME_STYLE = "font-size:11px;color:#bbbbbb;margin-top:2px;text-align:center;"
CARD_STYLE = ("margin:20px 0;padding:14px 16px;border:1px solid #f0c94f;border-radius:6px;"
              "background:#fffbe8;")
CARD_TITLE_STYLE = ("background:#f7c948;color:#7a5b00;font-weight:700;text-align:center;"
                    "letter-spacing:4px;padding:6px 0;margin:0 0 10px;border-radius:4px;font-size:15px;")
CARD_BODY_STYLE = "font-size:14px;color:#555555;line-height:1.8;text-align:justify;margin:0;"

COPYRIGHT_TEXT = ("本文仅用于学术交流与分享，版权属于原作者/出版商。"
                  "文字翻译部分仅代表小编个人理解，如果错漏或侵权，请联系小编修改或删除。")

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_REPORT_VERBS = {
    "illustrates", "illustrated", "shows", "shown", "presents", "presented",
    "depicts", "depicted", "demonstrates", "demonstrated", "summarizes", "summarized",
    "reports", "reported", "describes", "described", "displays", "displayed",
    "reconstructs", "reconstructed", "lists", "gives", "given", "compares", "compared",
    "receives", "received",
}


def _fix_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        load_dotenv()
    except Exception:
        pass


def _import_fitz():
    for name in ("pymupdf", "fitz"):
        try:
            return __import__(name)
        except Exception:
            continue
    raise RuntimeError("缺少 PyMuPDF，请安装：pip install PyMuPDF")


def _import_requests():
    try:
        import requests  # type: ignore
        return requests
    except Exception:
        raise RuntimeError("缺少 requests，请安装：pip install requests")


_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")


def _full_to_int(s: str) -> int:
    return int(s.translate(_FULLWIDTH))


def _looks_like_body_reference(rest: str) -> bool:
    """区分“正文引用”（Fig. 6 shows/illustrates ...）与真实图注（名词短语）。"""
    r = rest.strip()
    if not r:
        return False
    if r.startswith(")"):
        return True
    body = r.lstrip(". :：").strip()
    if not body:
        return False
    if body[0].islower():
        return True
    words = [w.rstrip(".,:;()") for w in body.split()]
    if not words:
        return False
    if words[0].lower() in _REPORT_VERBS:
        return True
    if words[0].lower() in {"it", "the", "this", "these", "those", "a", "an", "as"}:
        if any(w.lower() in _REPORT_VERBS for w in words[1:7]):
            return True
    return False


def match_caption(text: str) -> Optional[Tuple[str, int, str]]:
    t = text.strip()
    m = re.match(r"^(Fig(?:ure)?|figure|Table|table)\s*\.?\s*(\d+)([a-zA-Z])?(.*)$", t, re.I)
    if m:
        if m.group(3):
            return None
        if _looks_like_body_reference(m.group(4)):
            return None
        return ("table" if m.group(1).lower().startswith("t") else "figure",
                int(m.group(2)), m.group(4).strip())
    m = re.match(r"^(图|表)\s*([0-9０-９]+)(.*)$", t)
    if m:
        if _looks_like_body_reference(m.group(3)):
            return None
        return ("figure" if m.group(1) == "图" else "table",
                _full_to_int(m.group(2)), m.group(3).strip())
    return None


_SECTION_HEADINGS = {
    "摘要", "abstract", "关键词", "keywords", "引言", "introduction", "结论", "conclusion",
    "conclusions", "参考文献", "references", "致谢", "acknowledgments", "acknowledgements",
    "appendix", "附录", "materials and methods", "methods", "results", "discussion",
}


def _is_heading(s: str) -> bool:
    t = s.strip()
    if re.match(r"^\d{1,2}(?:\.\d+){0,3}\s*[、.．]?\s+\S", t) and len(t) <= 80:
        return True
    return t.lower().rstrip(":：") in {h.lower() for h in _SECTION_HEADINGS}


def page_lines(page, fitz) -> List[dict]:
    out = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for ln in block.get("lines", []):
            text = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
            if not text:
                continue
            out.append({"text": text, "bbox": fitz.Rect(ln["bbox"])})
    return out


def find_captions(doc, fitz) -> List[dict]:
    captions = []
    for pno in range(doc.page_count):
        page = doc.load_page(pno)
        lines = page_lines(page, fitz)
        i = 0
        while i < len(lines):
            res = match_caption(lines[i]["text"])
            if res:
                kind, num, rest = res
                text = lines[i]["text"]
                bbox = fitz.Rect(lines[i]["bbox"])
                if not rest:
                    j = i + 1
                    while j < len(lines):
                        nxt = lines[j]["text"]
                        if match_caption(nxt) or _is_heading(nxt):
                            break
                        gap = lines[j]["bbox"].y0 - lines[i]["bbox"].y1
                        if gap > lines[i]["bbox"].height * 2.5:
                            break
                        text += " " + nxt
                        bbox = bbox | fitz.Rect(lines[j]["bbox"])
                        j += 1
                captions.append({"kind": kind, "number": num, "text": text,
                                 "bbox": bbox, "page": pno + 1})
                i += 1
            else:
                i += 1
    return captions


def _dedupe_captions(captions: List[dict]) -> List[dict]:
    best = {}
    for c in captions:
        key = (c["kind"], c["number"])
        if key not in best or len(c["text"]) > len(best[key]["text"]):
            best[key] = c
    return list(best.values())


def graphic_boxes(page, fitz) -> List:
    boxes = []
    for info in page.get_image_info():
        boxes.append(fitz.Rect(info["bbox"]))
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.width < 3 or r.height < 3:
            continue
        if r.width > page.rect.width * 0.98 and r.height > page.rect.height * 0.98:
            continue
        boxes.append(r)
    return boxes


def _union_rect(boxes, fitz):
    r = fitz.Rect(boxes[0])
    for b in boxes[1:]:
        r = r | b
    return r


def figure_crop_region(cap_bbox, boxes, page, fitz, top_bound=0.0):
    """插图：图注在下方。crop_bottom=图注 y0-4；上界取“上一图注下边界”之后的图形，
    并用水平过滤避免把并排图（Fig. a / Fig. b）裁到一起。"""
    crop_bottom = max(0.0, cap_bbox.y0 - 4)
    cap_cx = (cap_bbox.x0 + cap_bbox.x1) / 2

    def h_rel(b):
        return (b.x0 <= cap_cx <= b.x1) or not (b.x1 < cap_bbox.x0 - 12 or b.x0 > cap_bbox.x1 + 12)

    def finish(cand):
        top = min(b.y0 for b in cand)
        x0 = min([cap_bbox.x0] + [b.x0 for b in cand])
        x1 = max([cap_bbox.x1] + [b.x1 for b in cand])
        pad = 6
        return fitz.Rect(max(0, x0 - pad), max(top_bound, top - pad),
                         min(page.rect.x1, x1 + pad), crop_bottom + 2)

    cand = [b for b in boxes if h_rel(b) and b.y1 >= top_bound - 2 and b.y1 <= crop_bottom + 2]
    if cand:
        return finish(cand)
    # 放宽水平过滤：仅垂直带内
    cand = [b for b in boxes if b.y1 >= top_bound - 2 and b.y1 <= crop_bottom + 2]
    if cand:
        return finish(cand)
    top = max(top_bound, crop_bottom - page.rect.height * 0.35)
    return fitz.Rect(page.rect.x0 + 8, top, page.rect.x1 - 8, crop_bottom + 2)


def table_crop_region(cap_bbox, boxes, page, fitz):
    crop_top = min(page.rect.y1, cap_bbox.y1 + 2)
    cap_cx = (cap_bbox.x0 + cap_bbox.x1) / 2
    below = []
    for b in boxes:
        if b.y0 < crop_top - 2:
            continue
        if (b.x0 <= cap_cx <= b.x1) or not (b.x1 < cap_bbox.x0 - 12 or b.x0 > cap_bbox.x1 + 12):
            below.append((b.y0 - crop_top, b))
    below.sort(key=lambda t: t[0])
    group = None
    if below:
        min_gap = below[0][0]
        group = [b for gap, b in below if gap <= min_gap + 40 and gap <= page.rect.height * 0.5]
    if group:
        bottom = max(b.y1 for b in group)
        x0 = min([cap_bbox.x0] + [b.x0 for b in group])
        x1 = max([cap_bbox.x1] + [b.x1 for b in group])
    else:
        bottom = min(page.rect.y1, crop_top + page.rect.height * 0.45)
        x0 = page.rect.x0 + 8
        x1 = page.rect.x1 - 8
    pad = 6
    return fitz.Rect(max(0, x0 - pad), max(0, crop_top - 4),
                     min(page.rect.x1, x1 + pad), min(page.rect.y1, bottom + pad))
# ---------------------------------------------------------------------------
# 首页抬头裁剪
# ---------------------------------------------------------------------------
def crop_paper_header(doc, out_dir: Path, fitz) -> dict:
    page = doc.load_page(0)
    abs_y0 = None
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for ln in block.get("lines", []):
            text = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
            if re.sub(r"\s+", "", text).lower().startswith("abstract"):
                abs_y0 = ln["bbox"][1]
                break
        if abs_y0 is not None:
            break
    top = 0.0
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.height < 2 and r.width > page.rect.width * 0.5 and r.y0 < page.rect.height * 0.18:
            top = max(top, r.y1)
    bottom = (abs_y0 - 2) if abs_y0 is not None else page.rect.height * 0.55
    region = fitz.Rect(0, top, page.rect.width, bottom)
    mat = fitz.Matrix(DPI / 72.0, DPI / 72.0)
    pix = page.get_pixmap(matrix=mat, clip=region)
    dest = out_dir / "header.png"
    pix.save(str(dest))
    mat_web = fitz.Matrix(WEB_DPI / 72.0, WEB_DPI / 72.0)
    pix_web = page.get_pixmap(matrix=mat_web, clip=region)
    datauri = _pix_to_datauri(pix_web, fitz)
    return {"kind": "header", "number": 0, "page": 1, "text": "论文首页抬头",
            "path": str(dest), "datauri": datauri}


def _render_two(page, region, path_hi, dpi, fitz) -> str:
    mat_hi = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix_hi = page.get_pixmap(matrix=mat_hi, clip=region)
    pix_hi.save(str(path_hi))
    mat_web = fitz.Matrix(WEB_DPI / 72.0, WEB_DPI / 72.0)
    pix_web = page.get_pixmap(matrix=mat_web, clip=region)
    return _pix_to_datauri(pix_web, fitz)


def _pix_to_datauri(pix, fitz, max_bytes: int = 1_500_000) -> str:
    if pix.colorspace is None or pix.colorspace.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    png = pix.tobytes("png")
    if len(png) <= max_bytes:
        return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    jpg = pix.tobytes("jpeg", jpg_quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")


# ---------------------------------------------------------------------------
# 主裁剪流程
# ---------------------------------------------------------------------------
def crop_all(doc, out_dir: Path, dpi: int, fitz, selected: Optional[set] = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    captions = _dedupe_captions(find_captions(doc, fitz))
    figures = sorted([c for c in captions if c["kind"] == "figure"], key=lambda c: c["number"])
    tables = sorted([c for c in captions if c["kind"] == "table"], key=lambda c: c["number"])

    fig_nums = [c["number"] for c in figures]
    tab_nums = [c["number"] for c in tables]
    fig_gaps = [n for n in range(1, max(fig_nums) + 1) if n not in set(fig_nums)] if fig_nums else []
    tab_gaps = [n for n in range(1, max(tab_nums) + 1) if n not in set(tab_nums)] if tab_nums else []

    def keep(c):
        return True if selected is None else (c["kind"], c["number"]) in selected

    crops = []
    for c in figures:
        if not keep(c):
            continue
        page = doc.load_page(c["page"] - 1)
        prev = []
        for k in captions:
            if k["page"] != c["page"]:
                continue
            if k["bbox"].y1 >= c["bbox"].y0 - 6:
                continue  # 非严格在上方（并排图注不参与）
            h_ov = not (k["bbox"].x1 < c["bbox"].x0 - 12 or k["bbox"].x0 > c["bbox"].x1 + 12)
            if h_ov:
                prev.append(k)
        top_bound = (max(k["bbox"].y1 for k in prev) + 2) if prev else 0.0
        region = figure_crop_region(c["bbox"], graphic_boxes(page, fitz), page, fitz, top_bound)
        name = f"fig_{c['number']:02d}.png"
        datauri = _render_two(page, region, out_dir / name, dpi, fitz)
        crops.append({"kind": "figure", "number": c["number"], "page": c["page"],
                      "caption": c["text"], "path": str(out_dir / name), "datauri": datauri})

    for c in tables:
        if not keep(c):
            continue
        page = doc.load_page(c["page"] - 1)
        boxes = graphic_boxes(page, fitz)
        region = table_crop_region(c["bbox"], boxes, page, fitz)
        if region.height < page.rect.height * 0.05 and c["page"] < doc.page_count:
            nxt = doc.load_page(c["page"])
            nboxes = graphic_boxes(nxt, fitz)
            top_boxes = [b for b in nboxes if b.y0 < nxt.rect.height * 0.5]
            if top_boxes:
                region = fitz.Rect(max(0, min(b.x0 for b in top_boxes) - 6),
                                   max(0, min(b.y0 for b in top_boxes) - 6),
                                   min(nxt.rect.x1, max(b.x1 for b in top_boxes) + 6),
                                   min(nxt.rect.y1, max(b.y1 for b in top_boxes) + 6))
                page = nxt
        name = f"table_{c['number']:02d}.png"
        datauri = _render_two(page, region, out_dir / name, dpi, fitz)
        crops.append({"kind": "table", "number": c["number"], "page": c["page"],
                      "caption": c["text"], "path": str(out_dir / name), "datauri": datauri})

    report = {"figures": fig_nums, "tables": tab_nums,
              "figure_gaps": fig_gaps, "table_gaps": tab_gaps,
              "figure_count": len(figures), "table_count": len(tables)}
    return crops, report


# ---------------------------------------------------------------------------
# 元数据
# ---------------------------------------------------------------------------
def _header_footer(s: str) -> bool:
    if len(s) < 4:
        return True
    if re.search(r"http|doi|©|copyright|issn|vol\.|received|accepted|published", s, re.I):
        return True
    if re.fullmatch(r"\s*\d{1,4}\s*", s):
        return True
    return False


def extract_meta(doc, fitz) -> dict:
    meta = {}
    for k, v in (doc.metadata or {}).items():
        key = str(k).lstrip("/").lower()
        if isinstance(v, str) and v.strip():
            meta[key] = v.strip()
    first = doc.load_page(0).get_text("text")
    title = meta.get("title", "").strip()
    if not title or len(title) <= 3:
        for line in first.splitlines():
            s = line.strip()
            if 6 <= len(s) <= 160 and not re.search(r"[。；，,.;]$", s) and not _header_footer(s):
                title = s
                break
    author = meta.get("author", "").strip()
    subject = (meta.get("subject") or "").strip()
    journal, volume, pages, year = "", "", "", ""
    m = re.search(r"^(.+?),\s*(\d+)\s*\((\d{4})\)\s*([\d\-–]+)\.", subject)
    if m:
        journal, volume, year, pages = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
    if not year:
        ym = YEAR_RE.search(first)
        year = ym.group(0) if ym else ""
    doi = ""
    dm = DOI_RE.search(first + "\n" + doc.load_page(0).get_text("text"))
    if dm:
        doi = dm.group(0).rstrip(".,;)")
    return {"title": title, "author": author, "journal": journal,
            "volume": volume, "pages": pages, "year": year, "doi": doi, "subject": subject}


def extract_abstract(doc, fitz) -> str:
    text = "\n".join(doc.load_page(i).get_text("text")
                     for i in range(min(doc.page_count, 3)))
    m = re.search(r"(摘要|Abstract)\s*[:：]?\s*(.{30,})", text, re.I | re.S)
    if not m:
        return ""
    rest = m.group(2)
    stop = re.search(r"(关键词|Keywords|引言|Introduction|1\s*引言)", rest, re.I)
    if stop:
        rest = rest[:stop.start()]
    return re.sub(r"\s+", " ", rest).strip()[:1200]


def format_authors(author_str: str) -> str:
    names = [p.strip() for p in re.split(r"[;,]", author_str) if p.strip()]
    out = []
    for n in names[:5]:
        parts = n.split()
        out.append(f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else n)
    return "; ".join(out)


# ---------------------------------------------------------------------------
# 可选大模型（DeepSeek / OpenAI 兼容接口）
# ---------------------------------------------------------------------------
def llm_client():
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return None, None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None, None
    base = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
    model = os.environ.get("LLM_MODEL") or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
    try:
        client = OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)
        return client, model
    except Exception:
        return None, None


def generate_content(client, model, meta: dict, items: List[dict]) -> Optional[dict]:
    item_lines = [f"{it['kind']}_{it['number']}: {it['caption']}" for it in items]
    prompt = (
        "你是一名科研论文中文科普编辑。请把下面的英文学术论文信息转成微信公众号推文所需的简体中文内容。\n\n"
        f"标题：{meta.get('title','')}\n"
        f"期刊：{meta.get('journal','')} {meta.get('year','')}\n"
        f"摘要：{meta.get('abstract','')}\n\n"
        "需要处理的图表（为每一张生成 caption_zh 与 guide）：\n" + "\n".join(item_lines) +
        "\n\n只输出一个 JSON 对象，不要输出任何其它文字或 Markdown 代码块标记，结构如下：\n"
        '{"title_zh":"中文译题","digest":"150-250字核心速览，一段话",'
        '"conclusions":["量化结论1","量化结论2","量化结论3"],'
        '"background":["研究背景与行业痛点","现有方法局限","本文核心突破"],'
        '"items":{"fig_1":{"caption_zh":"简短中文图注","guide":"2-3句中文导读"}}}\n'
        "要求：结论必须包含原文具体数字；不要编造数据。"
    )
    try:
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=0.3)
        text = resp.choices[0].message.content or ""
    except Exception as ex:
        print(f"[WARN] 大模型调用失败：{ex}", file=sys.stderr)
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None

# ---------------------------------------------------------------------------
# HTML 生成
# ---------------------------------------------------------------------------
def _strip_caption_prefix(caption: str) -> str:
    return re.sub(r"^(Fig(?:ure)?\.?\s*\d+\.?\s*|Table\.?\s*\d+\.?\s*|图\s*\d+\s*|表\s*\d+\s*)",
                  "", caption, flags=re.I).strip()


def build_references_card(meta: dict) -> str:
    authors = format_authors(meta.get("author", "")) or "Li, Qiming"
    title = meta.get("title", "")
    journal = meta.get("journal", "") or "Journal of Rock Mechanics and Geotechnical Engineering"
    year = meta.get("year", "")
    vol = meta.get("volume", "")
    pages = meta.get("pages", "")
    doi = meta.get("doi", "")
    ref = f"{authors}, 等. {title}[J]. {journal}"
    if year:
        ref += f", {year}"
    if vol:
        ref += f", {vol}"
    if pages:
        ref += f": {pages}"
    ref += "."
    if doi:
        ref += f" DOI: {doi}."
    return ref


def build_html(meta: dict, all_crops: List[dict], args, src_resolver: Callable,
               content: Optional[dict] = None) -> str:
    esc = html_lib.escape
    header = next((c for c in all_crops if c["kind"] == "header"), None)
    body = [c for c in all_crops if c["kind"] != "header"]
    renumber = bool(getattr(args, "renumber", False))

    title_zh = (content or {}).get("title_zh") or args.title or meta.get("title") or "未命名论文"
    en_title = meta.get("title", "")

    parts = [f'<section style="{SECTION_STYLE}">']
    parts.append(f'<h1 style="{H1_STYLE}">{esc(title_zh)}</h1>')
    parts.append(f'<p style="{EN_TITLE_STYLE}">{esc(en_title)}</p>')
    if header:
        parts.append(f'<img src="{src_resolver(header)}" style="width:100%;height:auto;" alt="论文首页抬头">')

    if content:
        digest = content.get("digest") or args.digest or ""
        parts.append(f'<h2 style="{H2_STYLE}">01 核心速览</h2>')
        parts.append(f'<section style="{DIGEST_BOX_STYLE}">{esc(digest)}</section>')
        concl = content.get("conclusions") or []
        if concl:
            parts.append(f'<p style="{P_STYLE}"><strong style="color:#1a56db;">三条量化核心结论</strong></p>')
            parts.append('<ol style="margin:0 0 24px;padding-left:20px;">')
            for c in concl[:3]:
                parts.append(f'<li style="margin:0 0 10px;font-size:15px;line-height:1.8;text-align:justify;">{esc(c)}</li>')
            parts.append('</ol>')
        bkg = content.get("background") or []
        if bkg:
            parts.append(f'<h2 style="{H2_STYLE}">02 研究背景与痛点</h2>')
            labels = ["研究背景与行业痛点", "现有方法局限", "本文核心突破"]
            for i, b in enumerate(bkg[:3]):
                lab = labels[i] if i < len(labels) else ""
                parts.append(f'<p style="{P_STYLE}"><strong style="color:#1a56db;">{lab}：</strong>{esc(b)}</p>')
        parts.append(f'<h2 style="{H2_STYLE}">03 图表精读</h2>')
        items_map = content.get("items") or {}
        fig_no = tab_no = 0
        for c in body:
            info = items_map.get(f"{c['kind']}_{c['number']}", {})
            caption_zh = info.get("caption_zh") or c["caption"]
            guide = info.get("guide") or ""
            if c["kind"] == "figure":
                fig_no += 1
                label, disp = "图", fig_no
            else:
                tab_no += 1
                label, disp = "表", tab_no
            if guide:
                parts.append(f'<p style="{GUIDE_STYLE}">{esc(guide)}</p>')
            head = f"{label}{disp}" if renumber else f"{label}{c['number']}"
            parts.append(f'<figure style="{FIGURE_STYLE}">'
                         f'<img src="{src_resolver(c)}" style="{IMG_STYLE}" alt="{esc(caption_zh)}">'
                         f'<figcaption style="{FIGCAP_STYLE}">{esc(head + " " + caption_zh)}</figcaption>'
                         f'</figure>')
    else:
        src_parts = [p for p in [meta.get("author"), meta.get("journal"),
                                 meta.get("year"),
                                 ("DOI: " + meta["doi"] if meta.get("doi") else "")] if p]
        if src_parts:
            parts.append(f'<p style="{SRC_STYLE}">{esc(" ｜ ".join(src_parts))}</p>')
        parts.append(f'<h2 style="{H2_STYLE}">图表精读</h2>')
        fig_no = tab_no = 0
        for c in body:
            if c["kind"] == "figure":
                fig_no += 1
                label, disp = "图", fig_no
            else:
                tab_no += 1
                label, disp = "表", tab_no
            head = f"{label}{disp}" if renumber else f"{label}{c['number']}"
            cap = _strip_caption_prefix(c["caption"])
            parts.append(f'<p style="{GUIDE_STYLE}"><!-- 导读：请补充 2~3 句中文说明 --></p>')
            parts.append(f'<figure style="{FIGURE_STYLE}">'
                         f'<img src="{src_resolver(c)}" style="{IMG_STYLE}" alt="{esc(cap)}">'
                         f'<figcaption style="{FIGCAP_STYLE}">{esc(head + " " + cap)}</figcaption>'
                         f'</figure>')

    ref = build_references_card(meta)
    parts.append(f'<div style="{CARD_STYLE}"><div style="{CARD_TITLE_STYLE}">参考文献</div>'
                 f'<p style="{CARD_BODY_STYLE}">{esc(ref)}</p></div>')
    parts.append(f'<div style="{CARD_STYLE}"><div style="{CARD_TITLE_STYLE}">版 权 声 明</div>'
                 f'<p style="{CARD_BODY_STYLE}">{esc(COPYRIGHT_TEXT)}</p></div>')
    parts.append("</section>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 微信 API
# ---------------------------------------------------------------------------
def get_access_token(requests, appid, secret):
    r = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                     params={"grant_type": "client_credential", "appid": appid, "secret": secret},
                     timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError("获取 access_token 失败：" + json.dumps(data, ensure_ascii=False))
    return data["access_token"]


def _prepare_image_data(path: Path, max_bytes: int = 1_000_000) -> bytes:
    fitz = _import_fitz()
    pix = fitz.Pixmap(str(path))
    if pix.colorspace is None or pix.colorspace.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    data = b""
    for q in (90, 80, 70, 60):
        data = pix.tobytes("jpeg", jpg_quality=q)
        if len(data) <= max_bytes:
            break
    if len(data) > max_bytes:
        try:
            from PIL import Image  # type: ignore
            import io
            im = Image.open(path).convert("RGB")
            scale = 1.0
            while len(data) > max_bytes and scale > 0.2:
                scale -= 0.2
                w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
                buf = io.BytesIO()
                im.resize((w, h), Image.LANCZOS).save(buf, "JPEG", quality=85)
                data = buf.getvalue()
        except Exception:
            pass
    if len(data) > max_bytes:
        raise RuntimeError(f"图片压缩后仍超过 1MB：{path}")
    return data


def upload_image(requests, token, path):
    data = _prepare_image_data(Path(path))
    r = requests.post("https://api.weixin.qq.com/cgi-bin/media/uploadimg",
                      params={"access_token": token},
                      files={"media": (Path(path).stem + ".jpg", data, "image/jpeg")}, timeout=120)
    res = r.json()
    if "url" not in res:
        raise RuntimeError("上传正文图片失败：" + json.dumps(res, ensure_ascii=False))
    return res["url"]


def upload_thumb(requests, token, path):
    data = _prepare_image_data(Path(path))
    r = requests.post("https://api.weixin.qq.com/cgi-bin/material/add_material",
                      params={"access_token": token, "type": "image"},
                      files={"media": (Path(path).stem + ".jpg", data, "image/jpeg")}, timeout=120)
    res = r.json()
    if "media_id" not in res:
        raise RuntimeError("上传封面失败：" + json.dumps(res, ensure_ascii=False))
    return res["media_id"]


def add_draft(requests, token, title, author, digest, content, thumb_media_id):
    payload = {"articles": [{
        "title": title or "未命名", "author": author or "", "digest": digest or "",
        "content": content, "thumb_media_id": thumb_media_id,
        "need_open_comment": 0, "only_fans_can_comment": 0}]}
    r = requests.post("https://api.weixin.qq.com/cgi-bin/draft/add",
                      params={"access_token": token}, json=payload, timeout=60)
    res = r.json()
    if "media_id" not in res:
        raise RuntimeError("创建草稿失败：" + json.dumps(res, ensure_ascii=False))
    return res["media_id"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_items_arg(s: Optional[str]) -> Optional[set]:
    if not s:
        return None
    sel = set()
    for tok in s.split(","):
        tok = tok.strip().lower()
        m = re.match(r"^(fig|figure|table|tab)_?(\d+)$", tok)
        if m:
            kind = "table" if m.group(1).startswith(("table", "tab")) else "figure"
            sel.add((kind, int(m.group(2))))
    return sel or None


def main(argv=None) -> int:
    _fix_stdout()
    _load_env()
    ap = argparse.ArgumentParser(prog="wechat_draft_helper",
                                 description="论文 PDF -> 公众号内联样式 HTML + 300 DPI 图表截图")
    ap.add_argument("--pdf", required=True, help="输入 PDF 路径")
    ap.add_argument("--out-dir", default="crops", help="截图输出目录（默认 crops）")
    ap.add_argument("--html", default="wechat_article.html", help="生成的 HTML 路径")
    ap.add_argument("--title", default=None, help="覆盖中文标题")
    ap.add_argument("--author", default=None, help="覆盖作者")
    ap.add_argument("--digest", default=None, help="覆盖核心速览")
    ap.add_argument("--items", default=None, help="精读模式：只处理指定图表，如 fig_1,fig_2,table_4")
    ap.add_argument("--renumber", action="store_true", help="图注按截取顺序重新编号（图1、图2…）")
    ap.add_argument("--llm", action="store_true", help="强制使用大模型生成中文成品")
    ap.add_argument("--no-llm", action="store_true", help="禁用大模型（只输出脚手架）")
    ap.add_argument("--thumb", default=None, help="封面图（--publish 时必填）")
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--publish", action="store_true", help="上传图片并推送公众号草稿箱")
    ap.add_argument("--appid", default=None)
    ap.add_argument("--secret", default=None)
    args = ap.parse_args(argv)

    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"[ERROR] 找不到 PDF：{pdf}", file=sys.stderr)
        return 2
    try:
        fitz = _import_fitz()
    except RuntimeError as ex:
        print(f"[ERROR] {ex}", file=sys.stderr)
        return 3

    doc = fitz.open(str(pdf))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = Path(args.html)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    meta = extract_meta(doc, fitz)
    meta["abstract"] = extract_abstract(doc, fitz)
    header = crop_paper_header(doc, out_dir, fitz)
    selected = parse_items_arg(args.items)
    crops, report = crop_all(doc, out_dir, args.dpi, fitz, selected)
    doc.close()

    all_crops = [header] + crops
    print(json.dumps({
        "figures": report["figures"], "tables": report["tables"],
        "figure_gaps": report["figure_gaps"], "table_gaps": report["table_gaps"],
        "figure_count": report["figure_count"], "table_count": report["table_count"],
        "selected_count": len(crops),
    }, ensure_ascii=False, indent=2))

    content = None
    use_llm = (not args.no_llm) and (args.llm or bool(
        os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")))
    if use_llm:
        client, model = llm_client()
        if client:
            content = generate_content(client, model, meta, crops)
            if content:
                print("[OK] 大模型内容生成成功", file=sys.stderr)

    def local_src(c):
        return c["datauri"]
    html_text = build_html(meta, all_crops, args, local_src, content)
    html_path.write_text(html_text, encoding="utf-8")

    manifest = {
        "pdf": str(pdf), "title": meta.get("title"), "author": meta.get("author"),
        "journal": meta.get("journal"), "year": meta.get("year"),
        "volume": meta.get("volume"), "pages": meta.get("pages"), "doi": meta.get("doi"),
        "report": report,
        "items": [{"kind": c["kind"], "number": c["number"], "page": c["page"],
                   "caption": (c.get("text") or c.get("caption", "")), "path": c["path"],
                   "datauri": c.get("datauri", "")}
                  for c in all_crops],
    }
    (html_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {"pdf": str(pdf), "html": str(html_path), "crops": len(crops),
              "header": str(Path(header["path"])), "figures": report["figure_count"],
              "tables": report["table_count"], "llm_used": bool(content)}

    appid = args.appid or os.environ.get("WECHAT_APP_ID", "")
    secret = args.secret or os.environ.get("WECHAT_APP_SECRET", "")
    if appid and secret:
        try:
            requests = _import_requests()
            token = get_access_token(requests, appid, secret)
            uploaded = {}

            def mmbiz_src(c):
                p = Path(c["path"])
                if p not in uploaded:
                    uploaded[p] = upload_image(requests, token, p)
                return uploaded[p]
            published_text = build_html(meta, all_crops, args, mmbiz_src, content)
            published_path = html_path.with_name(html_path.stem + ".wechat.html")
            published_path.write_text(published_text, encoding="utf-8")
            result["wechat_html"] = str(published_path)
            result["uploaded_images"] = len(uploaded)

            if args.publish:
                if not args.thumb:
                    print("[ERROR] --publish 需要 --thumb 封面图", file=sys.stderr)
                    return 4
                thumb_media_id = upload_thumb(requests, token, Path(args.thumb))
                final_title = (content or {}).get("title_zh") or args.title or meta.get("title") or "未命名"
                final_author = args.author or meta.get("author") or ""
                final_digest = (content or {}).get("digest") or args.digest or ""
                media_id = add_draft(requests, token, final_title, final_author,
                                     final_digest, published_text, thumb_media_id)
                result["draft_media_id"] = media_id
        except RuntimeError as ex:
            print(f"[ERROR] {ex}", file=sys.stderr)
            return 5

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
