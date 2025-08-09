

这个流程体现了现代浏览器的一个核心思想：**HTML解析和脚本执行是解耦的**，通过任务调度来避免长时间的脚本执行阻塞页面的渲染。

整个流程可以分为**两个主要阶段**：

1.  **发现与调度阶段**：在页面加载时，解析HTML，找到所有`<script>`标签，并为它们创建待执行的任务。
2.  **执行阶段**：在稍后的某个时间点，由事件循环从任务队列中取出任务并执行其中的JavaScript代码。

下面是这个流程的详细图解和说明：

```mermaid
sequenceDiagram
    participant TabLoad as Tab.load()
    participant HTMLParser as HTMLParser
    participant TaskRunner as 标签页主线程 (TaskRunner)
    participant JSContext as JSContext / dukpy

    Note over TabLoad: 1. 开始加载页面
    TabLoad->>HTMLParser: 2. HTMLParser(body).parse()
    HTMLParser-->>TabLoad: 3. 返回完整的 DOM 树 (self.nodes)

    Note over TabLoad: 4. 遍历DOM树, 寻找<script src="...">标签
    TabLoad->>TabLoad: 5. for node in tree_to_list(self.nodes, [])

    Note over TabLoad: 6. 找到一个脚本, 如 <script src="main.js">
    TabLoad->>TabLoad: 7. 发起网络请求，获取 "main.js" 的文件内容(body)

    Note over TabLoad: 8. **关键步骤**：不立即执行，而是封装成任务
    TabLoad->>+TaskRunner: 9. schedule_task(Task(self.js.run, "main.js", body))
    Note right of TabLoad: 将执行脚本的任务放入队列,<br/>然后继续处理其他<script>标签或完成加载。

    Note over TaskRunner: 10. 事件循环在未来的某个时刻<br/>从队列中取出该任务
    TaskRunner->>TaskRunner: 11. task.run()

    TaskRunner->>+JSContext: 12. 调用 self.js.run("main.js", body)

    Note over JSContext: 13. 使用 dukpy 执行 JS 代码
    JSContext->>JSContext: 14. self.interp.evaljs(body)
    deactivate JSContext
    deactivate TaskRunner
```

### 流程详解

1.  **开始加载 (`Tab.load`)**
    当你的浏览器加载一个URL时，`Tab.load` 方法被调用。它首先获取到HTML响应的 `body`。

2.  **解析DOM树 (`HTMLParser`)**
    代码首先执行 `self.nodes = HTMLParser(body).parse()`。`HTMLParser`会完整地读取整个HTML字符串，并构建出一个完整的DOM树。**此时，它并不会因为遇到`<script>`标签而停下**。

3.  **遍历DOM树，寻找脚本**
    在DOM树构建完毕后，`Tab.load` 方法会**主动地**、**专门地**去遍历这棵树，寻找所有 `tag == "script"` 并且包含 `src` 属性的元素节点。

    > **注意:** 您的当前实现只处理带有 `src` 属性的外部脚本，不处理行内脚本 (例如 `<script>alert('hello');</script>`)。

4.  **获取脚本内容**
    对于每一个找到的 `<script>` 标签，浏览器会解析其 `src` 属性得到URL，然后发起一次**同步的网络请求** (`script_url.request(url)`) 来获取脚本文件的内容。

5.  **调度任务（核心步骤）**
    获取到脚本内容后，浏览器并**不会立即执行它**。相反，它将执行这个脚本的操作封装成一个 `Task` 对象：`task = Task(self.js.run, script_url, body)`。
    然后，这个 `task` 被放入 `TaskRunner` 的任务队列中：`self.task_runner.schedule_task(task)`。

    这个设计的意义重大：

      * **非阻塞**：将脚本的执行推迟，使得 `Tab.load` 函数可以快速地完成它的工作（比如寻找页面上其他的CSS或脚本），而不会被一个复杂的JS文件执行过程所拖慢。
      * **顺序保证**：由于任务被依次放入队列，脚本的执行顺序（理论上）会遵循它们在HTML中出现的顺序。

6.  **执行脚本 (`JSContext.run`)**
    在未来的某个时刻，`TaskRunner` 的事件循环会从队列中取出这个任务并执行 `task.run()`，这最终会调用 `JSContext.run(...)` 方法。
    `JSContext.run` 方法使用 `dukpy` JS解释器 (`self.interp.evaljs(code)`) 来执行获取到的脚本代码。至此，一个 `<script>` 标签的生命周期才算完成。