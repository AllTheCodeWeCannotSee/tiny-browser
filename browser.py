import socket
import ssl
import os

import sys
import urllib.parse
import dukpy
import ctypes
import sdl2
import skia
import math
import time

import threading

INPUT_WIDTH_PX = 200
WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18
FONTS = {}
NAMED_COLORS = {
    "black": "#000000",
    "gray":  "#808080",
    "white": "#ffffff",
    "red":   "#ff0000",
    "green": "#00ff00",
    "blue":  "#0000ff",
    "lightblue": "#add8e6",
    "lightgreen": "#90ee90",
    "orange": "#ffa500",
    "orangered": "#ff4500",
}
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
COOKIE_JAR = {}
RUNTIME_JS = open("runtime.js").read()
EVENT_DISPATCH_JS = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"
SETTIMEOUT_JS = "__runSetTimeout(dukpy.handle)"
XHR_ONLOAD_JS = "__runXHROnload(dukpy.out, dukpy.handle)"

# ---------------------------------- HTTP --------------------------------- #
class URL:
    def __str__(self):
        port_part = ":" + str(self.port)
        if self.scheme == "https" and self.port == 443:
            port_part = ""
        if self.scheme == "http" and self.port == 80:
            port_part = ""
        return self.scheme + "://" + self.host + port_part + self.path
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
    
    # 同源策略 协议+主机+端口 
    def origin(self):
        return self.scheme + "://" + self.host + ":" + str(self.port)
    
    
    def resolve(self, url):
        '''
            处理相对路径
        '''
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
           
    def request(self, referrer, payload=None):
        if self.scheme == "file":
            try:
                with open(self.path, 'r', encoding='utf8') as f:
                    return f.read()
            except Exception as e:
                return "<html><body><h1>Error Reading File</h1><p>Could not read file {}: {}</p></body></html>".format(self.path, e)

        # 建立tcp
        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
            )
        s.connect((self.host, self.port))
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
            
        # ----构建请求头----
        method = "POST" if payload else "GET"
        request = "{} {} HTTP/1.0\r\n".format(method, self.path)
        
        
        
        # 同站cookie
        if self.host in COOKIE_JAR:
            cookie, params = COOKIE_JAR[self.host]
            request += "Cookie: {}\r\n".format(cookie)
            allow_cookie = True
            if referrer and params.get("samesite", "none") == "lax":
                if method != "GET":
                    allow_cookie = self.host == referrer.host
            if allow_cookie:
                request += "Cookie: {}\r\n".format(cookie)
        
        
        if payload:
            length = len(payload.encode("utf8"))
            request += "Content-Length: {}\r\n".format(length)
        
        request += "Host: {}\r\n".format(self.host)
        request += "\r\n"
        
        if payload: request += payload
        
        # ----发送请求----
        s.send(request.encode("utf8"))
        
        
        # ----接收响应----
        response = s.makefile("r", encoding="utf8", newline="\r\n")
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)
        
        # 读 headers
        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n": break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
            
        # 同站cookie 
        #   例子：Set-Cookie: session_id=abc123xyz; Path=/; Expires=Wed, 21 Oct 2025 07:28:00 GMT; HttpOnly
        #   结果：("session_id=abc123xyz", {"path": "/", "expires": "wed, 21 oct 2025 07:28:00 gmt", "httponly": "true"})

        if "set-cookie" in response_headers:
            cookie = response_headers["set-cookie"]
            params = {}
            if ";" in cookie:
                cookie, rest = cookie.split(";", 1)
                for param in rest.split(";"):
                    if '=' in param:
                        param, value = param.split("=", 1)
                    else:
                        value = "true"
                    params[param.strip().casefold()] = value.casefold()
            COOKIE_JAR[self.host] = (cookie, params)
        
            
            
        
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers
        
        content = response.read()
        s.close()
        return response_headers, content

# ---------------------------------- HTML Parser --------------------------------- #
class Text:
    '''
        文本节点的创建、插入到树中
    '''
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        
        self.is_focused = False

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
        
        self.is_focused = False
        
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

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list
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
    return host, int(port), path
def parseFile(url):
    return None, None, url

# ---------------------------------- CSS Parser --------------------------------- #
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

DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()



# ---------------------------------- Layout --------------------------------- #
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

    def should_paint(self):
        return True

    def paint_effects(self, cmds):
        return cmds
    
