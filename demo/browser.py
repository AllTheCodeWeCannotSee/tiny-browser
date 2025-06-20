import socket
import ssl
import tkinter
import tkinter.font

# ---------------------------------- URL --------------------------------- #
# url -> text body
class URL:
    # url -> schema, host, port
    def __init__(self, url):
        self.url = url
        # https://browser.engineering/http.html
        # http://localhost:5173/
        self.schema, url_host_port_path = self.url.split('://')
        host_port, self.path =url_host_port_path.split('/', 1)
        
        if ':' in host_port:
            self.host, self.port = host_port.split(':')
            self.port = int(self.port)
        else:
            self.host = host_port
            
        if self.schema == 'http':
            self.port = 80
        elif self.schema == 'https':
            self.port = 443

    def request(self):
        # ---------------------------------- connect --------------------------------- #
        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        
        s.connect((self.host, self.port))
        if self.schema == 'https':
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
        
        # ---------------------------------- send --------------------------------- #
        # GET /index.html HTTP/1.1
        # Host: www.example.com       
        request = ""
        request += f'GET /{self.path} HTTP/1.0\r\n'
        request += f'Host: {self.host}\r\n'
        request += '\r\n'
        s.send(request.encode('utf-8'))
        
        # ---------------------------------- response --------------------------------- #
        response = s.makefile("r", encoding="utf-8", newline="\r\n")
        version, status, explanation = response.readline().split(" ", 2)
        
        headers = {}
        
        while True:
            line = response.readline()
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            headers[header.casefold()] = value.strip()
        content = response.read()
        s.close()

        return headers, content
        
# ---------------------------------- HTML --------------------------------- #
# text body -> node tree
SELF_CLOSING_TAGS=[
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        ]
class HTMLParser:
    '''
        in: <div>hello<p>world? world!</p></div>
        out: Element(div)
    '''
    def __init__(self, body):
        self.body = body.strip()
        self.root = None
        self.unfinished = []
    
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

    def parse(self):
        """
        执行解析过程。
        - 采用简单的状态机逻辑，逐字符解析。
        - 正确处理标签的嵌套和闭合。
        - 忽略注释和 Doctype 等复杂结构。
        """
        buffer = ""
        in_tag = False # 一个简单的状态标志，表示当前是否在 < > 内部

        for char in self.body:
            if char == '<':
                # 进入标签模式前，如果 buffer 中有内容，说明是文本节点
                if buffer and self.unfinished:
                    parent = self.unfinished[-1]
                    text_node = Text(buffer)
                    text_node.parent = parent
                    parent.children.append(text_node)
                buffer = "" # 清空 buffer，准备接收标签名
                in_tag = True
            elif char == '>':
                # 退出标签模式，此时 buffer 中的内容是完整的标签名
                in_tag = False
                tag_name = buffer.strip()

                if not tag_name: continue # 处理 <> 这种情况
                tag_name, attributes = self.get_attributes(tag_name)

                # 判断是开始标签还是结束标签
                if tag_name.startswith('/'):
                    # 结束标签，例如 </p>
                    # 理想情况下，我们应该检查它是否与栈顶标签匹配
                    # if self.unfinished and self.unfinished[-1].tag == tag_name[1:]:
                    if self.unfinished:
                        self.unfinished.pop() # 从堆栈中弹出一个开放的标签
                elif tag_name in SELF_CLOSING_TAGS:
                    parent = self.unfinished[-1]
                    node = Element(tag_name)
                    parent.children.append(node)
                else:
                    # 开始标签，例如 <p>
                    element_node = Element(tag_name)
                    
                    if not self.root:
                        # 如果还没有根节点，那么这就是根节点
                        self.root = element_node
                    
                    if self.unfinished:
                        # 将新节点作为当前开放标签的子节点
                        parent = self.unfinished[-1]
                        element_node.parent = parent
                        parent.children.append(element_node)
                    
                    # 将新节点压入堆栈，因为它现在是一个开放的标签
                    self.unfinished.append(element_node)

                buffer = "" # 清空 buffer
            else:
                # 不在 < > 之间，或者在 < > 之间，都统一追加到 buffer
                buffer += char
        
        # 返回构建好的树的根节点
        return self.root
     
class Text:
    def __init__(self, text):
        self.text = text
        self.children = []
        self.parent = None

class Element:
    def __init__(self, tag):
        self.tag = tag
        self.children = []
        self.parent = None
        

         

# ---------------------------------- CSS --------------------------------- #
# css text -> styled tree


# ---------------------------------- Layout --------------------------------- #
# styled tree -> layout tree
# in: [Tag(div), Text(hello), Tag(i), Text(world? world!)]
# out: [(x, y, hello, font), (x, y, world, font), (x, y, ?, font), (x, y, world, font), (x, y, !, font)]


HSTEP = 13
VSTEP = 18
class Layout:
    def __init__(self, tree):
        self.tree = tree
        self.line = []
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        
        self.size = 12
        self.weight = "normal"
        self.style = "roman"
        
        self.rescurse(self.tree)
    
    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "br":
            self.flush()



            
    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP
    
    
        
    
    def rescurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)

            for child in tree.children:
                self.rescurse(child)
            self.close_tag(tree.tag)
            
            
    def word(self, word):
        font = tkinter.font.Font(
            size=self.size,
            weight=self.weight,
            slant=self.style,
        )
        w = font.measure(word)
        
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()

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
        
        

# ---------------------------------- Paint --------------------------------- #


    


# ---------------------------------- Browser --------------------------------- #

WIDTH = 800
HEIGHT = 600
SCROLL_STEP = 100

class Browser:
    def __init__(self):
        self.scroll = 0
        self.display_list = []
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()
        
        self.window.bind("<Down>", self.scrolldown)
    
    def scrolldown(self, event):
        self.scroll += SCROLL_STEP
        self.draw()
        
    
    def load(self, url):
        headers, body = url.request()
        # token 序列
        self.nodes = HTMLParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        for cursor_x, cursor_y, word, font in self.display_list:

            self.canvas.create_text(
                cursor_x,
                cursor_y - self.scroll,
                text=word,
                font=font,
                anchor="nw",
                )

if __name__ == '__main__':
    import sys
    url = URL(sys.argv[1])
    browser = Browser()
    browser.load(url)
    browser.window.mainloop()
    

    
    
    


    

    


    

