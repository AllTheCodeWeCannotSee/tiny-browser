import socket
import urllib.parse
import random
import html

'''
    SESSIONS = {
        "random_token_string_1": {"user": "crashoverride"},
        "random_token_string_2": {"user": "cerealkiller"},
        "random_token_string_3": {}  # 这个用户的会话是空的，因为他们还没登录
        # ... 可能还有其他用户的会话数据
    }
'''
SESSIONS = {}

s = socket.socket(
    family=socket.AF_INET, # ipv4
    type=socket.SOCK_STREAM, # tcp
    proto=socket.IPPROTO_TCP
)

s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(('', 8000))
s.listen()


def handle_connection(conx):
    # conx: 套接字连接
    # req: 文件类对象
    req = conx.makefile("b") # b: 二进制
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    assert method in ["GET", "POST"]
    
    # headers
    headers = {}
    while True:
        line = req.readline().decode('utf8')
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.casefold()] = value.strip()
    
    # POST 的请求体
    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf8')
    else:
        body = None
    
    # cookie
    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]
        
    # session
    session = SESSIONS.setdefault(token, {}) #  setdefault 方法既能从字典中获取键值，又能在键不存在时设置默认值
    status, body = do_request(session, method, url, headers, body)

    response = "HTTP/1.0 {}\r\n".format(status)
    response += "Content-Length: {}\r\n".format(
        len(body.encode("utf8")))
    
    if "cookie" not in headers:
        template = "Set-Cookie: token={}; SameSite=Lax\r\n"
        response += template.format(token)
        
        
    # 发送 Content-Security-Policy 请求头
    csp = "default-src http://localhost:8000"
    response += "Content-Security-Policy: {}\r\n".format(csp)
    
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()

LOGINS = {
    "crashoverride": "0cool",
    "cerealkiller": "emmanuel"
}

def do_request(session, method, url, headers, body):
    if method == "GET" and url == "/":
        return "200 OK", show_comments(session)
    elif method == "GET" and url == "/comment.js":
        with open("comment.js") as f:
            return "200 OK", f.read()
    elif method == "GET" and url == "/comment.css":
        with open("comment.css") as f:
            return "200 OK", f.read()
    elif method == "POST" and url == "/add":
        params = form_decode(body)
        add_entry(session, params)
        return "200 OK", show_comments(session)
    # login
    elif method == "GET" and url == "/login":
        return "200 OK", login_form(session)
    elif method == "POST" and url == "/":
        params = form_decode(body)
        return do_login(session, params)
    
    return "404 Not Found", not_found(url, method)


def do_login(session, params):
    username = params.get("username")
    password = params.get("password")
    if username in LOGINS and LOGINS[username] == password:
        session["user"] = username
        return "200 OK", show_comments(session)
    else:
        out = "<!doctype html>"
        out += "<h1>Invalid password for {}</h1>".format(username)
        return "401 Unauthorized", out


def login_form(session):
    body = "<!doctype html>"
    body += "<form action=/ method=post>"
    body += "<p>Username: <input name=username></p>"
    body += "<p>Password: <input name=password type=password></p>"
    body += "<p><button>Log in</button></p>"
    body += "</form>"
    return body 



def form_decode(body):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params

ENTRIES = [
    ("No names. We are nameless!", "cerealkiller"),
    ("HACK THE PLANET!!!", "crashoverride"),
]


def show_comments(session):
    out = "<!doctype html>"
    
    # 登陆
    if "user" in session:
        out += "<h1>Hello, " + session["user"] + "</h1>"
        
        nonce = str(random.random())[2:]
        session["nonce"] = nonce
        
        out += "<form action=add method=post>"
        out +=   "<p><input name=guest></p>"
        out +=   "<input name=nonce type=hidden value=" + nonce + ">"
        out +=   "<p><button>Sign the book!</button></p>"
        out += "</form>"
    else:
        out += "<a href=/login>Sign in to write in the guest book</a>"
    

    for entry, who in ENTRIES:
        out += "<p>" + html.escape(entry) + "\n"
        out += "<i>by " + html.escape(who) + "</i></p>"
    
    out += "<link rel=stylesheet href=/comment.css>"
    out += "<strong></strong>"
    out += "<script src=/comment.js></script>"

    return out

def not_found(url, method):
    out = "<!doctype html>"
    out += "<h1>{} {} not found!</h1>".format(method, url)
    return out
    
def add_entry(session, params):
    # 检查是否登陆
    if "user" not in session: return
    
    # 检查 nonce
    if "nonce" not in session or "nonce" not in params: return
    if session["nonce"] != params["nonce"]: return
    
    if 'guest' in params and len(params['guest']) < 100:
        ENTRIES.append((params['guest'], session["user"]))
    return show_comments(session)

if __name__ == "__main__":
    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 8000))
    s.listen()
    
    while True:
        conx, addr = s.accept()
        print("Received connection from", addr)
        handle_connection(conx)