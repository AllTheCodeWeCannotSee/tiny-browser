import socket
import ssl

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
        
# text body -> node tree

# css text -> styled tree

# styled tree -> layout tree


if __name__ == '__main__':
    import sys
    url = URL(sys.argv[1])
    headers, content =url.request()
    print(headers)
    print(content)

    

