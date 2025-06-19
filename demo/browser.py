import socket
import ssl
import tkinter

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
    # <div>hello<p>world</p></div>
    # hello word
    content = ""
    word = ""
    intag = False
    for c in text:
        if c == '<':
            intag = True
            content += word
            content += " "
            word = ""
        elif c == '>':
            intag = False
        elif intag:
            pass
        else:
            word += c
    return content
        
        


# ---------------------------------- CSS --------------------------------- #
# css text -> styled tree


# ---------------------------------- Layout --------------------------------- #
# styled tree -> layout tree


HSTEP = 13
VSTEP = 18
def layout(content):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    
    for c in content:
        if cursor_x + HSTEP > WIDTH:
            cursor_x = HSTEP
            cursor_y += VSTEP
        cursor_x += HSTEP
        display_list.append((cursor_x, cursor_y, c))
    return display_list



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
        content = lex(body)
        self.display_list = layout(content)
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        for cursor_x, cursor_y, word in self.display_list:

            self.canvas.create_text(
                cursor_x,
                cursor_y - self.scroll,
                text=word)
        
        
        




if __name__ == '__main__':
    import sys
    url = URL(sys.argv[1])
    browser = Browser()
    browser.load(url)
    browser.window.mainloop()
    
    
    


    

    


    