class BlockLayout:
    '''
        块级元素的布局对象
    '''
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        
        # 存放 LineLayout 对象
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

    def paint_effects(self, cmds):
        cmds = paint_visual_effects(
            self.node, cmds, self.self_rect())
        return cmds
    
    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag != "input" and self.node.tag !=  "button")
    

    def self_rect(self):
        return skia.Rect.MakeLTRB(
            self.x, self.y,
            self.x + self.width, self.y + self.height)
        
    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children or self.node.tag == "input":
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
            self.new_line()
            self.recurse(self.node)
            
        for child in self.children:
            child.layout()
            
        self.height = sum([child.height for child in self.children])

            
    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)

        
        if bgcolor != "transparent":
            radius = float(
                self.node.style.get(
                    "border-radius", "0px")[:-2])
            cmds.append(DrawRRect(
                self.self_rect(), radius, bgcolor))
            
        return cmds
        

            
    def recurse(self, node):
        '''
            node: inline node
            例子：
                输入：hello <p>world</p>
                流程：self.word(hello), self.word(world)
        '''
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.new_line()
            
            elif node.tag == "input" or node.tag == "button":
                self.input(node)
            
            else:
                for child in node.children:
                    self.recurse(child)
        
    def input(self, node):
        w = INPUT_WIDTH_PX
        if self.cursor_x + w > self.width:
            self.new_line()
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        input = InputLayout(node, line, previous_word)
        line.children.append(input)

        weight = node.style["font-weight"]
        style = node.style["font-style"]

        size = float(node.style["font-size"][:-2]) * .75
        font = get_font(size, weight, style)

        self.cursor_x += w + font.measureText(" ")
    
    def word(self, node, word): 
        '''
            作用：就像一个打字员在排版
                它拿到一个单词，看看当前行还够不够地方放下它。如果不够，就另起一行。
                然后，把这个单词“写”在当前行的末尾，并把笔向右移动相应的距离，准备写下一个字
            self.children: 一个个 LineLayout 实例
            node: TextNode
            word: str
        '''
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        size = float(node.style["font-size"][:-2]) * .75
        font = get_font(size, weight, style)
        w = font.measureText(word)
        
        if self.cursor_x + w > self.width:
            # 如果到达行尾，处理 line 缓冲区
            self.new_line()
            
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)
        self.cursor_x += w + font.measureText(" ")
        
    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)
  
class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        
        self.x = None
        self.y = None
        self.width = None
        self.height = None  
    def should_paint(self):
        return True
    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        max_ascent = max([-word.font.getMetrics().fAscent 
                          for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline + word.font.getMetrics().fAscent
        max_descent = max([word.font.getMetrics().fDescent
                           for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)
    def paint(self):
        return []
        
    def paint_effects(self, cmds):
        return cmds
    
class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.parent = parent
        self.previous = previous
        self.children = []
        
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.font = None

    def should_paint(self):
        return True
    
    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)
        
        self.width = self.font.measureText(self.word)

        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = linespace(self.font)
        
    def paint(self):
        cmds = []
        color = self.node.style["color"]
        cmds.append(
            DrawText(self.x, self.y, self.word, self.font, color))
        return cmds
    
    def paint_effects(self, cmds):
        return cmds
        
class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.font = None
     
    def should_paint(self):
        return True
       
    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]

        size = float(self.node.style["font-size"][:-2]) * .75
        self.font = get_font(size, weight, style)
        
        self.width = INPUT_WIDTH_PX
        self.height = linespace(self.font)

        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

    
    def self_rect(self):
        return skia.Rect.MakeLTRB(
            self.x, self.y, self.x + self.width,
            self.y + self.height)
    
    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        
        if self.node.attributes.get("type") == "hidden":
            return cmds
        
        # 绘制背景
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            cmds.append(DrawRRect(self.self_rect(), radius, bgcolor))

        
        # 获取输入框中的文本/按钮的文本
        if self.node.tag == "input":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "button":
            if len(self.node.children) == 1 and \
               isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print("Ignoring HTML contents inside button")
                text = ""
        
        # 绘制输入框中的文本/按钮的文本、
        color = self.node.style["color"]
        cmds.append(DrawText(self.x, self.y, text, self.font, color))

        # 绘制焦点
        if self.node.is_focused:
            cx = self.x + self.font.measureText(text)
            cmds.append(DrawLine(
                cx, self.y, cx, self.y + self.height, "black", 1))
        
        return cmds
    
    def paint_effects(self, cmds):
        return paint_visual_effects(self.node, cmds, self.self_rect())
    
class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    def contains_point(self, x, y):
        return x >= self.left and x < self.right \
            and y >= self.top and y < self.bottom 

def linespace(font):
    '''
        计算出该字体用于渲染一行文本时所占用的总垂直高度
    '''
    metrics = font.getMetrics()
    return metrics.fDescent - metrics.fAscent

# ---------------------------------- Paint --------------------------------- #

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        
        self.rect = skia.Rect.MakeLTRB(
            x1, y1,
            x1 + font.measureText(text),
            y1 - font.getMetrics().fAscent \
                + font.getMetrics().fDescent)
        
        
        self.text = text
        self.font = font
        self.color = color

    def execute(self, canvas):
        paint = skia.Paint(
            AntiAlias=True,
            Color=parse_color(self.color),
        )
        baseline = self.rect.top() \
            - self.font.getMetrics().fAscent
        canvas.drawString(self.text, float(self.rect.left()),
            baseline, self.font, paint)
    
class DrawRect:
    def __init__(self, rect, color):
        self.rect = rect
        self.color = color
    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
        )
        canvas.drawRect(self.rect, paint)

class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = skia.Rect.MakeLTRB(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, canvas):
        path = skia.Path().moveTo(
            self.rect.left(), self.rect.top()) \
                .lineTo(self.rect.right(),
                    self.rect.bottom())
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawPath(path, paint)

class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness
    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawRect(self.rect, paint)
        
class DrawRRect:
    def __init__(self, rect, radius, color):
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.color = color

    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
        )
        canvas.drawRRect(self.rrect, paint)

class Blend:
    def __init__(self, opacity, blend_mode, children):
        self.opacity = opacity
        self.blend_mode = blend_mode
        self.should_save = self.blend_mode or self.opacity < 1

        self.children = children
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.children:
            self.rect.join(cmd.rect)

    def execute(self, canvas):
        paint = skia.Paint(
            Alphaf=self.opacity,
            BlendMode=parse_blend_mode(self.blend_mode),
        )
        if self.should_save:
            canvas.saveLayer(None, paint)
        for cmd in self.children:
            cmd.execute(canvas)
        if self.should_save:
            canvas.restore()

