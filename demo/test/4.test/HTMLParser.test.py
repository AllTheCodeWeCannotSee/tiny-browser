# ===============================================================
# 辅助类 (为了让您的 HTMLParser 可以运行)
# ===============================================================
class Element:
    """代表一个 HTML 元素/标签。"""
    def __init__(self, tag):
        self.tag = tag
        self.children = []
        self.parent = None

    def __repr__(self):
        # repr 方法让打印对象时输出更清晰
        return f"Element('{self.tag}')"

class Text:
    """代表一个文本节点。"""
    def __init__(self, text):
        self.text = text
        self.parent = None

    def __repr__(self):
        return f"Text('{self.text}')"

# ===============================================================
# 您提供的 HTMLParser 类 (附带最小修改)
# ===============================================================
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
  
   
# ===============================================================
# 一个简单的函数来可视化输出的树状结构
# ===============================================================
def print_tree(node, indent=0):
    """递归地打印出节点树。"""
    if node is None:
        print(" " * indent + "None")
        return
        
    # 打印当前节点，使用 repr(node) 来获得清晰的表示
    print(" " * indent + repr(node))
    
    # 如果是 Element 节点，递归打印它的所有子节点
    if isinstance(node, Element):
        for child in node.children:
            print_tree(child, indent + 2)

# ===============================================================
# 主程序：执行解析并打印结果
# ===============================================================
if __name__ == '__main__':
    # 1. 输入
    input_html = "<div>hello <br><p>world? world!</p></div>"
    
    # 2. 创建解析器并执行解析
    parser = HTMLParser(input_html)
    output_tree = parser.parse()
    
    # 3. 打印输入和输出
    print("--- 输入 (Input) ---")
    print(input_html)
    print("\n" + "="*25 + "\n")
    print("--- 解析结果 (Output Tree) ---")
    print_tree(output_tree)