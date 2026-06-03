import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# API配置
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-83bc1f24365a41ee8d0b3dff11d9a2b2"  # 用户需要替换为自己的百炼API Key
MODEL_NAME = "qwen-plus"

# PDF目录配置
PDF_DIR = PROJECT_ROOT / "pdfs"
OUTPUT_DIR = PROJECT_ROOT / "output"

# 处理参数
MAX_PDFS = 20
MAX_WORKERS = 4
MAX_RETRY = 3
TIMEOUT = 1800

# 文本处理参数
MAX_TEXT_LENGTH = 200000
CHUNK_SIZE = 50000
CHUNK_OVERLAP = 5000

# 确保目录存在
PDF_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)