def parse_blend_mode(blend_mode_str):
    if blend_mode_str == "multiply":
        return skia.BlendMode.kMultiply
    elif blend_mode_str == "difference":
        return skia.BlendMode.kDifference
    elif blend_mode_str == "destination-in":
        return skia.BlendMode.kDstIn
    elif blend_mode_str == "source-over":
        return skia.BlendMode.kSrcOver
    else:
        return skia.BlendMode.kSrcOver
def paint_tree(layout_object, display_list):
    cmds = []
    if layout_object.should_paint():
        cmds = layout_object.paint()
    for child in layout_object.children:
        paint_tree(child, cmds)

    if layout_object.should_paint():
        cmds = layout_object.paint_effects(cmds)
    display_list.extend(cmds)
def get_font(size, weight, style):
    key = (weight, style)
    if key not in FONTS:
        if weight == "bold":
            skia_weight = skia.FontStyle.kBold_Weight
        else:
            skia_weight = skia.FontStyle.kNormal_Weight
        if style == "italic":
            skia_style = skia.FontStyle.kItalic_Slant
        else:
            skia_style = skia.FontStyle.kUpright_Slant
        skia_width = skia.FontStyle.kNormal_Width
        style_info = \
            skia.FontStyle(skia_weight, skia_width, skia_style)
        font = skia.Typeface('Arial', style_info)
        FONTS[key] = font
    return skia.Font(FONTS[key], size)
def paint_visual_effects(node, cmds, rect):
    opacity = float(node.style.get("opacity", "1.0"))
    blend_mode = node.style.get("mix-blend-mode")

    if node.style.get("overflow", "visible") == "clip":
        border_radius = float(node.style.get(
            "border-radius", "0px")[:-2])
        if not blend_mode:
            blend_mode = "source-over"
        cmds.append(Blend(1.0, "destination-in", [
            DrawRRect(rect, border_radius, "white")
        ]))

    return [Blend(opacity, blend_mode, cmds)]
def parse_color(color):
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return skia.Color(r, g, b)
    elif color.startswith("#") and len(color) == 9:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        a = int(color[7:9], 16)
        return skia.Color(r, g, b, a)
    elif color in NAMED_COLORS:
        return parse_color(NAMED_COLORS[color])
    else:
        return skia.ColorBLACK
 


# ----------------------------------  Main --------------------------------- #


REFRESH_RATE_SEC = .033

class MeasureTime:
    def __init__(self):
        self.lock = threading.Lock()
        self.file = open("browser.trace", "w")
        self.file.write('{"traceEvents": [')
        ts = time.time() * 1000000
        self.file.write(
            '{ "name": "process_name",' +
            '"ph": "M",' +
            '"ts": ' + str(ts) + ',' +
            '"pid": 1, "cat": "__metadata",' +
            '"args": {"name": "Browser"}}')
        self.file.flush()

    def time(self, name):
        ts = time.time() * 1000000
        tid = threading.get_ident()
        self.lock.acquire(blocking=True)
        self.file.write(
            ', { "ph": "B", "cat": "_",' +
            '"name": "' + name + '",' +
            '"ts": ' + str(ts) + ',' +
            '"pid": 1, "tid": ' + str(tid) + '}')
        self.file.flush()
        self.lock.release()

    def stop(self, name):
        ts = time.time() * 1000000
        tid = threading.get_ident()
        self.lock.acquire(blocking=True)
        self.file.write(
            ', { "ph": "E", "cat": "_",' +
            '"name": "' + name + '",' +
            '"ts": ' + str(ts) + ',' +
            '"pid": 1, "tid": ' + str(tid) + '}')
        self.file.flush()
        self.lock.release()

    def finish(self):
        self.lock.acquire(blocking=True)
        for thread in threading.enumerate():
            self.file.write(
                ', { "ph": "M", "name": "thread_name",' +
                '"pid": 1, "tid": ' + str(thread.ident) + ',' +
                '"args": { "name": "' + thread.name + '"}}')
        self.file.write(']}')
        self.file.close()
        self.lock.release()

# done
class Task:
    def __init__(self, task_code, *args):
        self.task_code = task_code
        self.args = args
    def run(self):
        self.task_code(*self.args)
        self.task_code = None
        self.args = None
# done
class TaskRunner:
    def __init__(self, tab):
        self.condition = threading.Condition()
        self.tab = tab
        self.tasks = []
        # 主线程
        # 主线程对应 Tab 标签页，负责执行脚本、加载资源、渲染页面，以及运行事件处理器和回调函数等相关任务
        self.main_thread = threading.Thread(
            target=self.run,
            name="Main thread"
        )
        self.needs_quit = False
    
    def schedule_task(self, task):
        self.condition.acquire(blocking=True)
        self.tasks.append(task)
        self.condition.notify()
        self.condition.release()
    
    def set_needs_quit(self):
        self.condition.acquire(blocking=True)
        self.needs_quit = True
        self.condition.notify()
        self.condition.release()
    
    def clear_pending_tasks(self):
        self.condition.acquire(blocking=True)
        self.tasks.clear()
        self.condition.release()
    
    def start_thread(self):
        self.main_thread.start()
        
    def run(self):
        while True:
            self.condition.acquire(blocking=True)
            needs_quit = self.needs_quit
            self.condition.release() 
            if needs_quit:
                self.handle_quit()
                return 
            task = None
            self.condition.acquire(blocking=True)            
            if len(self.tasks) > 0:
                task = self.tasks.pop(0)
            self.condition.release()

            if task:
                task.run()
            
            self.condition.acquire(blocking=True)
            if len(self.tasks) == 0 and not self.needs_quit:
                self.condition.wait()
            self.condition.release()

