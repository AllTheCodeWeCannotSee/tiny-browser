import socket
import ssl
import os
import tkinter
import tkinter.font
import sys


WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18
FONTS = {}
HEAD_TAGS = [
            "base", "basefont", "bgsound", "noscript",
            "link", "meta", "title", "style", "script",
        ]
SELF_CLOSING_TAGS = [
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        ]
BLOCK_ELEMENTS = [
            "html", "body", "article", "section", "nav", "aside",
            "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
            "footer", "address", "p", "hr", "pre", "blockquote",
            "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
            "figcaption", "main", "div", "table", "form", "fieldset",
            "legend", "details", "summary"
        ]
INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


class URL:
    def __init__(self, url):
        # http://example.org/index.html
        self.scheme, url = url.split('://', 1)
        assert self.scheme in ["http", "https", "file"]
        if self.scheme == "http":
            self.host, self.port, self.path = parseHttp(url)
        elif self.scheme == "https":
            self.host, self.port, self.path = parseHttps(url)
        elif self.scheme == "file":
            self.host, self.port, self.path = parseFile(url)
      
    def resolve(self, url):
        if "://" in url: return URL(url)
        if not url.startswith("/"):
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        if url.startswith("//"):
            return URL(self.scheme + ":" + url)
        else:
            return URL(self.scheme + "://" + self.host + \
                       ":" + str(self.port) + url)
           
    def request(self):
        # Added for specific HTML content loading
        if self.path == "/specific_document.html":
            return HTML_FOR_STRUCTURE_PRINT
        if self.scheme == "file":
            try:
                with open(self.path, 'r', encoding='utf8') as f:
                    return f.read()
            except Exception as e:
                return "<html><body><h1>Error Reading File</h1><p>Could not read file {}: {}</p></body></html>".format(self.path, e)

        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
            )
        s.connect((self.host, self.port))
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
        request = "GET {} HTTP/1.1\r\n".format(self.path)
        request += "Host: {}\r\n".format(self.host)
        request += "Connection: close\r\n"
        request += "User-Agent: tiny-browser\r\n"
        request += "\r\n"
        
        s.send(request.encode("utf8"))
        
        response = s.makefile("r", encoding="utf8", newline="\r\n")
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)
        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n": break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers
        content = response.read()
        s.close()
        return content

class CSSParser:
    def __init__(self,s):
        self.s = s
        self.i = 0
    def selector(self):
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out
    
    def parse(self):
        rules = []
        while self.i < len(self.s):
            try: 
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules
     
    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1
    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.s[start:self.i]
    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1    
    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val
    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop.casefold()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs
    
    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None
  
class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1
    def matches(self, node):
        return isinstance(node, Element) and node.tag == self.tag

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority
    def matches(self, node):
        '''
            div p
        '''
        # 当前节点是 p，则 False
        if not self.descendant.matches(node): return False
        # 当前节点匹配，向上便利父节点有没有 div
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

def cascade_priority(rule):
    selector, body = rule
    return selector.priority
  
def style(node, rules):
    node.style = {}
    
    # 继承
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    
    # style sheet
    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value
            
    # node 的 style 属性
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value
    
    if node.style["font-size"].endswith("%"):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            parent_font_size = INHERITED_PROPERTIES["font-size"]
        node_pct = float(node.style["font-size"][:-1]) / 100 # 移除 %
        parent_px = float(parent_font_size[:-2]) # 移除 px
        node.style["font-size"] = str(node_pct * parent_px) + "px"
        
    for child in node.children:
        style(child, rules)

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, 
            width=WIDTH,
            height=HEIGHT,
            bg="white"
        )
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
    def scrolldown(self, e):
        max_y = max(self.document.height + 2*VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()
    def scrollup(self, e):
        self.scroll -= SCROLL_STEP
        self.draw()
    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)
    def load(self, url):
        body = url.request()
        
        # 第1次遍历：生成 node tree
        self.nodes = HTMLParser(body).parse()
        
        # 获取 css 文件
        rules = DEFAULT_STYLE_SHEET.copy()
        links = [node.attributes["href"]
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "link"
                 and node.attributes.get("rel") == "stylesheet"
                 and "href" in node.attributes]
        for link in links:
            style_url = url.resolve(link)
            try:
                body = style_url.request()
            except:
                continue
            rules.extend(CSSParser(body).parse())
            
        # 第2次遍历：生成 style tree
        style(self.nodes, sorted(rules, key=cascade_priority))
        
        # 第3次遍历：生成 layout tree
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        
        # 第4次遍历：生成绘制列表 (Painting)
        self.display_list = []
        paint_tree(self.document, self.display_list)
        
        self.draw()
    def _print_layout_node_details(self, layout_node, indent_str=""):
        node_type_name = type(layout_node).__name__
        
        node_description = ""
        if hasattr(layout_node, 'node') and layout_node.node:
            if isinstance(layout_node.node, Element):
                node_description = f"关联节点 (Associated Node): Element <{layout_node.node.tag}>"
            elif isinstance(layout_node.node, Text):
                text_preview = layout_node.node.text.strip()
                if len(text_preview) > 30:
                    text_preview = text_preview[:27] + "..."
                node_description = f"关联节点 (Associated Node): Text \"{text_preview}\""
            else: # Should not happen for DocumentLayout/BlockLayout with current structure
                node_description = f"关联节点 (Associated Node): {type(layout_node.node).__name__}"
        
        print(f"{indent_str}{node_type_name} [{node_description}]")
        
        attrs_to_print = {
            "x": "x 坐标", "y": "y 坐标", 
            "width": "宽度 (width)", "height": "高度 (height)"
        }
        for attr_name, attr_desc in attrs_to_print.items():
            if hasattr(layout_node, attr_name):
                value = getattr(layout_node, attr_name)
                # Only print if not None, as some might be None initially or not applicable
                if value is not None:
                    print(f"{indent_str}  {attr_desc}: {value}")

        if isinstance(layout_node, BlockLayout):
            mode = layout_node.layout_mode()
            print(f"{indent_str}  布局模式 (Layout Mode): {mode}")
            if mode == "inline":
                print(f"{indent_str}  行内元素数量 (Inline items in display_list): {len(layout_node.display_list)}")

        for child in layout_node.children:
            self._print_layout_node_details(child, indent_str + "  ")

    def print_document_layout_structure(self):
        if not hasattr(self, 'document') or not self.document:
            print("文档布局 (Document layout) 尚未生成。请先加载一个 URL。")
            return
    
        print("\n--- 文档布局树结构 (Document Layout Tree Structure) ---")
        self._print_layout_node_details(self.document)
        print("--- 结束文档布局树结构 (End of Document Layout Tree Structure) ---\n")


