这个过程的核心是 **`dukpy`** 库，它充当了 JavaScript 和 Python 之间的桥梁。

### 场景设定

假设我们的浏览器加载了以下简单的 HTML：

```html
<html>
  <body>
    <p>Some text</p>
    <div>
        <p class="note">A note</p>
    </div>
  </body>
</html>
```

然后，页面中的一个脚本执行了这行代码：

```javascript
// 这段 JS 代码在浏览器中运行
let paragraphs = document.querySelectorAll("p");
```

### 执行流程详解

#### 第 1 步：JavaScript 调用

1. 在 JavaScript 环境中，`document.querySelectorAll("p")` 被调用。
2. `document` 对象上的 `querySelectorAll` 方法是在 `[runtime.js](code-assist-path:/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js "/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js")` 中定义的。它的作用是调用一个特殊的函数（我们称之为 `call_python`），这个函数由 `dukpy` 注入到 JavaScript 环境中。
3. `call_python` 的任务是将函数调用请求发送给 Python。它会传递函数名 (`"querySelectorAll"`) 和所有参数 (选择器字符串 `"p"`)。

```javascript
// 在 runtime.js (概念上的简化代码)
class Document {
    // ...
    querySelectorAll(selector) {
        // 'call_python' 是 dukpy 提供的魔法函数
        // 它会调用在 Python 端导出的同名函数
        const handles = call_python("querySelectorAll", selector);

        // handles 将会是 [0, 1] 这样的整数数组
        // 将每个 handle 包装成一个 JS Node 对象
        return handles.map(handle => new Node(handle));
    }
    // ...
}

let document = new Document();
```

#### 第 2 步：进入 Python (`JSContext.querySelectorAll`)

1. `dukpy` 接收到来自 JavaScript 的请求，并调用在 `JSContext` 类中注册的 `querySelectorAll` 方法。
    
2. Python 的 `querySelectorAll(self, selector_text)` 方法被执行，其中 `selector_text` 的值是 `"p"`。
    
    ```python
    # 在 browser.py 的 JSContext 类中
    def querySelectorAll(self, selector_text): # selector_text is "p"
        # 2a. 解析选择器
        selector = CSSParser(selector_text).selector()
        # 这会创建一个 TagSelector 对象，其 tag 属性为 "p"
    
        # 2b. 遍历 DOM 树
        # tree_to_list 会返回一个包含所有 DOM 节点的扁平列表
        # 假设列表是 [<html>, <body>, <p>, Text, <div>, <p class="note">, Text]
        nodes = [node for node
             in tree_to_list(self.tab.nodes, [])
             if selector.matches(node)]
        # selector.matches(node) 会检查 node.tag == "p"
        # 最终 `nodes` 列表会包含两个 <p> 元素对象
    
        # 2c. 为匹配的节点生成句柄 (Handle)
        return [self.get_handle(node) for node in nodes]
        # 假设这是第一次调用，它会返回 [0, 1]
    ```
    

#### 第 3 步：句柄 (Handle) 的创建与管理

这是理解的关键部分。JavaScript 不能直接持有 Python 对象的引用。**句柄（Handle）** 是一个简单的整数 ID，作为 Python 对象的唯一标识符，可以在两种语言之间安全地传递。

`get_handle` 方法负责创建和管理这些 ID。

```python
# 在 browser.py 的 JSContext 类中
def get_handle(self, elt):
    # self.node_to_handle 是一个字典，像这样：{ <Element p>: 0, <Element p.note>: 1 }
    # self.handle_to_node 是反向映射：{ 0: <Element p>, 1: <Element p.note> }

    if elt not in self.node_to_handle:
        # 如果是新节点，创建一个新 handle
        handle = len(self.node_to_handle) # 第一次是 0，第二次是 1
        self.node_to_handle[elt] = handle
        self.handle_to_node[handle] = elt
    else:
        # 如果节点之前已见过，返回已有的 handle
        handle = self.node_to_handle[elt]
    return handle
```

在我们的例子中：

- 当处理第一个 `<p>` 元素时，`get_handle` 创建了句柄 `0`。
- 当处理第二个 `<p class="note">` 元素时，`get_handle` 创建了句柄 `1`。
- 最终，Python 函数返回列表 `[0, 1]`。

#### 第 4 步：返回 JavaScript

1. `dukpy` 将 Python 返回的列表 `[0, 1]` 转换成 JavaScript 的数组 `[0, 1]`。
2. 在 `[runtime.js](code-assist-path:/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js "/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js")` 中，`querySelectorAll` 的实现接收到这个数组。
3. 它使用 `map` 函数遍历这个句柄数组，为每个句柄创建一个新的 `Node` 对象。`new Node(0)` 和 `new Node(1)`。
4. 最终，`document.querySelectorAll("p")` 返回一个包含这两个 `Node` 对象的数组，这个数组被赋值给 `paragraphs` 变量。

#### 后续操作：从 JS 再次调用 Python

现在，如果 JavaScript 代码试图操作这些返回的节点，比如：

```javascript
// 假设 paragraphs[1] 是句柄为 1 的 Node 对象
let className = paragraphs[1].getAttribute("class");
```

1. **JS**: `getAttribute("class")` 在 `Node` 对象上被调用。这个对象内部存储着它的句柄 `1`。
2. **`[runtime.js](code-assist-path:/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js "/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js")`**: `Node.prototype.getAttribute` 方法会再次使用 `call_python`，这次调用的是 Python 的 `getAttribute` 函数，并把**句柄 `1`** 和属性名 `"class"` 作为参数传过去。
3. **Python**: `JSContext.getAttribute(self, handle, attr)` 被调用 (`handle=1`, `attr="class"`).
    - 它使用 `self.handle_to_node[1]` 来精确地找回之前匹配到的 `<p class="note">` Python 对象。
    - 然后它访问该对象的 `attributes` 字典，找到 `"class"` 键对应的值 `"note"`。
    - 它将字符串 `"note"` 返回。
4. **JS**: `dukpy` 将 Python 字符串 `"note"` 转为 JS 字符串，并返回给调用者。变量 `className` 的值就成了 `"note"`。

### 总结

这个流程就像一个翻译和中介系统：

- **JS 世界**: 使用方便的 `document.querySelectorAll`。
- **`dukpy` 桥梁**: 将 JS 调用“翻译”成 Python 调用。
- **Python 世界**: 实际执行 DOM 节点的查找和匹配逻辑。
- **句柄 (Handle)**: 作为跨语言的“身份证”或“指针”，让 JS 能够间接地引用和操作 Python 中的对象。
- **`[runtime.js](code-assist-path:/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js "/Users/hao/Downloads/tiny-browser-397270f0f52554c06a3cbdb7b859c1420b541dc0/runtime.js")`**: 在 JS 端提供与标准 Web API 一致的接口，并在内部处理与 Python 的通信细节，对开发者隐藏了底层的复杂性。