class CommitData:
    '''
        Tab 绘制 display_list 时, 所需的 URL, 文档高度, 滚动位置
    '''
    def __init__(self, url, scroll, height, display_list):
        self.url = url
        self.height = height
        self.scroll = scroll
        self.display_list = display_list

# done
class JSContext:
    '''
        为每个浏览器标签页（Tab）创建一个独立的 JavaScript 执行环境
        并充当 Python 代码与在该环境中运行的 JavaScript 代码之间的桥梁
    '''
    def __init__(self, tab):
        self.tab = tab
        # 当加载新页面时，旧的 JSContext 会被标记为 discarded
        self.discarded = False
        self.interp = dukpy.JSInterpreter()
        # handle 与 node 的映射关系
        # handle：字典中条目的数量
        self.node_to_handle = {}
        self.handle_to_node = {}
        # （js函数名称, py函数名称）
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("XMLHttpRequest_send", self.XMLHttpRequest_send)
        self.interp.export_function("setTimeout", self.setTimeout)
        self.interp.export_function("requestAnimationFrame", self.requestAnimationFrame)
        
        self.interp.evaljs(RUNTIME_JS)
    
    # ---------------------------------- RAF --------------------------------- #
    def requestAnimationFrame(self):
        self.tab.browser.set_needs_animation_frame(self.tab)
    
    # ---------------------------------- setTimeout --------------------------------- #
    def setTimeout(self, handle, time):
        def run_callback():
            task = Task(self.dispatch_settimeout, handle)
            self.tab.task_runner.schedule_task(task)
        threading.Timer(time / 1000.0, run_callback).start()
    def dispatch_settimeout(self, handle):
        if self.discarded: return
        self.tab.browser.measure.time('script-settimeout')
        self.interp.evaljs(SETTIMEOUT_JS, handle=handle)
        self.tab.browser.measure.stop('script-settimeout')
        
    # ---------------------------------- XMLHttpRequest --------------------------------- #
    def XMLHttpRequest_send(self, method, url, body, isasync, handle):
        full_url = self.tab.url.resolve(url)
        # csp
        if not self.tab.allowed_request(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        # sop
        if full_url.origin() != self.tab.url.origin():
            raise Exception(
                "Cross-origin XHR request not allowed")
        def run_load():
            headers, response = full_url.request(self.tab.url, body)
            task = Task(self.dispatch_xhr_onload, response, handle)
            self.tab.task_runner.schedule_task(task)
            return response 
        if not isasync:
            # 同步
            return run_load()
        else:
            # 异步 启动一个线程, 与主线程并行
            threading.Thread(target=run_load).start()
    def dispatch_xhr_onload(self, out, handle):
        if self.discarded: return
        self.tab.browser.measure.time('script-xhr')
        do_default = self.interp.evaljs(
            XHR_ONLOAD_JS, out=out, handle=handle)
        self.tab.browser.measure.stop('script-xhr')
    
    # ---------------------------------- innerHTML_set --------------------------------- #
    def innerHTML_set(self, handle, s):
        """
        在 Python 端设置由句柄标识的 DOM 元素的 innerHTML。

        当 JavaScript 代码修改元素的 `innerHTML` 属性时，此方法被调用。
        它会解析传入的 HTML 字符串，用新生成的节点替换目标元素的
        现有子节点，并触发页面的重新渲染。

        参数:
            handle (int): 唯一标识目标 DOM 元素的整数句柄。
                          这个句柄是从 JavaScript 环境传递过来的。
            s (str):      要设置为元素新内容的 HTML 字符串。

        副作用:
            - 修改由 `handle` 标识的 DOM 元素的子节点。
            - 调用 `self.tab.render()` 来更新浏览器标签页的显示。
        """
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.tab.set_needs_render()

    # ---------------------------------- querySelectorAll --------------------------------- #
    def querySelectorAll(self, selector_text):
        # text -> handles
        # TagSelector / DescendantSelector
        selector = CSSParser(selector_text).selector()
        nodes = [node for node
             in tree_to_list(self.tab.nodes, [])
             if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]

    def get_handle(self, elt):
        # element -> handle
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle
    
    # ---------------------------------- getAttribute --------------------------------- #
    def getAttribute(self, handle, attr):
        # handle, 属性名 -> 属性值
        elt = self.handle_to_node[handle]
        attr = elt.attributes.get(attr, None)
        return attr if attr else ""



    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_JS, type=type, handle=handle)
        return not do_default
    
        
    def run(self, script, code):
        try:
            self.tab.browser.measure.time('script-load')
            self.interp.evaljs(code)
            self.tab.browser.measure.stop('script-load')
        except dukpy.JSRuntimeError as e:
            self.tab.browser.measure.stop('script-load')
            print("Script", script, "crashed", e)
       
