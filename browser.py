import socket
import ssl
import os
import tkinter
import sys



WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 200
HSTEP, VSTEP = 13, 18

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
        self.width = WIDTH
        self.height = HEIGHT
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, 
            width=self.width,
            height=self.height
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.scrollwheel)
        self.window.bind("<Configure>", self.handle_resize)
        self.display_list = []
        self.text_content = "" 
        # 用于resize防抖的计时器
        self.resize_timer = None
    def handle_resize(self, event):
        """
        FIX 1: 性能优化 (Debouncing)
        当窗口变化时，取消上一个计时器并设置一个新的。
        这可以确保真正的布局计算只在用户停止调整大小后执行一次。
        """
        if self.resize_timer:
            self.window.after_cancel(self.resize_timer)
        self.resize_timer = self.window.after(150, self.perform_layout) # 150毫秒延迟

    def perform_layout(self):
        """
        这是真正执行重新布局和绘制的函数
        """
        # 使用winfo_width/height获取画布当前的的实际大小
        new_width = self.canvas.winfo_width()
        new_height = self.canvas.winfo_height()

        if new_width == self.width and new_height == self.height:
            return

        self.width = new_width
        self.height = new_height

        if self.text_content:
            self.display_list = self.layout(self.text_content)
            self.draw()

    def scrollwheel(self, e):
        if sys.platform == "darwin": 
            self.scroll -= e.delta
        else: 
            self.scroll -= int(e.delta / 120 * SCROLL_STEP) 
        if self.scroll < 0: 
            self.scroll = 0
        self.draw()
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()
    def scrollup(self, e):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0: 
            self.scroll = 0
        self.draw()
    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + self.height: 
                continue
            if y + VSTEP < self.scroll: 
                continue
            self.canvas.create_text(x, y - self.scroll, text=c)
    def load(self, url):
        body = url.request()
        self.text_content = lex(body)
        self.display_list = self.layout(self.text_content)
        self.draw()
    def layout(self, text):
        display_list = []
        cursor_x, cursor_y = HSTEP, VSTEP
        for c in text:
            if c == "\n":
                cursor_y += VSTEP
                cursor_x = HSTEP
                continue
            if cursor_x >= self.width - HSTEP: 
                cursor_y += VSTEP
                cursor_x = HSTEP
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP
            
        return display_list  



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


def lex(body):
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += c
    return text


if __name__ == "__main__":
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
