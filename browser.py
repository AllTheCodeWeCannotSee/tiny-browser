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
         
    def request(self):
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


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, 
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()
    def scrollup(self, e):
        self.scroll -= SCROLL_STEP
        self.draw()
    def draw(self):
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=word, font=font, anchor="nw")
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
        self.draw()

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
    '''
        构建 HTML 树
    '''
    def __init__(self, body):
        self.body = body
        self.unfinished = [] # 未完成的 node 栈（文本、元素）
        self.HEAD_TAGS = [
            "base", "basefont", "bgsound", "noscript",
            "link", "meta", "title", "style", "script",
        ]
        self.SELF_CLOSING_TAGS = [
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        ]

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
        elif tag in self.SELF_CLOSING_TAGS:
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
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and \
                tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break


class Layout:
    def __init__(self, tree):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.line = []
        self.recurse(tree)
        self.flush()
        
    def word(self, word): 
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
         # 完成一行后，处理 line 缓冲区
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()
            
        if self.cursor_x + w > WIDTH - HSTEP:
            self.cursor_y += font.metrics("linespace") * 1.25
            self.cursor_x = HSTEP
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")
    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        self.cursor_y += font.metrics("linespace") * 1.25
        self.cursor_x = HSTEP
        self.line = []
    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "br":
            self.flush()
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP
        elif tag == "small":
            self.size += 2
        elif tag == "/big":
            self.size -= 4
            
    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)
  

        
def parseHttp(url):
    if "/" not in url:
        url += "/"
    host, path = url.split('/', 1)
    if ":" in host:
            host, port = host.split(":", 1)
    else:
        port = 80
    path = "/" + path
    return host, port, path

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

if __name__ == "__main__":
    # body = URL(sys.argv[1]).request()
    # nodes = HTMLParser(body).parse()
    # print_tree(nodes)
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()