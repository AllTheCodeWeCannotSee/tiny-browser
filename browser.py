import socket
import ssl
import os

class URL:
    def __init__(self, url):
        # http://example.org/index.html
        self.scheme, url = url.split('://', 1)
        assert self.scheme in ["http", "https", "file"]
        if self.scheme == "http":
            self.port = 80
            self.host = getHostHttp(url)
            self.path = getPathHttp(url)
            self.port = getPortHttp(url)

        elif self.scheme == "https":
            self.port = 443
            self.host = getHostHttp(url)
            self.path = getPathHttp(url)
            self.port = getPortHttps(url)
        elif self.scheme == "file":
            self.path = getPathFile(url)
            self.host = None
            self.port = None
         
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


def getHostHttp(url):
    if "/" not in url:
        url += "/"
    host, url = url.split('/', 1)
    if ":" in host:
            host, port = host.split(":", 1)
    return host

def getPortHttp(url):
    if "/" not in url:
        url += "/"
    host, url = url.split('/', 1)
    if ":" in host:
        host, port = host.split(":", 1)
        return port
    return 80

def getPortHttps(url):
    if "/" not in url:
        url += "/"
    host, url = url.split('/', 1)
    if ":" in host:
        host, port = host.split(":", 1)
        return port
    return 443
        
def getPathHttp(url):
    if "/" not in url:
        url += "/"
    host, url = url.split('/', 1)
    url = "/" + url
    return url

def getPathFile(url):
    return url


def show(body):
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(c, end="") 
def load(url):
    body = url.request()
    show(body)
if __name__ == "__main__":
    import sys
    load(URL(sys.argv[1]))