class Text:
    '''
        文本节点的创建、插入到树中
    '''
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
    def __repr__(self):
        return repr(self.text)

class Element:
    '''
        元素节点的创建、插入到树中
    '''
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent
    def __repr__(self):
        return "<" + self.tag + ">"

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = [] # 未完成的 node 栈（文本、元素）
    def parse(self):
        '''
            解析 HTML
        '''
        text = ""
        in_tag = False
        for c in self.body:
            if c == "<":
                # <p>1</p> <p>2</p>
                # 运行到 2 的 <p> 的 < 时
                # add_text(1)
                in_tag = True
                if text: self.add_text(text) 
                text = ""
            elif c == ">":
                # <p>1</p>
                # 运行到 1 的 > 时
                # add_tag(p)
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                # <p>1</p>
                # 运行到 1 时, text = 1
                # 运行到 p 时, text = p
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()
    def add_text(self, text):
        '''
            添加文本节点, 将其作为最后一个未完成节点的子节点
        '''
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)
    def add_tag(self, tag):
        '''
            添加元素节点
        '''
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes,parent)
            self.unfinished.append(node)
    def finish(self):
        '''
            处理未完成的节点
        '''
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
    def get_attributes(self, text):
        '''
            解析属性
        '''
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
        return tag, attributes
    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]    
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] \
                and tag not in ["head", "body", "/html"]:
                if tag in HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and \
                tag not in ["/head"] + HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

class DocumentLayout:
    '''
        layout tree 根节点
    '''
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.previous = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        
        self.width = WIDTH - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP
        
        child.layout()
        self.height = child.height
        
    def paint(self):
        return []

class BlockLayout:
    '''
        块级元素的布局对象
    '''
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        
        # 元素框左上角的 x 坐标。
        # 它通常直接继承自 self.parent.x
        self.x = None
         
        # 元素框左上角的 y 坐标。
        # 它的值取决于 self.previous：
        #   如果存在，则为 previous.y + previous.height；
        #   如果不存在（即它是第一个子元素），则直接继承自 self.parent.y
        self.y = None 
        
        # 元素的宽度。
        # 它通常直接继承自 self.parent.width，占据父元素提供的所有水平空间。
        self.width = None
        
        # 元素的高度。
        # 这是一个计算结果。
        #   在所有子元素布局完成后 (child.layout())，它的高度会被计算出来。
        #   在 "block" 模式下，它是所有子元素高度的总和。
        self.height = None
        self.display_list = []
        
    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"
        
    def layout(self):
        '''
            node tree -> layout tree
        '''
        self.x = self.parent.x
        self.width = self.parent.width
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        mode = self.layout_mode()
        if mode == "block":
            # block
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            # inline
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 12
            
            self.line = []
            self.recurse(self.node)
            self.flush()
            
        for child in self.children:
            child.layout()
        if mode == "block":
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y
            
    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            cmds.append(rect)

        
        if self.layout_mode() == "inline":
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))
        return cmds
        
    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font, color in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for rel_x, word, font, color in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font, color))
        self.cursor_x = 0
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
            
    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.flush()
            for child in node.children:
                self.recurse(child)
    
    def word(self, node, word): 
        color = node.style["color"]
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal": 
            style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        
        font = get_font(size, weight, style)
        w = font.measure(word)
        
        if self.cursor_x + w > self.width:
            # 如果到达行尾，处理 line 缓冲区
            self.flush() 
        self.line.append((self.cursor_x, word, font, color))
        self.cursor_x += w + font.measure(" ")

class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        
class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.parent = parent
        self.previous = previous
        self.children = []
        

        


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw',
            fill=self.color
            )
    
class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color)



def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())
    for child in layout_object.children:
        paint_tree(child, display_list)
        
def parseHttp(url):
    if "/" not in url:
        url += "/"
    host, path = url.split('/', 1)
    if ":" in host:
            host, port = host.split(":", 1)
    else:
        port = 80
    path = "/" + path
    return host, int(port), path

def parseHttps(url):
    if "/" not in url:
        url += "/"
    host, path = url.split('/', 1)
    if ":" in host:
            host, port = host.split(":", 1)
    else:
        port = 443
    path = "/" + path
    return host, port, path

def parseFile(url):
    return None, None, url

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

HTML_FOR_STRUCTURE_PRINT = """
<html>
  <body>
    <h1>A Blue Headline</h1>
    <p>Some text and a <span>italic</span> word.</p>
  </body>
</html>
"""

if __name__ == "__main__":
    
    
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
    # browser = Browser()
    # browser.load(URL("file:///specific_document.html"))
    # browser.print_document_layout_structure()
    