class Browser:
    '''
        管理键盘事件(Tab管理鼠标)
        渲染流程:
            1. (浏览器线程)请求动画帧: set_needs_animation_frame
            2. (浏览器线程)安排动画帧: 将任务放入主线程的 TaskRunner
            3. 主线程: render
            4. 主线程: 调用 browser.commit
            5. (浏览器线程)进行光栅化和绘制: commit
    '''
    def __init__(self):
        self.chrome = Chrome(self)
        # sdl
        self.sdl_window = sdl2.SDL_CreateWindow(b"Browser",
            sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH, HEIGHT, sdl2.SDL_WINDOW_SHOWN)
        
        # Skia surface
        self.root_surface = skia.Surface.MakeRaster( # 创建一个基于 CPU 内存的栅格化表面的函数
            skia.ImageInfo.Make( # 描述了栅格表面的属性，例如尺寸和像素格式
                WIDTH, HEIGHT,
                ct=skia.kRGBA_8888_ColorType, # 颜色类型：红蓝绿透明度，每个占8位
                at=skia.kUnpremul_AlphaType)) # 代表 Alpha 类型
        # chrome_surface
        self.chrome_surface = skia.Surface(
            WIDTH, math.ceil(self.chrome.bottom))
        # tab_surface
        self.tab_surface = None
        
        
        self.tabs = []
        self.active_tab = None
        self.focus = None
        self.address_bar = ""
        self.lock = threading.Lock()
        self.active_tab_url = None
        self.active_tab_scroll = 0
        
        self.measure = MeasureTime()
        # 浏览器线程
        threading.current_thread().name = "Browser thread"
        
        # 根据系统的字节序来设置 RGBA 的掩码
        # 将像素缓冲区（从 Skia 表面获取的）传递给 SDL 以创建 surface
        if sdl2.SDL_BYTEORDER == sdl2.SDL_BIG_ENDIAN:
            self.RED_MASK = 0xff000000
            self.GREEN_MASK = 0x00ff0000
            self.BLUE_MASK = 0x0000ff00
            self.ALPHA_MASK = 0x000000ff
        else:
            self.RED_MASK = 0x000000ff
            self.GREEN_MASK = 0x0000ff00
            self.BLUE_MASK = 0x00ff0000
            self.ALPHA_MASK = 0xff000000
            
        self.animation_timer = None
        self.needs_animation_frame = False # 脏位 标记是否需要render（后台的tab不需要）
        self.needs_raster_and_draw = False # 脏位
        
        self.active_tab_height = 0
        self.active_tab_display_list = None
       
    def render(self):
        self.active_tab.task_runner.run()
        if self.active_tab.loaded:
            self.active_tab.run_animation_frame(self.active_tab_scroll) 
    
    def commit(self, tab, data):
        self.lock.acquire(blocking=True)
        if tab == self.active_tab:
            self.active_tab_url = data.url
            if data.scroll != None:
                self.active_tab_scroll = data.scroll
            self.active_tab_height = data.height
            if data.display_list:
                self.active_tab_display_list = data.display_list
            self.animation_timer = None
            self.set_needs_raster_and_draw()
        self.lock.release()

    
    def set_needs_animation_frame(self, tab):
        '''
            后台的tab不需要render
        '''
        self.lock.acquire(blocking=True)
        if tab == self.active_tab:
            self.needs_animation_frame = True
        self.lock.release()
    
    def set_needs_raster_and_draw(self):
        self.needs_raster_and_draw = True
       
    def raster_and_draw(self):
        self.lock.acquire(blocking=True)
        if not self.needs_raster_and_draw:
            self.lock.release()
            return
        self.measure.time('raster/draw')
        self.raster_chrome()
        self.raster_tab()
        self.draw()
        self.measure.stop('raster/draw')
        self.needs_raster_and_draw = False
        self.lock.release()
    
    def schedule_animation_frame(self):
        def callback():
            self.lock.acquire(blocking=True)
            scroll = self.active_tab_scroll
            active_tab = self.active_tab
            self.needs_animation_frame = False
            self.lock.release()
            task = Task(self.active_tab.run_animation_frame, scroll)
            active_tab.task_runner.schedule_task(task)
        self.lock.acquire(blocking=True)
        if self.needs_animation_frame and not self.animation_timer:
            self.animation_timer = \
                threading.Timer(REFRESH_RATE_SEC, callback)
            self.animation_timer.start()
        self.lock.release()

    def clamp_scroll(self, scroll):
        height = self.active_tab_height
        maxscroll = height - (HEIGHT - self.chrome.bottom)
        return max(0, min(scroll, maxscroll))

    def handle_down(self):
        self.lock.acquire(blocking=True)
        if not self.active_tab_height:
            self.lock.release()
            return
        self.active_tab_scroll = self.clamp_scroll(
            self.active_tab_scroll + SCROLL_STEP)
        self.set_needs_raster_and_draw()
        self.needs_animation_frame = True
        self.lock.release()
        
    def set_active_tab(self, tab):
        self.active_tab = tab
        self.active_tab_scroll = 0
        self.active_tab_url = None
        self.needs_animation_frame = True
        self.animation_timer = None

    
    def handle_click(self, e):
        self.lock.acquire(blocking=True)
        if e.y < self.chrome.bottom:
            self.focus = None
            self.chrome.click(e.x, e.y)
            self.set_needs_raster_and_draw()
        else:
            if self.focus != "content":
                self.focus = "content"
                self.chrome.focus = None
                self.set_needs_raster_and_draw()
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            task = Task(self.active_tab.click, e.x, tab_y)
            self.active_tab.task_runner.schedule_task(task)
        self.lock.release()
    
    
    def handle_key(self, char):
        self.lock.acquire(blocking=True)
        if not (0x20 <= ord(char) < 0x7f): return
        if self.chrome.keypress(char):
            self.set_needs_raster_and_draw()
        elif self.focus == "content":
            task = Task(self.active_tab.keypress, char)
            self.active_tab.task_runner.schedule_task(task)
        self.lock.release()
    
    def schedule_load(self, url, body=None):
        self.active_tab.task_runner.clear_pending_tasks()
        task = Task(self.active_tab.load, url, body)
        self.active_tab.task_runner.schedule_task(task)  
    
    def handle_enter(self):
        self.lock.acquire(blocking=True)
        if self.chrome.enter():
            self.set_needs_raster_and_draw()
        self.lock.release()
    
          
    # 获取锁   
    def new_tab(self, url):
        self.lock.acquire(blocking=True)
        self.new_tab_internal(url)
        self.lock.release()
    # 不获取锁
    def new_tab_internal(self, url):
        new_tab = Tab(self, HEIGHT - self.chrome.bottom)
        self.tabs.append(new_tab)
        self.set_active_tab(new_tab)
        self.schedule_load(url)  

    def raster_tab(self):
        if self.active_tab_height == None:
            return
        if not self.tab_surface or \
                self.active_tab_height != self.tab_surface.height():
            self.tab_surface = skia.Surface(WIDTH, self.active_tab_height)

        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        for cmd in self.active_tab_display_list:
            cmd.execute(canvas)

    def handle_quit(self):
        self.measure.finish()
        for tab in self.tabs:
            tab.task_runner.set_needs_quit()
        sdl2.SDL_DestroyWindow(self.sdl_window)
    
    def raster_chrome(self):
        canvas = self.chrome_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        for cmd in self.chrome.paint():
            cmd.execute(canvas)
 
    
    def draw(self):
        '''
        作用:   
            将 Skia 渲染的浏览器标签页内容和浏览器 UI 合成到一起，然后将这个最终的图像通过 SDL 显示在窗口中。
            它充当了 Skia (渲染引擎) 和 SDL (窗口和显示系统) 之间的桥梁。
            
        Skia 高质量的2D图形渲染
        SDL2 跨平台的窗口管理和底层硬件交互
        -------------------------------------
            用 Skia 绘制好网页内容 
            -> 将绘制结果转换为原始像素数据 
            -> 用这些数据创建一个 SDL 表面 
            -> 将这个 SDL 表面复制到窗口的显示表面 
            -> 更新窗口，让用户看到最新的内容。
        '''
        
        # 该画布绑定到 root_surface
        canvas = self.root_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        
        # 将 tab_surface 复制到 canvas 上
        tab_rect = skia.Rect.MakeLTRB(
            0, self.chrome.bottom, WIDTH, HEIGHT)
        tab_offset = self.chrome.bottom - self.active_tab.scroll
        canvas.save()
        canvas.clipRect(tab_rect)
        canvas.translate(0, tab_offset)
        self.tab_surface.draw(canvas, 0, 0)
        canvas.restore()

        # 将 chrome_surface 复制到 canvas 上
        chrome_rect = skia.Rect.MakeLTRB(
            0, 0, WIDTH, self.chrome.bottom)
        canvas.save()
        canvas.clipRect(chrome_rect)
        self.chrome_surface.draw(canvas, 0, 0)
        canvas.restore()
        

        # This makes an image interface to the Skia surface, but
        # doesn't actually copy anything yet.
        skia_image = self.root_surface.makeImageSnapshot()
        skia_bytes = skia_image.tobytes()
        
        # 从一个已有的像素数据缓冲区 (skia_bytes) 创建一个 SDL 表面 (surface)。
        # 将一个图形库（Skia）绘制的内容显示在由另一个库（SDL）管理的窗口中。
        depth = 32 # Bits per pixel
        pitch = 4 * WIDTH # Bytes per row
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes, WIDTH, HEIGHT, depth, pitch,
            self.RED_MASK, self.GREEN_MASK,
            self.BLUE_MASK, self.ALPHA_MASK)

        rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        # SDL_BlitSurface is what actually does the copy.
        sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        sdl2.SDL_UpdateWindowSurface(self.sdl_window)
        

 
