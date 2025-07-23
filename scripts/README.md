# 小红书到大众点评文案生成器

这个脚本可以自动从小红书爬取指定关键词的热门帖子，然后使用AI技术筛选最佳图片和生成适合大众点评的美食测评文案。

## 功能特性

- 🔍 **智能搜索**: 自动搜索小红书上的指定关键词内容
- 📊 **热度排序**: 按点赞数排序，获取最受欢迎的100个帖子
- 🖼️ **AI图片筛选**: 使用大模型智能筛选最符合主题的9张图片
- ✍️ **文案生成**: 基于爬取内容生成专业的大众点评风格测评文案
- 💾 **数据存储**: 所有数据自动存储到MySQL数据库
- 🤖 **多AI支持**: 支持OpenAI GPT和本地模型（如Ollama）

## 安装依赖

### 基础依赖
```bash
# 安装项目基础依赖
pip install -r requirements.txt

# 额外的AI功能依赖
pip install openai requests
```

### 数据库配置
确保MySQL数据库已安装并配置：

```bash
# 设置数据库连接信息
export RELATION_DB_USER="your_username"
export RELATION_DB_PWD="your_password"
export RELATION_DB_HOST="localhost"
export RELATION_DB_PORT="3306"
export RELATION_DB_NAME="crawler_system"
```

运行数据库初始化脚本：
```bash
mysql -u your_username -p your_database < schema/tables.sql
```

## AI模型配置

### 方案一：使用OpenAI GPT

```bash
# 设置OpenAI API密钥
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_MODEL="gpt-3.5-turbo"  # 可选，默认为gpt-3.5-turbo

# 如果使用自定义API地址（如国内代理）
export OPENAI_BASE_URL="https://your-proxy-url.com/v1"
```

### 方案二：使用本地模型（推荐使用Ollama）

1. 安装Ollama：
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

2. 下载模型：
```bash
ollama pull llama2
# 或者使用中文优化模型
ollama pull qwen:7b
```

3. 设置环境变量：
```bash
export LOCAL_MODEL_URL="http://localhost:11434/api/generate"
export LOCAL_MODEL_NAME="llama2"  # 或 qwen:7b
```

### 方案三：仅使用模板生成（无需AI配置）
如果不配置AI模型，脚本会自动使用内置的模板生成功能，虽然效果稍逊但仍然可用。

## 使用方法

### 基本用法

```bash
# 使用默认关键词"北京本垒美式烤肉"
cd scripts
python xhs_to_dianping.py

# 指定自定义关键词
python xhs_to_dianping.py "上海网红火锅"

# 使用环境变量指定关键词
export KEYWORD="成都串串香"
python xhs_to_dianping.py
```

### 高级配置

在运行脚本前，你可以通过修改 `config/base_config.py` 来调整爬虫参数：

```python
# 最大爬取帖子数量
CRAWLER_MAX_NOTES_COUNT = 200

# 是否启用图片下载
ENABLE_GET_IMAGES = True

# 并发数量控制
MAX_CONCURRENCY_NUM = 4

# 爬取间隔（秒）
CRAWLER_MAX_SLEEP_SEC = 2
```

## 输出结果

脚本运行完成后会输出以下内容：

1. **控制台输出**：
   - 爬取进度和统计信息
   - 生成的文案内容
   - 筛选的图片URL列表
   - 参考的热门帖子信息

2. **文件输出**：
   - `output_关键词.json`：包含完整结果的JSON文件

3. **数据库存储**：
   - 所有爬取的帖子数据存储在MySQL的`xhs_note`表中
   - 评论数据存储在`xhs_note_comment`表中

## 示例输出

```
==================================================
小红书到大众点评文案生成结果
==================================================
关键词: 北京本垒美式烤肉
获取帖子数: 87
筛选图片数: 9

==============================
生成的文案:
==============================
探店北京本垒美式烤肉 | 这家店真的绝了！📸✨

🍖 今天来探店传说中的北京本垒美式烤肉，真的是被惊艳到了！

【口味卖相】⭐⭐⭐⭐⭐
烤肉的火候掌握得刚刚好，外焦内嫩，每一口都能感受到肉汁的鲜美💧 摆盘也很用心，颜值和味道都在线👍

【服务体验】⭐⭐⭐⭐
服务员小姐姐超级热情，会主动帮忙烤肉，还会推荐好吃的搭配🥰 整个用餐过程很愉快

【环境氛围】⭐⭐⭐⭐
店内装修很有特色，灯光氛围营造得很棒✨ 适合和朋友聚餐，拍照也很好看📷

【价格水平】⭐⭐⭐⭐
人均消费合理，分量足够，性价比还是很不错的💰 学生党也可以承受

总的来说，北京本垒美式烤肉真的值得一试！已经预约下次带家人来了🎉

#美食探店 #烤肉推荐 #北京美食

==============================
筛选的图片:
==============================
1. https://sns-img-bd.xhscdn.com/xxx.jpg
2. https://sns-img-bd.xhscdn.com/yyy.jpg
...

结果已保存到: output_北京本垒美式烤肉.json
```

## 工作流程

1. **爬取阶段**：
   - 启动小红书爬虫，搜索指定关键词
   - 按点赞数降序排列，爬取热门帖子
   - 下载帖子图片并存储到本地
   - 将所有数据保存到MySQL数据库

2. **数据处理**：
   - 从数据库查询点赞数最高的100个帖子
   - 收集所有图片URL和相关信息

3. **AI分析**：
   - 使用大模型分析图片内容和帖子信息
   - 筛选出最符合主题的9张图片
   - 基于热门帖子内容生成测评文案

4. **结果输出**：
   - 在控制台显示完整结果
   - 保存结果到JSON文件
   - 提供图片URL供后续使用

## 故障排除

### 常见问题

1. **数据库连接失败**
   ```
   解决方案：检查数据库配置和连接信息
   ```

2. **爬虫被限制**
   ```
   解决方案：
   - 减少并发数量（MAX_CONCURRENCY_NUM）
   - 增加爬取间隔（CRAWLER_MAX_SLEEP_SEC）
   - 启用代理IP（ENABLE_IP_PROXY）
   ```

3. **AI API调用失败**
   ```
   解决方案：
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 脚本会自动降级到模板生成
   ```

4. **没有获取到帖子数据**
   ```
   解决方案：
   - 确认关键词是否存在相关内容
   - 检查数据库中是否有历史数据
   - 尝试更换关键词
   ```

### 日志调试

脚本内置了详细的日志记录，可以通过以下方式查看：

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # 启用调试日志
```

## 扩展功能

### 自定义AI Prompt

你可以修改 `AIModelManager` 类中的提示词来优化AI效果：

```python
# 修改图片筛选提示词
async def analyze_images_content(self, ...):
    prompt = f"""
    你的自定义提示词...
    """
```

### 添加新的数据源

可以扩展脚本支持其他平台的数据：

```python
class MultiPlatformGenerator(XhsToDianpingGenerator):
    async def crawl_additional_sources(self):
        # 添加其他平台的爬虫逻辑
        pass
```

## 许可证

本脚本仅供学习和研究使用，请遵守相关平台的使用条款和robots.txt规则。

## 联系方式

如有问题或建议，请通过GitHub Issues联系。 