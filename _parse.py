import re
xml = open(r"D:\文档\ChatGPT\公众号发布草稿\_doc.xml", encoding="utf-8").read()
paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
print("num paras", len(paras))
for i,p in enumerate(paras):
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)
    txt = "".join(texts)
    imgs = re.findall(r'r:embed="(rId\d+)"', p)
    hasimg = bool(re.search(r"<w:drawing>", p))
    if txt.strip() or hasimg:
        print(f"[{i}] TXT={txt!r} IMG={imgs}")