class Chrome:
    '''
        浏览器上的工具栏，除了显示的网页外的内容
    '''
    def __init__(self, browser):
        self.browser = browser
        self.focus = None
        self.address_bar = ""
        
        self.font = get_font(20, "normal", "roman")
        self.font_height = linespace(self.font)
        
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2*self.padding
        
        
        # Button: + 
        plus_width = self.font.measureText("+") + 2*self.padding

        self.newtab_rect = skia.Rect.MakeLTRB(
           self.padding, self.padding,
           self.padding + plus_width,
           self.padding + self.font_height)
        
        # 地址栏
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2*self.padding
        self.bottom = self.urlbar_bottom
        
        # 后退按钮 <
        back_width = self.font.measureText("<") + 2*self.padding
        self.back_rect = skia.Rect.MakeLTRB(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding)
        
        # 地址栏
        self.address_rect = skia.Rect.MakeLTRB(
            self.back_rect.top() + self.padding,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding)

        self.bottom = self.urlbar_bottom

    def blur(self):
        self.focus = None
    
    def keypress(self, char):
        if self.focus == "address bar":
            self.address_bar += char  
            return True
        return False
    
    def enter(self):
        if self.focus == "address bar":
            self.browser.active_tab.load(URL(self.address_bar))
            self.focus = None
            return True
        return False

    
    def click(self, x, y):
        if self.newtab_rect.contains(x, y):
            self.browser.new_tab_internal(URL("https://browser.engineering/"))
        elif self.back_rect.contains(x, y):
            task = Task(self.browser.active_tab.go_back)
            self.browser.active_tab.task_runner.schedule_task(task)
        elif self.address_rect.contains(x, y):
            self.focus = "address bar"
            self.address_bar = ""
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains(x, y):
                    self.browser.active_tab = tab
                    active_tab = self.browser.active_tab
                    task = Task(active_tab.set_needs_render)
                    active_tab.task_runner.schedule_task(task)
                    break


    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right() + self.padding
        tab_width =self.font.measureText("Tab X") + 2*self.padding
        return skia.Rect.MakeLTRB(
            tabs_start + tab_width * i, self.tabbar_top,
            tabs_start + tab_width * (i + 1), self.tabbar_bottom)
        
    def paint(self):
        cmds = []
        
        
        # 界面底部的分割线
        cmds.append(DrawLine(0, self.bottom, WIDTH, self.bottom, "black", 1))
        
        # 绘制 +
        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(
            DrawText(self.newtab_rect.left() + self.padding,
                     self.newtab_rect.top(),
                     "+",
                     self.font,"black"))
        
        # 绘制 Tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(DrawLine(
                bounds.left(), 0, bounds.left(), bounds.bottom(),
                "black", 1))
            cmds.append(DrawLine(
                bounds.right(), 0, bounds.right(), bounds.bottom(),
                "black", 1))
            cmds.append(DrawText(
                bounds.left() + self.padding, bounds.top() + self.padding,
                "Tab {}".format(i), self.font, "black"))

            if tab == self.browser.active_tab:
                cmds.append(DrawLine(
                    0, bounds.bottom(), bounds.left(), bounds.bottom(),
                    "black", 1))
                cmds.append(DrawLine(
                    bounds.right(), bounds.bottom(), WIDTH, bounds.bottom(),
                    "black", 1))
        

         
        # 绘制后退按钮
        cmds.append(DrawOutline(self.back_rect, "black", 1))
        cmds.append(DrawText(
            self.back_rect.left() + self.padding,
            self.back_rect.top(),
            "<", self.font, "black"))      
    
        # 绘制地址栏
        cmds.append(DrawOutline(self.address_rect, "black", 1))          
        
        # 地址栏成为焦点时  
        if self.focus == "address bar":
            cmds.append(DrawText(
                self.address_rect.left() + self.padding,
                self.address_rect.top(),
                self.address_bar, self.font, "black"))
            
            # 光标
            w = self.font.measureText(self.address_bar)
            cmds.append(DrawLine(
                self.address_rect.left() + self.padding + w,
                self.address_rect.top(),
                self.address_rect.left() + self.padding + w,
                self.address_rect.bottom(),
                "red", 1))
        else:
            url = str(self.browser.active_tab.url)
            cmds.append(DrawText(
                self.address_rect.left() + self.padding,
                self.address_rect.top(),
                url, self.font, "black"))
            
        return cmds
   
