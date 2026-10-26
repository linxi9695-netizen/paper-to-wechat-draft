import re
xml = open(r"D:\文档\ChatGPT\公众号发布草稿\_doc.xml", encoding="utf-8").read()
paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
for idx in [6,10,55]:
    print("="*90)
    print("PARA", idx)
    print(paras[idx][:1400])
