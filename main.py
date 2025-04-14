from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os
import sqlite3
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，避免需要显示界面
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import jieba
from wordcloud import WordCloud
import io
from astrbot.api.message_components import Image
import re
import json

@register("astrbot_plugin_chat_stats", "User", "基于SQLite存储的群聊统计分析工具", "1.0.0")
class ChatStatsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取 SQLite 数据库路径
        self.db_path = None
        self.config_file = "chat_stats_config.json"
        self.triggers = {
            "群聊排名": self.generate_chat_ranking,
            "群聊热力图": self.generate_heatmap,
            "群聊词云": self.generate_wordcloud
        }
        
    async def initialize(self):
        """初始化插件，找到SQLite数据库"""
        try:
            # 读取配置文件
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.db_path = config.get("db_path", None)
                    if self.db_path:
                        logger.info(f"使用配置中的数据库路径: {self.db_path}")
                    else:
                        logger.warning("配置中未找到数据库路径")
            else:
                # 尝试找到SQLite Chat Store插件的数据库
                logger.info("尝试查找SQLite Chat Store插件的数据库...")
                # 尝试从多个可能的位置查找
                possible_paths = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "astrbot-sqlite-plugin", "chat_records.db"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "astrbot_plugin_sqlite_chat_store", "chat_records.db"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sqlite_chat_store", "chat_records.db"),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        self.db_path = path
                        logger.info(f"找到SQLite数据库: {self.db_path}")
                        # 创建默认配置
                        default_config = {
                            "db_path": self.db_path
                        }
                        with open(config_path, 'w', encoding='utf-8') as f:
                            json.dump(default_config, f, indent=2, ensure_ascii=False)
                        logger.info(f"创建默认配置文件: {config_path}")
                        break
                
                if not self.db_path:
                    logger.warning("未找到SQLite数据库，请在配置文件中指定路径")
                    # 创建空白配置文件
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump({"db_path": ""}, f, indent=2, ensure_ascii=False)
                    logger.info(f"创建空白配置文件: {config_path}")
        except Exception as e:
            logger.error(f"初始化统计插件失败: {str(e)}")
            self.db_path = None
    
    def get_connection(self):
        """获取数据库连接"""
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            return None
    
    def get_today_data(self, group_id):
        """获取当天的群聊数据"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            # 获取今天的日期范围
            today = datetime.now().strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 查询数据
            df = pd.read_sql_query("""
                SELECT sender_id, sender_name, message, timestamp 
                FROM chat_records 
                WHERE group_id = ? AND timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            """, conn, params=(group_id, today, tomorrow))
            
            conn.close()
            
            if df.empty:
                return None
                
            # 添加小时列，用于热力图
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            
            return df
        except Exception as e:
            logger.error(f"获取数据失败: {str(e)}")
            if conn:
                conn.close()
            return None
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听消息，检测触发关键词"""
        if event.get_platform_name() != "gewechat":
            return
            
        # 检查是否是群聊
        if not event.message_obj.group_id:
            return
            
        # 检查消息内容是否包含触发词
        message = event.message_str.strip()
        
        for trigger, handler in self.triggers.items():
            if trigger in message:
                group_id = event.message_obj.group_id
                result = await handler(group_id)
                if result:
                    yield result
                break
    
    async def generate_chat_ranking(self, group_id):
        """生成群聊排名条形图"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成群聊排名")
        
        # 按发送人统计消息数量
        sender_counts = df.groupby('sender_name').size().sort_values(ascending=False)
        
        # 生成条形图
        plt.figure(figsize=(10, 6))
        sender_counts.plot(kind='bar', color='skyblue')
        plt.title('今日群聊排名')
        plt.xlabel('发送人')
        plt.ylabel('消息数量')
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        from astrbot.api.message_components import Plain, Image as ComponentImage
        
        # 使用MessageChain构建消息
        return AstrMessageEvent.result_builder().add_component(
            ComponentImage(base64=img_buf.getvalue())
        ).add_plain(f"{today} 群聊排名统计").build()
    
    async def generate_heatmap(self, group_id):
        """生成群聊热力图"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成热力图")
        
        # 排序发送者按消息总数
        sender_totals = df.groupby('sender_name').size().sort_values(ascending=False)
        top_senders = sender_totals.index.tolist()
        
        # 限制最多显示10个发送者
        if len(top_senders) > 10:
            top_senders = top_senders[:10]
        
        # 生成热力图数据
        heatmap_data = []
        for sender in top_senders:
            sender_df = df[df['sender_name'] == sender]
            hourly_counts = sender_df.groupby('hour').size()
            
            # 确保所有小时都有数据
            hour_data = [hourly_counts.get(hour, 0) for hour in range(24)]
            heatmap_data.append(hour_data)
        
        # 创建热力图
        plt.figure(figsize=(12, 8))
        im = plt.imshow(heatmap_data, cmap='YlOrRd')
        
        # 设置标签
        plt.yticks(np.arange(len(top_senders)), top_senders)
        plt.xticks(np.arange(0, 24, 1), [f"{h}时" for h in range(24)])
        plt.xlabel('时间')
        plt.ylabel('发送人')
        plt.title('今日群聊热力图')
        
        # 添加颜色条
        plt.colorbar(im, label='消息数量')
        
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        from astrbot.api.message_components import Plain, Image as ComponentImage
        
        # 使用MessageChain构建消息
        return AstrMessageEvent.result_builder().add_component(
            ComponentImage(base64=img_buf.getvalue())
        ).add_plain(f"{today} 群聊热力图").build()
    
    async def generate_wordcloud(self, group_id):
        """生成群聊词云"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成词云")
        
        # 合并所有消息文本
        all_text = ' '.join(df['message'].tolist())
        
        # 过滤掉表情符号、URL等
        all_text = re.sub(r'http\S+', '', all_text)  # 移除URL
        all_text = re.sub(r'[^\w\s]', '', all_text)  # 移除标点符号
        
        # 使用jieba进行中文分词
        words = ' '.join(jieba.cut(all_text))
        
        # 生成词云
        wordcloud = WordCloud(
            font_path='/System/Library/Fonts/PingFang.ttc',  # macOS中文字体
            width=800,
            height=400,
            background_color='white',
            max_words=100,
            contour_width=1,
            contour_color='steelblue'
        ).generate(words)
        
        # 创建图像
        plt.figure(figsize=(10, 6))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        from astrbot.api.message_components import Plain, Image as ComponentImage
        
        # 使用MessageChain构建消息
        return AstrMessageEvent.result_builder().add_component(
            ComponentImage(base64=img_buf.getvalue())
        ).add_plain(f"{today} 群聊词云").build()
    
    @filter.command("chatstats_config")
    async def config(self, event: AstrMessageEvent):
        """配置群聊统计插件"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("只有管理员可以执行此操作")
            return
        
        message_parts = event.message_str.split()
        if len(message_parts) < 3:
            yield event.plain_result("使用方法: /chatstats_config db_path <SQLite数据库路径>")
            return
            
        param = message_parts[1]
        value = message_parts[2]
        
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
                
            if param == "db_path":
                config["db_path"] = value
                self.db_path = value
                
                # 测试连接
                conn = self.get_connection()
                if conn:
                    conn.close()
                    status = "数据库连接成功"
                else:
                    status = "数据库连接失败，请检查路径是否正确"
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                yield event.plain_result(f"配置已更新: {param} = {value}\n{status}")
            else:
                yield event.plain_result(f"未知参数: {param}")
        except Exception as e:
            yield event.plain_result(f"配置失败: {str(e)}")
    
    @filter.command("chatstats_status")
    async def status(self, event: AstrMessageEvent):
        """查看群聊统计插件状态"""
        status_info = []
        
        if self.db_path and os.path.exists(self.db_path):
            conn = self.get_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM chat_records")
                    count = cursor.fetchone()[0]
                    status_info.append(f"数据库连接: 正常")
                    status_info.append(f"数据库路径: {self.db_path}")
                    status_info.append(f"记录总数: {count}")
                    
                    # 获取今日记录数
                    today = datetime.now().strftime('%Y-%m-%d')
                    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                    cursor.execute("SELECT COUNT(*) FROM chat_records WHERE timestamp >= ? AND timestamp < ?", 
                                 (today, tomorrow))
                    today_count = cursor.fetchone()[0]
                    status_info.append(f"今日记录数: {today_count}")
                    
                    conn.close()
                except Exception as e:
                    status_info.append(f"数据库查询失败: {str(e)}")
                    if conn:
                        conn.close()
            else:
                status_info.append(f"数据库连接: 失败")
                status_info.append(f"数据库路径: {self.db_path}")
                status_info.append("请检查数据库路径是否正确")
        else:
            status_info.append("数据库路径未配置或不存在")
            status_info.append(f"当前路径: {self.db_path if self.db_path else '未设置'}")
            status_info.append("请使用 /chatstats_config db_path <路径> 配置数据库路径")
        
        yield event.plain_result("\n".join(status_info))
    
    async def terminate(self):
        """终止插件"""
        logger.info("群聊统计分析插件已终止")
