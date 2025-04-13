# AstrBot 群聊统计分析插件

基于 SQLite 存储的群聊统计分析工具，提供群聊排名、热力图和词云等数据可视化功能。

## 功能介绍

本插件基于 `astrbot_plugin_sqlite_chat_store` 插件存储的聊天数据，自动监听群聊中的特定关键词，并生成对应的统计图表：

1. **群聊排名**：当检测到消息中包含"群聊排名"关键词时，自动生成当天该群聊下按照发送人维度统计的消息数量条形图。
2. **群聊热力图**：当检测到消息中包含"群聊热力图"关键词时，生成当天该群聊下按照小时维度每个发送人在每个小时内发送消息的热力图。
3. **群聊词云**：当检测到消息中包含"群聊词云"关键词时，生成当天该群聊下的聊天内容词云图。

## 依赖条件

- 需要配置 SQLite 数据库路径（可以是 `astrbot_plugin_sqlite_chat_store` 插件的数据库）
- 需要安装以下 Python 依赖库：
  - matplotlib
  - pandas
  - numpy
  - jieba (中文分词)
  - wordcloud

## 安装步骤

1. 确保已安装 AstrBot 并正确配置 Gewechat
2. 将本插件克隆到 AstrBot 的插件目录中：

```bash
cd <AstrBot安装目录>/data/plugins/
git clone https://github.com/lihongjie224/astrbot-stats-plugin
```

3. 安装插件依赖：

```bash
cd <AstrBot安装目录>/data/plugins/astrbot-stats-plugin
pip install -r requirements.txt
```

4. 重新启动 AstrBot 或在 WebUI 中重载插件

## 配置说明

本插件初次启动时，会尝试自动查找 SQLite 聊天记录数据库的位置。如果无法自动找到，需要手动配置数据库路径。

1. 通过命令配置数据库路径：

```
/chatstats_config db_path <SQLite数据库路径>
```

例如，如果使用 `astrbot_plugin_sqlite_chat_store` 插件的数据库：

```
/chatstats_config db_path /path/to/astrbot_plugin_sqlite_chat_store/chat_records.db
```

2. 或者直接编辑配置文件 `chat_stats_config.json`（插件首次加载后会自动创建）：

```json
{
  "db_path": "/path/to/chat_records.db"
}
```

## 使用方法

插件会自动监听群聊中的特定关键词，无需额外命令。在群聊中发送以下关键词即可触发相应功能：

### 1. 生成群聊排名
   
在群聊中发送包含"群聊排名"的消息

```
今天的群聊排名怎么样？
```

机器人将自动回复一张按消息数量排序的条形图。

### 2. 生成群聊热力图
   
在群聊中发送包含"群聊热力图"的消息

```
请生成今日群聊热力图
```

机器人将自动回复一张展示每个人在不同时段发言数量的热力图。

### 3. 生成群聊词云
   
在群聊中发送包含"群聊词云"的消息

```
大家今天都聊了什么？群聊词云
```

机器人将自动回复一张基于今日聊天内容的词云图。

## 管理命令

### 1. 查看插件状态

```
/chatstats_status
```

返回插件当前状态，包括：
- 数据库连接状态
- 数据库路径
- 聊天记录总数量
- 今日聊天记录数量

### 2. 配置插件

```
/chatstats_config db_path <数据库路径>
```

配置 SQLite 数据库路径，需要管理员权限。

## 注意事项

1. 所有统计数据仅包含当天（0:00至现在）的聊天记录
2. 热力图最多显示发言数量最多的10位群成员
3. 词云会自动过滤URL、表情符号等内容
4. 插件需要依赖 SQLite 格式的聊天记录数据库
5. 首次使用时，可能需要等待一段时间收集足够的聊天数据才能生成有意义的图表

## 故障排除

1. 如果关键词没有触发反应，请确认：
   - 数据库路径是否配置正确
   - 是否在群聊中发送的消息
   - 当天是否有足够的聊天记录
   
2. 如果图表生成失败，检查：
   - 依赖库是否正确安装
   - 对应的中文字体是否存在

3. 如果找不到数据库，使用 `/chatstats_status` 命令查看当前配置，并使用 `/chatstats_config` 命令重新配置数据库路径
