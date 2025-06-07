import socket
import ssl
import os
import tkinter
import tkinter.font


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
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    '''
    输入：
        [
            Tag('p'), 
            Text('Hello '), 
            Tag('b'), 
            Text('world'), 
            Tag('/b'), 
            Text('!'), 
            Tag('/p')
        ]
    输出：
        [
            (13, 18, 'Hello', <tkinter.font.Font object at ...>),  # 使用 normal weight, roman style
            (x_world, 18, 'world', <tkinter.font.Font object at ...>), # 使用 bold weight, roman style
            (x_bang, 18, '!', <tkinter.font.Font object at ...>)    # 使用 normal weight, roman style
        ]
    '''
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.line = []
        for tok in tokens:
            self.token(tok)
        self.flush()
        
    def token(self, tok):
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
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
    '''
    输入：<p>Hello <b>world</b>!</p>
    输出：
        [
            Tag('p'), 
            Text('Hello '), 
            Tag('b'), 
            Text('world'), 
            Tag('/b'), 
            Text('!'), 
            Tag('/p')
        ]
    '''
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))

    return out

  

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()