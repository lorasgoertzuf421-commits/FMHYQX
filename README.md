# FMHY Cleaner GUI 说明

翻墙/科学上网/冒泡法上网网络推荐使用白羊加[🔍](https://baiyangjiasu.com/register?invite=RWqaczzt)

更多工具及教程地址：https://wofacai.pages.dev/

TG频道：https://t.me/woxituoHH

交流群：https://t.me/woxituohhhhj
需要Gemini GPT codex的可以进群交流。中转免费账号供应滴下我。之前的注册机没法用了，暂时没时间写。codex见底了。



## 1. 文件作用

`fmhy_cleaner_gui.py` 是一个面向 `FMHY` 单页 Markdown 数据的可视化清洗工具。

它的主要目标不是简单把 Markdown 转成表格，而是把原始文档里的标题层级关系整理出来，重点提取：

- 一级标题
- 二级标题
- 更深层标题路径
- 标题下的具体资源内容
- 资源主链接
- 资源描述

当前默认读取的源文件是：

`desktop_collector/fmhy/single-page.md`

## 2. 适用的数据结构

FMHY 的原始 Markdown 主要是这种结构：

```md
# 一级标题
* 一级标题下面直接挂的内容

## 二级标题
* 二级标题下面的内容

### 更深标题
* 更深标题下面的内容
```

这个程序会把“谁属于谁”整理清楚：

- 如果内容直接挂在一级标题下面，那么结果里只有一级标题，二级标题为空。
- 如果内容挂在二级标题下面，那么一级标题和二级标题都会保留。
- 如果内容挂在三级及更深标题下面，那么一级标题、二级标题照样保留，同时把更深层标题写进“更深标题”字段。

## 3. 解析后的核心字段

程序内部每条记录会整理成这些关键信息：

- `level1_title`
  一级标题
- `level2_title`
  二级标题；如果原内容直接挂在一级标题下，这里可能为空
- `deeper_path`
  三级及更深标题组成的路径
- `heading_path`
  完整标题路径
- `content_title`
  资源名称或内容标题
- `url`
  主链接
- `description`
  描述信息
- `entry_kind`
  内容类型，例如普通资源、`Note`、站内跳转等
- `extra_links`
  同一条内容里的附加链接
- `raw_text`
  原始 Markdown 文本

## 4. 界面功能

程序启动后，主表格会展示这些列：

- 一级标题
- 二级标题
- 更深标题
- 内容标题
- 主链接
- 类型
- 描述

界面支持这些操作：

- 选择其他 Markdown 文件
- 重新解析
- 按关键词搜索
- 过滤 `Note`
- 过滤站内跳转
- 过滤 Reddit/FMHY 内链
- 过滤无链接条目
- 按“一二级标题 + 内容 + 链接”去重
- 导出 `JSON`
- 导出 `CSV`
- 导出 `Markdown`

下半区还有两个辅助面板：

- `条目详情`
  查看当前选中记录的完整结构化信息
- `统计汇总`
  查看一级标题统计，以及“一级标题 / 二级标题”组合统计

## 5. 导出规则

### JSON

导出完整结构化数据，适合后续继续做程序处理。

### CSV

适合给 Excel、WPS、数据库导入使用。当前会导出这些字段：

- `line_no`
- `level1_title`
- `level2_title`
- `deeper_path`
- `heading_path`
- `content_title`
- `url`
- `description`
- `marker`
- `entry_kind`
- `extra_links`
- `raw_text`

### Markdown

会重新按层级生成清洗后的 Markdown，结构大致如下：

```md
## 一级标题

### 二级标题

- [内容标题](链接) - 更深标题路径 | 描述
```

## 6. 运行方式

在当前项目目录下执行：

```powershell
python C:\code\WoXituo\desktop_collector\fmhy_cleaner_gui.py
```

如果 Python 已经加入环境变量，也可以先进入目录再运行：

```powershell
cd C:\code\WoXituo\desktop_collector
python .\fmhy_cleaner_gui.py
```

## 7. 当前处理逻辑说明

程序目前会做这些基础清洗：

- 去除部分 Markdown 修饰符
- 去除部分 HTML 标签
- 提取 Markdown 链接
- 清理零宽字符
- 识别条目前缀符号
- 保留标题层级关系

同时会识别一部分特殊内容：

- 以 `Note` 开头的说明性条目
- 带 `↪` 的站内跳转条目
- FMHY/Reddit 内部跳转链接

这些内容是否保留，可以在界面里勾选控制。

## 8. 适合的使用场景

这个工具比较适合下面几类工作：

- 把 FMHY 原始 Markdown 拆成可入库数据
- 检查一级标题和二级标题是否挂对
- 给后续资源站、导航站、搜索页做预处理
- 导出成 CSV 后交给人工继续筛选
- 导出成 JSON 后喂给后续脚本或数据库

## 9. 注意事项

- 这个工具目前以 `* ` 开头的列表项为主要提取对象。
- 如果原文某些内容不是列表项，而是纯段落文本，它默认不会像列表项那样完整入表。
- 程序重点是“理顺一二级标题与条目关系”，不是做全文无损还原。
- 对于一条里包含多个链接的情况，首个链接会作为 `url`，剩余链接放进 `extra_links`。

## 10. 后续可继续增强的方向

如果后面还要继续改，可以考虑这些方向：

- 增加“只导出一级标题 / 二级标题 / 内容标题”简版 CSV
- 增加批量导出到 SQLite 或 JSON Lines
- 增加按一级标题分文件导出
- 增加对纯段落资源块的识别
- 增加内容预览中的原始上下文片段