class Tab:
    '''
        渲染流程:
            1. (浏览器线程)请求动画帧: set_needs_animation_frame
            2. (浏览器线程)安排动画帧: 将任务放入主线程的 TaskRunner
            3. 主线程: render
            4. 主线程: 调用 browser.commit
            5. (浏览器线程)进行光栅化和绘制: commit
    '''
    def __init__(self, browser, tab_height):
        self.history = [] # 存储浏览历史
        self.tab_height = tab_height
        self.focus = None # foucs node
        self.url = None # URL对象
        self.scroll = 0
        self.scroll_changed_in_tab = False # TODO
        self.needs_raf_callbacks = False # TODO
        self.needs_render = False # 脏位, 在 HTML 变更时设置 needs_render，而无需直接调用 render
        self.js = None
        self.browser = browser
        
        self.loaded = False # TODO
        
        self.task_runner = TaskRunner(self)
        self.task_runner.start_thread()
        
                
    def load(self, url, payload=None):
        '''
            url: 要访问的新URL
            self.url: 请求来源页面的 URL
        '''
        self.loaded = False
        self.scroll = 0
        
        self.scroll_changed_in_tab = True # TODO
        self.task_runner.clear_pending_tasks()
        
        headers, body = url.request(self.url, payload)
       
        self.url = url
        self.history.append(url)  # 历史记录
        
        # 仅加载来自资源列表的资源
        self.allowed_origins = None
        if "content-security-policy" in headers:
           csp = headers["content-security-policy"].split()
           if len(csp) > 0 and csp[0] == "default-src":
                self.allowed_origins = csp[1:]
        
        
        # 第1次遍历：生成 node tree
        self.nodes = HTMLParser(body).parse()
        
        
        # js
        if self.js: self.js.discarded = True
        self.js = JSContext(self)
        # 找到所有 JS 的 url(string)
        scripts = [node.attributes["src"] for node
                   in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == "script"
                   and "src" in node.attributes]
        for script in scripts:
            script_url = url.resolve(script)
            
            # 是否在资源列表
            if not self.allowed_request(script_url):
                print("Blocked script", script, "due to CSP")
                continue
            
            try:
                header, body = script_url.request(url)
            except:
                continue
            # 放入任务队列
            task = Task(self.js.run, script_url, body)
            self.task_runner.schedule_task(task)

        # 获取 css 文件
        self.rules = DEFAULT_STYLE_SHEET.copy()
        links = [node.attributes["href"]
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "link"
                 and node.attributes.get("rel") == "stylesheet"
                 and "href" in node.attributes]
        for link in links:
            style_url = url.resolve(link)
            if not self.allowed_request(style_url):
                print("Blocked style", link, "due to CSP")
                continue
            try:
                header, body = style_url.request(url)
            except:
                continue
            self.rules.extend(CSSParser(body).parse())
        
        # 将原本[加载页面, 样式计算, 布局, 绘制, 显示] 中的 [样式计算, 布局, 绘制, 显示] 放到 render()
        self.set_needs_render()
        self.loaded = True
        
    def set_needs_render(self):
        self.needs_render = True
        self.browser.set_needs_animation_frame(self)
        
    def clamp_scroll(self, scroll):
        height = math.ceil(self.document.height + 2*VSTEP)
        maxscroll = height - self.tab_height
        return max(0, min(scroll, maxscroll))
        
    # TODO
    def run_animation_frame(self, scroll):
        if not self.scroll_changed_in_tab:
            self.scroll = scroll
        self.browser.measure.time('script-runRAFHandlers')
        self.js.interp.evaljs("__runRAFHandlers()")
        self.browser.measure.stop('script-runRAFHandlers')

        self.render()

        scroll = None
        if self.scroll_changed_in_tab:
            scroll = self.scroll
        document_height = math.ceil(self.document.height + 2*VSTEP)
        commit_data = CommitData(
            self.url, scroll, document_height, \
            self.display_list)
        self.display_list = None
        self.browser.commit(self, commit_data)
        self.scroll_changed_in_tab = False
    
    def render(self):
        if not self.needs_render: return 
        self.browser.measure.time('render')
        # 第2次遍历：生成 style tree
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        
        # 第3次遍历：生成 layout tree
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        
        # 第4次遍历：生成绘制列表 (Painting)
        self.display_list = []
        paint_tree(self.document, self.display_list)
        
        # 渲染完后
        self.needs_render = False
        
        clamped_scroll = self.clamp_scroll(self.scroll)
        if clamped_scroll != self.scroll:
            self.scroll_changed_in_tab = True
        self.scroll = clamped_scroll
        
        self.browser.measure.stop('render')

      
    
    def click(self, x, y):
        '''
            渲染是从元素到布局对象，再到页面坐标，最后到屏幕坐标；
            而点击处理则相反，从屏幕坐标开始，转换为页面坐标，布局对象，最后是元素
        '''
        
        # 处理点击事件前，确保布局树是最新状态
        self.render()
        self.focus = None
        # 屏幕坐标 x, y
        
        # 页面坐标
        y += self.scroll
        # 页面坐标转换为布局对象
        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x <obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]
        if not objs: return 
        elt = objs[-1].node # 在坐标范围内的，布局树的最下层的布局对象对应的 styled node tree 的 node
        
        # 向上遍历
        while elt:
            if isinstance (elt, Text):
                pass
            
            # 处理：链接
            elif elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event("click", elt): return
                url = self.url.resolve(elt.attributes["href"])
                self.load(url)
                return 
            # 处理：输入框
            elif elt.tag == "input":
                elt.attributes["value"] = ""
                if self.focus:
                    self.focus.is_focused = False
                self.focus = elt
                elt.is_focused = True
                self.set_needs_render()
                return
            elif elt.tag == "button":
                while elt.parent:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            
            elt = elt.parent
      
    def allowed_request(self, url):
        return self.allowed_origins == None or \
            url.origin() in self.allowed_origins
              
    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def keypress(self, char):
        if self.focus:
            if self.js.dispatch_event("keydown", self.focus): return
            self.focus.attributes["value"] += char
            self.set_needs_render()

  
    def submit_form(self, elt):
        if self.js.dispatch_event("submit", elt): return
        inputs = [node for node in tree_to_list(elt, [])
                  if isinstance(node, Element)
                  and node.tag == "input"
                  and "name" in node.attributes]
        body = ""
        # &k1=v1&k2=v2&k3=v3
        for input in inputs:
            name = input.attributes["name"]
            value = input.attributes.get("value", "")
            
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            
            body += "&" + name + "=" + value
        # k1=v1&k2=v2&k3=v3
        body = body[1:]
        
        url = self.url.resolve(elt.attributes["action"])
        self.load(url, body)
        
    def scrolldown(self):
        max_y = max(self.document.height + 2*VSTEP - self.tab_height, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def raster(self, canvas):
        for cmd in self.display_list:
            cmd.execute(canvas)

    
   
# sdl 的 mainloop
def mainloop(browser):
    event = sdl2.SDL_Event()
    while True:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                browser.handle_quit()
                sdl2.SDL_Quit()
                sys.exit()
            # 绑定事件
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                browser.handle_click(event.button)
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_RETURN:
                    browser.handle_enter()
                elif event.key.keysym.sym == sdl2.SDLK_DOWN:
                    browser.handle_down()
            elif event.type == sdl2.SDL_TEXTINPUT:
                browser.handle_key(event.text.text.decode('utf8'))
        
        if browser.active_tab.task_runner.needs_quit:
                break

        browser.raster_and_draw()
        browser.schedule_animation_frame()

 

if __name__ == "__main__":
    sdl2.SDL_Init(sdl2.SDL_INIT_EVENTS)
    browser = Browser()
    browser.new_tab(URL(sys.argv[1]))
    browser.raster_and_draw()
    mainloop(browser)
    

    