import re
xml = open(r"D:\文档\ChatGPT\公众号发布草稿\_doc.xml", encoding="utf-8").read()
# Print the first few paragraphs raw to understand formatting
paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
for idx in [0,3,4,5,6,8,10,55,56,62,63,65,66]:
    p = paras[idx]
    print("="*80)
    print("PARA", idx)
    print(p[:1800])
