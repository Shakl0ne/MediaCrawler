#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
小红书爬虫到大众点评文案生成脚本
功能：
1. 调用小红书爬虫搜索指定关键词
2. 按点赞数排序爬取100个帖子并存储到MySQL
3. 使用大模型筛选最佳9个图片
4. 生成适合大众点评的美食测评文案
"""

import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db
from media_platform.xhs import XiaoHongShuCrawler
from store.xhs.xhs_store_sql import query_content_by_content_id
from db import AsyncMysqlDB
from var import media_crawler_db_var

# AI模型相关导入
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Warning: openai package not installed. AI features will use template-based generation.")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests package not installed. Local AI model support disabled.")


@dataclass
class RestaurantPost:
    """餐厅帖子数据类"""
    note_id: str
    title: str
    desc: str
    liked_count: int
    comment_count: int
    collected_count: int
    image_list: List[str]
    note_url: str
    nickname: str


class AIModelManager:
    """AI模型管理器"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self.local_model_url = os.getenv('LOCAL_MODEL_URL', 'http://localhost:11434/api/generate')
        
        if self.openai_api_key and HAS_OPENAI:
            openai.api_key = self.openai_api_key
            openai.base_url = self.openai_base_url
    
    async def analyze_images_content(self, image_candidates: List[Dict], keyword: str, num_images: int = 9) -> List[str]:
        """使用AI分析图片内容并筛选最佳图片"""
        
        # 构建提示词
        prompt = f"""
        作为美食图片分析专家，请从以下图片候选列表中筛选出最适合{keyword}主题的{num_images}张图片。

        筛选标准：
        1. 图片内容与{keyword}高度相关
        2. 图片质量高，构图美观
        3. 能体现食物的色香味
        4. 适合在大众点评等美食平台展示
        5. 图片来源帖子的点赞数较高

        候选图片信息：
        {self._format_image_candidates_for_ai(image_candidates[:30])}

        请直接返回筛选出的图片URL列表，每行一个URL，不需要其他解释。
        """
        
        try:
            if self.openai_api_key and HAS_OPENAI:
                response = await self._call_openai(prompt)
            else:
                response = await self._call_local_model(prompt)
            
            # 解析AI返回的URL列表
            urls = [line.strip() for line in response.split('\n') if line.strip() and line.strip().startswith('http')]
            return urls[:num_images]
            
        except Exception as e:
            logging.warning(f"AI图片筛选失败，使用启发式方法: {e}")
            return await self._heuristic_image_selection(image_candidates, num_images)
    
    async def generate_dianping_content(self, reference_posts: List[Dict], keyword: str, selected_images: List[str]) -> str:
        """使用AI生成大众点评风格的文案"""
        
        prompt = f"""
        你是一位优秀的美食探店达人，请帮我写一篇针对{keyword}餐厅的美食测评。

        要求：
        1. 请从口味卖相、服务、环境、价格的方面去做点评
        2. 可以用一些表情符号，但是不要用-和**等格式符号
        3. 要求200-300字左右
        4. 写出一个特别有画面感的标题
        5. 语言风格要符合大众点评用户的习惯，真实自然

        参考信息（来自小红书高点赞帖子）：
        {self._format_posts_for_ai(reference_posts[:10])}

        已筛选的图片数量：{len(selected_images)}张精美图片

        请生成一篇完整的大众点评风格测评，包含标题和正文：
        """
        
        try:
            if self.openai_api_key and HAS_OPENAI:
                response = await self._call_openai(prompt)
            else:
                response = await self._call_local_model(prompt)
            
            return response.strip()
            
        except Exception as e:
            logging.warning(f"AI文案生成失败，使用模板方法: {e}")
            return await self._generate_template_content(reference_posts, keyword)
    
    async def _call_openai(self, prompt: str) -> str:
        """调用OpenAI API"""
        try:
            response = await openai.ChatCompletion.acreate(
                model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": "你是一个专业的美食内容创作者和图片分析师。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API调用失败: {e}")
    
    async def _call_local_model(self, prompt: str) -> str:
        """调用本地模型API（如Ollama）"""
        if not HAS_REQUESTS:
            raise Exception("requests库未安装，无法调用本地模型")
        
        try:
            payload = {
                "model": os.getenv('LOCAL_MODEL_NAME', 'llama2'),
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.local_model_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except Exception as e:
            raise Exception(f"本地模型调用失败: {e}")
    
    def _format_image_candidates_for_ai(self, candidates: List[Dict]) -> str:
        """格式化图片候选信息供AI分析"""
        formatted = []
        for i, candidate in enumerate(candidates, 1):
            formatted.append(f"{i}. URL: {candidate['url']}")
            formatted.append(f"   帖子标题: {candidate['post_title']}")
            formatted.append(f"   点赞数: {candidate['liked_count']}")
            formatted.append(f"   描述片段: {candidate['post_desc'][:100]}...")
            formatted.append("")
        return "\n".join(formatted)
    
    def _format_posts_for_ai(self, posts: List[Dict]) -> str:
        """格式化帖子信息供AI参考"""
        formatted = []
        for i, post in enumerate(posts, 1):
            formatted.append(f"{i}. 标题: {post['title']}")
            formatted.append(f"   描述: {post['desc'][:200]}...")
            formatted.append(f"   点赞数: {post['liked_count']}")
            formatted.append("")
        return "\n".join(formatted)
    
    async def _heuristic_image_selection(self, candidates: List[Dict], num_images: int) -> List[str]:
        """启发式图片筛选（AI调用失败时的后备方案）"""
        candidates.sort(key=lambda x: x['liked_count'], reverse=True)
        
        selected = []
        seen_urls = set()
        
        for candidate in candidates:
            if len(selected) >= num_images:
                break
                
            url = candidate['url']
            if url not in seen_urls and url.strip():
                selected.append(url)
                seen_urls.add(url)
        
        return selected[:num_images]
    
    async def _generate_template_content(self, reference_posts: List[Dict], keyword: str) -> str:
        """基于模板生成文案（AI调用失败时的后备方案）"""
        # 从参考内容中提取关键信息
        keywords_found = []
        for post in reference_posts:
            desc = post.get('desc', '')
            title = post.get('title', '')
            
            # 提取口味、环境、服务相关的关键词
            text = f"{title} {desc}".lower()
            
            if any(word in text for word in ['好吃', '美味', '香', '嫩', '鲜']):
                keywords_found.append('口味佳')
            if any(word in text for word in ['环境', '装修', '氛围', '店面']):
                keywords_found.append('环境好')
            if any(word in text for word in ['服务', '态度', '热情']):
                keywords_found.append('服务好')
            if any(word in text for word in ['划算', '便宜', '实惠', '性价比']):
                keywords_found.append('性价比高')
        
        # 生成标题
        title = f"探店{keyword} | 这家店真的绝了！📸✨"
        
        # 生成正文
        content_parts = [
            f"🍖 今天来探店传说中的{keyword}，真的是被惊艳到了！",
            "",
            "【口味卖相】⭐⭐⭐⭐⭐",
            "烤肉的火候掌握得刚刚好，外焦内嫩，每一口都能感受到肉汁的鲜美💧 摆盘也很用心，颜值和味道都在线👍",
            "",
            "【服务体验】⭐⭐⭐⭐",
            "服务员小姐姐超级热情，会主动帮忙烤肉，还会推荐好吃的搭配🥰 整个用餐过程很愉快",
            "",
            "【环境氛围】⭐⭐⭐⭐",
            "店内装修很有特色，灯光氛围营造得很棒✨ 适合和朋友聚餐，拍照也很好看📷",
            "",
            "【价格水平】⭐⭐⭐⭐",
            "人均消费合理，分量足够，性价比还是很不错的💰 学生党也可以承受",
            "",
            f"总的来说，{keyword}真的值得一试！已经预约下次带家人来了🎉",
            "",
            "#美食探店 #烤肉推荐 #北京美食"
        ]
        
        return f"{title}\n\n" + "\n".join(content_parts)


class XhsToDianpingGenerator:
    """小红书到大众点评文案生成器"""
    
    def __init__(self, keyword: str):
        self.keyword = keyword
        self.posts: List[RestaurantPost] = []
        self.selected_images: List[str] = []
        self.generated_content: str = ""
        self.ai_manager = AIModelManager()
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    async def crawl_xhs_posts(self, max_posts: int = 100) -> None:
        """
        爬取小红书帖子
        
        Args:
            max_posts: 最大爬取帖子数量
        """
        self.logger.info(f"开始爬取小红书关键词: {self.keyword}")
        
        # 临时修改配置
        original_keywords = config.KEYWORDS
        original_sort_type = config.SORT_TYPE
        original_max_notes = config.CRAWLER_MAX_NOTES_COUNT
        original_save_option = config.SAVE_DATA_OPTION
        
        try:
            # 设置爬虫配置
            config.KEYWORDS = self.keyword
            config.SORT_TYPE = "popularity_descending"  # 按点赞数降序
            config.CRAWLER_MAX_NOTES_COUNT = max_posts
            config.SAVE_DATA_OPTION = "db"  # 保存到数据库
            config.CRAWLER_TYPE = "search"
            config.ENABLE_GET_IMAGES = True  # 启用图片爬取
            config.ENABLE_GET_COMMENTS = False  # 不需要评论，提高效率
            
            # 初始化数据库
            await db.init_db()
            
            # 创建爬虫实例
            crawler = XiaoHongShuCrawler()
            
            # 开始爬取
            await crawler.start()
            
            self.logger.info(f"完成爬取，开始从数据库获取数据")
            
        except Exception as e:
            self.logger.error(f"爬虫执行出错: {e}")
            raise
        finally:
            # 恢复原始配置
            config.KEYWORDS = original_keywords
            config.SORT_TYPE = original_sort_type
            config.CRAWLER_MAX_NOTES_COUNT = original_max_notes
            config.SAVE_DATA_OPTION = original_save_option
    
    async def get_top_posts_from_db(self, limit: int = 100) -> List[RestaurantPost]:
        """
        从数据库获取点赞最高的帖子
        
        Args:
            limit: 获取帖子数量限制
            
        Returns:
            帖子列表
        """
        self.logger.info("从数据库获取点赞最高的帖子")
        
        async_db_conn: AsyncMysqlDB = media_crawler_db_var.get()
        
        # 查询点赞数最高的帖子，按点赞数降序排列
        sql = f"""
        SELECT note_id, title, `desc`, liked_count, comment_count, collected_count, 
               image_list, note_url, nickname
        FROM xhs_note 
        WHERE source_keyword = '{self.keyword}'
        AND liked_count IS NOT NULL 
        AND liked_count != ''
        AND image_list IS NOT NULL
        AND image_list != ''
        ORDER BY CAST(liked_count AS UNSIGNED) DESC
        LIMIT {limit}
        """
        
        try:
            rows = await async_db_conn.query(sql)
            posts = []
            
            for row in rows:
                # 处理图片列表
                image_list = []
                if row.get('image_list'):
                    image_list = [img.strip() for img in row['image_list'].split(',') if img.strip()]
                
                # 转换点赞数为整数
                liked_count = 0
                try:
                    liked_count = int(row.get('liked_count', 0) or 0)
                except (ValueError, TypeError):
                    liked_count = 0
                
                post = RestaurantPost(
                    note_id=row['note_id'],
                    title=row.get('title', ''),
                    desc=row.get('desc', ''),
                    liked_count=liked_count,
                    comment_count=int(row.get('comment_count', 0) or 0),
                    collected_count=int(row.get('collected_count', 0) or 0),
                    image_list=image_list,
                    note_url=row.get('note_url', ''),
                    nickname=row.get('nickname', '')
                )
                posts.append(post)
            
            self.logger.info(f"获取到 {len(posts)} 个帖子")
            self.posts = posts
            return posts
            
        except Exception as e:
            self.logger.error(f"数据库查询出错: {e}")
            raise
    
    async def select_best_images_with_ai(self, num_images: int = 9) -> List[str]:
        """
        使用AI筛选最佳图片
        
        Args:
            num_images: 需要筛选的图片数量
            
        Returns:
            筛选出的图片URL列表
        """
        self.logger.info(f"使用AI筛选最佳 {num_images} 张图片")
        
        # 收集所有图片URL和对应的帖子信息
        image_candidates = []
        for post in self.posts[:50]:  # 只考虑前50个高点赞帖子
            for img_url in post.image_list:
                image_candidates.append({
                    'url': img_url,
                    'post_title': post.title,
                    'post_desc': post.desc,
                    'liked_count': post.liked_count,
                    'post_url': post.note_url
                })
        
        # 使用AI模型筛选图片
        selected_images = await self.ai_manager.analyze_images_content(
            image_candidates, self.keyword, num_images
        )
        
        self.selected_images = selected_images
        self.logger.info(f"筛选完成，选出 {len(selected_images)} 张图片")
        
        return selected_images
    
    async def generate_dianping_content_with_ai(self) -> str:
        """
        使用AI生成大众点评风格的文案
        
        Returns:
            生成的文案内容
        """
        self.logger.info("生成大众点评风格文案")
        
        # 收集帖子内容用于参考
        reference_content = []
        for post in self.posts[:20]:  # 取前20个高质量帖子作为参考
            reference_content.append({
                'title': post.title,
                'desc': post.desc,
                'liked_count': post.liked_count
            })
        
        # 使用AI生成文案
        content = await self.ai_manager.generate_dianping_content(
            reference_content, self.keyword, self.selected_images
        )
        
        self.generated_content = content
        self.logger.info("文案生成完成")
        
        return content
    
    async def run(self) -> Dict[str, any]:
        """
        运行完整流程
        
        Returns:
            包含结果的字典
        """
        try:
            # 1. 爬取小红书帖子
            await self.crawl_xhs_posts(100)
            
            # 2. 从数据库获取点赞最高的帖子
            posts = await self.get_top_posts_from_db(100)
            
            if not posts:
                raise ValueError("未获取到任何帖子数据")
            
            # 3. 筛选最佳图片
            images = await self.select_best_images_with_ai(9)
            
            # 4. 生成文案
            content = await self.generate_dianping_content_with_ai()
            
            result = {
                'keyword': self.keyword,
                'total_posts': len(posts),
                'selected_images': images,
                'content': content,
                'top_posts': [
                    {
                        'title': post.title,
                        'liked_count': post.liked_count,
                        'note_url': post.note_url
                    } for post in posts[:10]
                ]
            }
            
            self.logger.info("任务完成！")
            return result
            
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}")
            raise
        finally:
            # 关闭数据库连接
            await db.close()


async def main():
    """主函数"""
    # 可以通过命令行参数或环境变量设置关键词
    keyword = os.getenv('KEYWORD', '北京本垒美式烤肉')
    
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
    
    generator = XhsToDianpingGenerator(keyword)
    
    try:
        result = await generator.run()
        
        # 输出结果
        print("=" * 50)
        print("小红书到大众点评文案生成结果")
        print("=" * 50)
        print(f"关键词: {result['keyword']}")
        print(f"获取帖子数: {result['total_posts']}")
        print(f"筛选图片数: {len(result['selected_images'])}")
        print("\n" + "=" * 30)
        print("生成的文案:")
        print("=" * 30)
        print(result['content'])
        
        print("\n" + "=" * 30)
        print("筛选的图片:")
        print("=" * 30)
        for i, img_url in enumerate(result['selected_images'], 1):
            print(f"{i}. {img_url}")
        
        print("\n" + "=" * 30)
        print("参考的热门帖子:")
        print("=" * 30)
        for i, post in enumerate(result['top_posts'], 1):
            print(f"{i}. {post['title']} (点赞: {post['liked_count']})")
        
        # 保存结果到文件
        output_file = f"output_{keyword.replace(' ', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


