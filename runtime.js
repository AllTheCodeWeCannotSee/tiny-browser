console = {
  log: function (x) {
    call_python("log", x);
  },
};

// DOM node
/**
 * 构造一个表示 DOM 节点的 JavaScript 对象。
 * 这个对象主要通过一个句柄 (handle) 与 Python 端的实际 DOM 元素进行关联。
 * @constructor
 * @param {number} handle - 与 Python 端 DOM 元素对应的唯一整数句柄。
 */
function Node(handle) {
  this.handle = handle;
}

document = {
  // text -> Node
  querySelectorAll: function (s) {
    var handles = call_python("querySelectorAll", s);
    return handles.map(function (h) {
      return new Node(h);
    });
  },
};

// 属性名 -> 属性值
Node.prototype.getAttribute = function (attr) {
  return call_python("getAttribute", this.handle, attr);
};

/**
 * @example
 * LISTENERS = {
 *   123: { // 节点句柄 123
 *     "click": [ // "click" 事件类型
 *       function handleClick1(event) { console.log("Node 123 clicked (listener 1)"); },
 *       function handleClick2(event) { console.log("Node 123 clicked (listener 2)"); }
 *     ],
 *     "keydown": [ // "keydown" 事件类型
 *       function handleKeyDown(event) { console.log("Key pressed on node 123"); }
 *     ]
 *   },
 *   456: { // 节点句柄 456
 *     "mouseover": [ function handleMouseOver(event) { console.log("Mouse over node 456"); } ]
 *   }
 *   // ... 其他节点的监听器
 * };
 */

// 事件对象
LISTENERS = {};
function Event(type) {
  this.type = type;
  this.do_default = true;
}
Event.prototype.preventDefault = function () {
  this.do_default = false;
};

/**
 * 为此节点注册一个特定事件类型的事件监听器。
 * 监听器存储在一个全局的 `LISTENERS` 对象中，该对象首先按节点句柄索引，然后按事件类型索引。
 *
 * @param {string} type - 要监听的事件类型 (例如, "click", "keydown")。
 * @param {function} listener - 当事件发生时要调用的函数。
 * @this Node 当前 Node 实例。
 * @global LISTENERS 用于存储事件监听器的全局对象。
 */
Node.prototype.addEventListener = function (type, listener) {
  if (!LISTENERS[this.handle]) LISTENERS[this.handle] = {};
  var dict = LISTENERS[this.handle];
  if (!dict[type]) dict[type] = [];
  var list = dict[type];
  list.push(listener);
};

Node.prototype.dispatchEvent = function (evt) {
  var type = evt.type;
  var handle = this.handle;
  var list = (LISTENERS[handle] && LISTENERS[handle][type]) || [];
  for (var i = 0; i < list.length; i++) {
    list[i].call(this);
  }
  return evt.do_default;
};

/**
 * @property {string} innerHTML - 获取或设置节点的 HTML 内容。
 * @description
 * 当设置 `innerHTML` 属性时，会调用 Python 端的 `innerHTML_set` 函数，
 * 将当前节点的句柄 (handle) 和新的 HTML 字符串传递给 Python，
 * 以便在 Python 管理的 DOM 树中更新对应节点的内容。
 *
 * @example
 * var node = new Node(123); // 假设 123 是一个有效的节点句柄
 * node.innerHTML = "<p>New content</p>"; // 这会调用 call_python("innerHTML_set", 123, "<p>New content</p>")
 */
Object.defineProperty(Node.prototype, "innerHTML", {
  set: function (s) {
    call_python("innerHTML_set", this.handle, s.toString());
  },
});

// setTimeout
SET_TIMEOUT_REQUESTS = {};
function setTimeout(callback, time_delta) {
  var handle = Object.keys(SET_TIMEOUT_REQUESTS).length;
  SET_TIMEOUT_REQUESTS[handle] = callback;
  call_python("setTimeout", handle, time_delta);
}

function __runSetTimeout(handle) {
  var callback = SET_TIMEOUT_REQUESTS[handle];
  callback();
}

// XMLHttpRequest 跨站请求
// x = new XMLHttpRequest();
// x.open("GET", url, false);
// x.send(body);

XHR_REQUESTS = {};

function XMLHttpRequest() {
  this.handle = Object.keys(XHR_REQUESTS).length;
  XHR_REQUESTS[this.handle] = this;
}

XMLHttpRequest.prototype.open = function (method, url, is_async) {
  this.method = method;
  this.url = url;
  this.is_async = is_async;
};

XMLHttpRequest.prototype.send = function (body) {
  this.responseText = call_python(
    "XMLHttpRequest_send",
    this.method,
    this.url,
    body,
    this.is_async,
    this.handle
  );
};

function __runXHROnload(body, handle) {
  var obj = XHR_REQUESTS[handle];
  obj.responseText = body;
  var evt = new Event("load");
  if (obj.onload) {
    obj.onload(evt);
  }
}

// requestAnimationFrame
RAF_LISTENERS = [];
function requestAnimationFrame(fn) {
  RAF_LISTENERS.push(fn);
  call_python("requestAnimationFrame");
}

function __runRAFHandlers() {
  var handles_copy = RAF_LISTENERS;
  RAF_LISTENERS = [];
  for (var i = 0; i < handles_copy.length; i++) {
    handles_copy[i]();
  }
}
