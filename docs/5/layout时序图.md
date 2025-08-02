

### HTML 示例

我们将使用这个简单而经典的 HTML 结构。它包含了块级元素和内联元素，足以触发代码中所有的核心逻辑。

```html
<body>
  <p>
    Welcome to <b>my</b> page.
  </p>
</body>
```

**涉及的节点**:

  * `<body>` 元素 (块级)
  * `<p>` 元素 (块级)
  * `"Welcome to "` (文本节点, 内联)
  * `<b>` 元素 (内联)
  * `"my"` (文本节点, 内联)
  * `" page."` (文本节点, 内联)

### 参与者说明

在时序图中，我们会看到以下几个参与者：

  * **LayoutEngine**: 代表调用布局流程的外部引擎。
  * **L\_body**: 为 `<body>` 节点创建的 `BlockLayout` 对象实例。
  * **L\_p**: 为 `<p>` 节点创建的 `BlockLayout` 对象实例。

### Layout 过程时序图

下面的图详细描绘了从 `LayoutEngine` 开始，到所有元素布局完成的每一步调用和返回过程。

```mermaid
sequenceDiagram
    participant LayoutEngine
    participant L_body as BlockLayout(body)
    participant L_p as BlockLayout(p)

    LayoutEngine ->> L_body: create(node=body, ...)
    LayoutEngine ->> L_body: layout()
    activate L_body
    
    note right of L_body: 1. L_body 计算自己的 x, y, width
    L_body ->> L_body: layout_mode()
    note right of L_body: 2. body包含块级子元素<p>，所以模式是 "block"

    alt mode == "block"
        note right of L_body: 3. “堆箱子”模式：为子节点<p>创建布局对象
        L_body ->> L_p: create(node=p, parent=L_body, ...)
        
        note right of L_body: 4. 递归调用：命令子“箱子” L_p 自己去布局
        L_body ->> L_p: layout()
        activate L_p

        note right of L_p: 5. L_p 计算自己的 x, y, width
        L_p ->> L_p: layout_mode()
        note right of L_p: 6. p的子节点是文本和<b>，所以模式是 "inline"
        
        alt mode == "inline"
            note right of L_p: 7. “在Word里打字”模式：<br/>初始化光标，不创建子布局对象。<br/>调用 recurse() 和 flush() 处理所有内联内容。
            L_p ->> L_p: recurse("Welcome to <b>my</b> page.")
            note right of L_p: 8. L_p 计算出自己的 height (基于文字流的高度)
        end
        
        L_p -->> L_body: layout() 返回
        deactivate L_p
    end
    
    note right of L_body: 9. L_body 等待所有子“箱子”布局完毕
    note right of L_body: 10. 计算自己的 height (等于 L_p 的高度)
    L_body -->> LayoutEngine: layout() 返回
    deactivate L_body
```

