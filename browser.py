import socket
import ssl
import os
import tkinter
import tkinter.font
import sys
import urllib.parse
import dukpy

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

COOKIE_JAR = {}

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




class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    def contains_point(self, x, y):
        return x >= self.left and x < self.right \
            and y >= self.top and y < self.bottom 

class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        canvas.create_line(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            fill=self.color, width=self.thickness)

class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            outline=self.color,
            width=self.thickness
        )
        

class Chrome:
    '''
        浏览器上的工具栏，除了显示的网页外的内容
    '''
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2*self.padding
        
        self.bottom = self.tabbar_bottom
        
        self.focus = None
        self.address_bar = ""
        
        # Button: + 
        plus_width = self.font.measure("+") + 2*self.padding
        self.newtab_rect = Rect(
            self.padding,
            self.padding,
            self.padding + plus_width,
            self.padding + self.font_height
        )
        
        # 地址栏
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2*self.padding
        self.bottom = self.urlbar_bottom
        
        # 后退按钮 <
        back_width = self.font.measure("<") + 2*self.padding
        self.back_rect = Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding)
        
        # 地址栏
        self.address_rect = Rect(
            self.back_rect.top + self.padding,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding)
    
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
    
    def click(self, x, y):
        self.focus = None
        
        if self.newtab_rect.contains_point(x, y):
            self.browser.new_tab(URL("https://browser.engineering/"))
        elif self.back_rect.contains_point(x, y):
            self.browser.active_tab.go_back()
        elif self.address_rect.contains_point(x, y):
            self.focus = "address bar"
            self.address_bar = ""
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains_point(x, y):
                    self.browser.active_tab = tab
                    break

    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width =self.font.measure("Tab X") + 2*self.padding
        return Rect(
            tabs_start + tab_width * i, self.tabbar_top,
            tabs_start + tab_width * (i + 1), self.tabbar_bottom)
    def paint(self):
        cmds = []
        
        # 绘制白色矩形
        cmds.append(DrawRect(Rect(0, 0, WIDTH, self.bottom), "white"))
        
        # 界面底部的分割线
        cmds.append(DrawLine(0, self.bottom, WIDTH, self.bottom, "black", 1))
        
        # 绘制 +
        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(
            DrawText(self.newtab_rect.left + self.padding,
                     self.newtab_rect.top,
                     "+",
                     self.font,"black"))
        
        # 绘制 Tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(DrawLine(
                bounds.left, 0, bounds.left, bounds.bottom,
                "black", 1))
            cmds.append(DrawLine(
                bounds.right, 0, bounds.right, bounds.bottom,
                "black", 1))
            cmds.append(DrawText(
                bounds.left + self.padding, bounds.top + self.padding,
                "Tab {}".format(i), self.font, "black"))
            
        # 突出显示活动页
        if tab == self.browser.active_tab:
            cmds.append(DrawLine(
                0, bounds.bottom, bounds.left, bounds.bottom,
                "black", 1))
            cmds.append(DrawLine(
                bounds.right, bounds.bottom, WIDTH, bounds.bottom,
                "black", 1))
        

         
        # 绘制后退按钮
        cmds.append(DrawOutline(self.back_rect, "black", 1))
        cmds.append(DrawText(
            self.back_rect.left + self.padding,
            self.back_rect.top,
            "<", self.font, "black"))      
    
        # 绘制地址栏
        cmds.append(DrawOutline(self.address_rect, "black", 1))          
        
        # 地址栏成为焦点时  
        if self.focus == "address bar":
            cmds.append(DrawText(
                self.address_rect.left + self.padding,
                self.address_rect.top,
                self.address_bar, self.font, "black"))
            
            # 光标
            w = self.font.measure(self.address_bar)
            cmds.append(DrawLine(
                self.address_rect.left + self.padding + w,
                self.address_rect.top,
                self.address_rect.left + self.padding + w,
                self.address_rect.bottom,
                "red", 1))
        else:
            url = str(self.browser.active_tab.url)
            cmds.append(DrawText(
                self.address_rect.left + self.padding,
                self.address_rect.top,
                url, self.font, "black"))
            
        return cmds

