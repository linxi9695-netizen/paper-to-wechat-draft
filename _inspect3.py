import re
xml = open(r"D:\文档\ChatGPT\公众号发布草稿\_doc.xml", encoding="utf-8").read()
# opening tag
m = re.search(r"<w:document[^>]*>", xml)
print("OPEN:", m.group(0))
# sectPr
s = re.search(r"<w:sectPr.*?</w:sectPr>", xml, re.S)
print("SECTPR:", s.group(0))
# check settings for anything referencing
print("len", len(xml))
