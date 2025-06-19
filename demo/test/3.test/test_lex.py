import unittest
# 假设 browser.py 与此文件在同一目录或已添加到 PYTHONPATH
# 因此我们可以直接导入 Text, Tag 和 lex。
# 如果 browser.py 在其他位置，您可能需要调整 PYTHONPATH
# 或者如果它是包的一部分，则使用相对导入。
from browser import Text, Tag, lex, paint_tokens


if __name__ == '__main__':
    text = "<div>hello<p>world? world!</p></div>"
    tokens = lex(text)
    paint_tokens(tokens)