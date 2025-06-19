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

def lex(text):
    # in: <div>hello<p>world? world!</p></div>
    # out: [Tag(div), Text(hello), Tag(p), Text(world? world!), Tag(/p), Tag(/div)]
    content = []
    buffer = ""

    for c in text:
        if c == '<':
            if buffer:
                content.append(Text(buffer))
            buffer = ""
        elif c == '>':
            if buffer:
                content.append(Tag(buffer))
                buffer = ""
        else:
            buffer += c
    
    if buffer:
        content.append(Text(buffer)) 
    return content
        
class Text:
    def __init__(self, text):
        self.text = text
     
class Tag:
    def __init__(self, tag):
        self.tag = tag         

def paint_tokens(tokens):
    for tok in tokens:
        if isinstance(tok, Text):
            print("text:", tok.text)
        elif isinstance(tok, Tag):
            print("tag:", tok.tag)
            

# ---------------------------------- CSS --------------------------------- #
# css text -> styled tree


# ---------------------------------- Layout --------------------------------- #
# styled tree -> layout tree
# in: [Tag(div), Text(hello), Tag(i), Text(world? world!)]
# out: [(x, y, hello, font), (x, y, world, font), (x, y, ?, font), (x, y, world, font), (x, y, !, font)]


HSTEP = 13
VSTEP = 18
class Layout:
    def __init__(self, tokens):
        self.tokens = tokens
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        
        self.size = 12
        self.weight = "normal"
        self.style = "roman"
        
        for tok in tokens:
            self.token(tok)
    def token(self, tok):
        if isinstance(tok, Text):
            text = tok.text.split()
            for word in text:
                self.word(word)
        elif isinstance(tok, Tag):
            if tok.tag == "i":
                self.style = "italic"
            elif tok.tag == '/i':
                self.style = "roman"
 
            
    def word(self, word):
        font = tkinter.font.Font(
            size=self.size,
            weight=self.weight,
            slant=self.style,
        )
        w = font.measure(word)
        
        if self.cursor_x + w < WIDTH:
            pass
        else:
            self.cursor_x = HSTEP
            self.cursor_y += VSTEP
        self.display_list.append((self.cursor_x, self.cursor_y, word, font))
        self.cursor_x += w + HSTEP



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
        content = lex(body)
        self.display_list = Layout(content).display_list
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
    

    
    
    


    

    


    