class Browser:
    '''
        管理键盘事件（Tab管理鼠标）
    '''
    def __init__(self):
        
        self.tabs = []
        self.active_tab = None
        self.focus = None
        
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, 
            width=WIDTH,
            height=HEIGHT,
            bg="white"
        )
        self.canvas.pack()
        
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)
        
        self.chrome = Chrome(self)
        
    def draw(self):
        self.canvas.delete("all")
        self.active_tab.draw(self.canvas, self.chrome.bottom)
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)
    
    def handle_enter(self, e):
        self.chrome.enter()
        self.draw()
        
    def handle_key(self, e):
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return
        
        if self.chrome.keypress(e.char):
            self.draw()
        elif self.focus == "content":
            self.active_tab.keypress(e.char)
            self.draw()
        
        
        
    def handle_down(self, e):
        self.active_tab.scrolldown()
        self.draw()
        
    def handle_up(self, e):
        self.active_tab.scrollup()
        self.draw()
        
    def handle_click(self, e):
        if e.y < self.chrome.bottom:
            self.focus = None
            self.chrome.click(e.x, e.y)
        else:
            self.focus = "content"
            self.chrome.blur()
            
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
        self.draw()
    def new_tab(self, url):
        new_tab = Tab(HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()
        
class Tab:
    def __init__(self, tab_height):
        self.scroll = 0
        self.url = None # URL对象
        self.tab_height = tab_height
        
        # 存储浏览历史
        self.history = []
        
        # foucs node
        self.focus = None
      
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
            self.render()

    # 处理点击，包含点击链接    
    def click(self, x, y):
        '''
            渲染是从元素到布局对象，再到页面坐标，最后到屏幕坐标；
            而点击处理则相反，从屏幕坐标开始，转换为页面坐标，布局对象，最后是元素
        '''
        if self.focus:
            self.focus.is_focused = False
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
                return self.load(url)
            # 处理：输入框
            elif elt.tag == "input":
                if self.js.dispatch_event("click", elt): return
                self.focus = elt
                elt.attributes["value"] = ""
                self.focus = elt
                elt.is_focused = True
                return self.render()
            elif elt.tag == "button":
                if self.js.dispatch_event("click", elt): return
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            
            elt = elt.parent
        
        self.render()
      
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

    def scrollup(self):
        self.scroll -= SCROLL_STEP

    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.rect.top > self.scroll + self.tab_height: continue
            if cmd.rect.bottom < self.scroll: continue
            cmd.execute(self.scroll - offset, canvas)
    def load(self, url, payload=None):
        '''
            url: 要访问的新URL
            self.url: 请求来源页面的 URL
        '''
        # 历史记录
        self.history.append(url)
        self.url = url
        headers, body = url.request(self.url, payload)
        
        # 仅加载来自资源列表的资源
        self.allowed_origins = None
        if "content-security-policy" in headers:
           csp = headers["content-security-policy"].split()
           if len(csp) > 0 and csp[0] == "default-src":
                self.allowed_origins = []
                for origin in csp[1:]:
                    self.allowed_origins.append(URL(origin).origin())
        
        
        # 第1次遍历：生成 node tree
        self.nodes = HTMLParser(body).parse()
        
        # js
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
            self.js.run(script, body)

        
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
            try:
                header, body = style_url.request(url)
            except:
                continue
            self.rules.extend(CSSParser(body).parse())
        
        # 将原本[加载页面, 样式计算, 布局, 绘制, 显示] 中的 [样式计算, 布局, 绘制, 显示] 放到 render()
        self.render()
        
    def render(self):
        # 第2次遍历：生成 style tree
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        
        # 第3次遍历：生成 layout tree
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        
        # 第4次遍历：生成绘制列表 (Painting)
        self.display_list = []
        paint_tree(self.document, self.display_list)
   
RUNTIME_JS = open("runtime.js").read()
EVENT_DISPATCH_JS = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"


class JSContext:
    def __init__(self, tab):
        self.tab = tab
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
        
        self.interp.evaljs(RUNTIME_JS)
    
    def XMLHttpRequest_send(self, method, url, body):
        full_url = self.tab.url.resolve(url)
        
        # 同源策略
        if not self.tab.allowed_request(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        headers, out = full_url.request(self.tab.url, body)
        
        # 同源策略
        if full_url.origin() != self.tab.url.origin():
            raise Exception("Cross-origin XHR request not allowed")
        
        return out
     
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
        self.tab.render()


    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_JS, type=type, handle=handle)
        return not do_default
    
    
    # handle, 属性名 -> 属性值
    def getAttribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        attr = elt.attributes.get(attr, None)
        return attr if attr else ""
        
    # element -> handle
    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    # text -> handles
    def querySelectorAll(self, selector_text):
        # TagSelector / DescendantSelector
        selector = CSSParser(selector_text).selector()
        nodes = [node for node
             in tree_to_list(self.tab.nodes, [])
             if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]
        
    def run(self, script, code):
        try:
            return self.interp.evaljs(code)
        except dukpy.JSRuntimeError as e:
            print("Script", script, "crashed", e)
        
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

    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag != "input" and self.node.tag !=  "button")
    
    def self_rect(self):
        return Rect(self.x, self.y, self.x + self.width, self.y + self.height)
        
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

        if self.layout_mode() == "inline":
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))
        
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
            
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
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        font = get_font(size, weight, style)

        self.cursor_x += w + font.measure(" ")
    
    def word(self, node, word): 
        '''
            作用：就像一个打字员在排版
                它拿到一个单词，看看当前行还够不够地方放下它。如果不够，就另起一行。
                然后，把这个单词“写”在当前行的末尾，并把笔向右移动相应的距离，准备写下一个字
            self.children: 一个个 LineLayout 实例
            node: TextNode
            word: str
        '''
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
            self.new_line()
            
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)
        
        self.cursor_x += w + font.measure(" ")
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

        max_ascent = max([word.font.metrics("ascent") 
                          for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")
        max_descent = max([word.font.metrics("descent")
                           for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)
    def paint(self):
        return []
        
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
        
        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")
    def paint(self):
        color = self.node.style["color"]
        return [DrawText(self.x, self.y, self.word, self.font, color)]

        
INPUT_WIDTH_PX = 200
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
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)
        
        self.width = INPUT_WIDTH_PX

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")
    
    def self_rect(self):
        return Rect(self.x, self.y, self.x + self.width, self.y + self.height) 
    
    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        
        # 绘制背景
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
        
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
            cx = self.x + self.font.measure(text)
            cmds.append(DrawLine(
                cx, self.y, cx, self.y + self.height, "black", 1))
        
        return cmds
        
        
        
        


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.rect = Rect(x1, y1,
            x1 + font.measure(text), y1 + font.metrics("linespace"))
        self.text = text
        self.font = font
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.rect.left, self.rect.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw',
            fill=self.color)
    
class DrawRect:
    def __init__(self, rect, color):
        self.rect = rect
        self.color = color
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width=0,
            fill=self.color)


def paint_tree(layout_object, display_list):
    if layout_object.should_paint():
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
    return host, int(port), path

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
    Browser().new_tab(URL(sys.argv[1]))
    tkinter.mainloop()
    
    # Browser().load(URL(sys.argv[1]))
    # tkinter.mainloop()
    

    