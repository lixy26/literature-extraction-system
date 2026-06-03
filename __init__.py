"""
肝癌文献基因信息提取系统

模块说明：
- config.py: 配置文件，包含API密钥、路径等设置
- pdf_reader.py: PDF文件读取模块
- prompts.py: 提示词定义模块
- llm_client.py: 大语言模型客户端
- processor.py: 文献处理核心模块
- utils.py: 工具函数模块
- main.py: 主入口文件

使用方法：
1. 在config.py中配置API密钥
2. 将PDF文献放入pdfs/目录
3. 运行main.py
"""

__version__ = "1.0.0"
__author__ = "Bioinformatics Research Team"