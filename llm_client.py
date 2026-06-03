import os
import json
import time
import logging
from typing import Optional, Dict, Any
from openai import OpenAI
from config import API_URL, API_KEY, MODEL_NAME, MAX_RETRY, TIMEOUT
from prompts import SYSTEM_PROMPT, build_prompt

logger = logging.getLogger(__name__)


class LLMClient:
    """大语言模型客户端，负责调用API进行文本处理"""

    def __init__(self):
        # 优先使用环境变量
        self.api_key = os.getenv("DASHSCOPE_API_KEY", API_KEY)
        self.api_url = API_URL
        self.model_name = MODEL_NAME
        self.max_retry = MAX_RETRY
        self.timeout = TIMEOUT
        
        # 创建OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url
        )

    def call_api(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        调用大语言模型API
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            
        Returns:
            API响应的JSON数据，失败返回None
        """
        for attempt in range(self.max_retry):
            try:
                logger.info(f"第 {attempt + 1}/{self.max_retry} 次调用API")
                
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=8192,
                    # response_format={"type": "json_object"},  # 暂时移除，可能导致空响应
                    timeout=self.timeout
                )
                
                # 打印完整的响应对象以便调试
                logger.info(f"API响应对象: {completion}")
                logger.info(f"响应choices数量: {len(completion.choices)}")
                
                content = completion.choices[0].message.content
                logger.info(f"原始content类型: {type(content)}, 是否为None: {content is None}")
                
                if content is None:
                    logger.error("API返回了None内容！")
                    # 检查是否有refusal
                    if hasattr(completion.choices[0].message, 'refusal'):
                        logger.error(f"Refusal: {completion.choices[0].message.refusal}")
                    return {"raw_response": "API返回空内容"}
                
                # 处理可能的代码块包装
                if content.startswith("```json"):
                    content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
                
                # 去除首尾空白
                content = content.strip()
                
                # 记录原始响应（用于调试）
                logger.debug(f"API原始响应内容长度: {len(content)} 字符")
                logger.debug(f"API响应前500字符: {content[:500]}")
                
                try:
                    parsed = json.loads(content)
                    logger.info("API调用成功，已解析JSON响应")
                    
                    # 处理JSON数组格式 - 如果返回的是数组，包装成对象
                    if isinstance(parsed, list):
                        logger.info("检测到JSON数组格式，将其包装为对象")
                        return {"genes": parsed}
                    
                    return parsed
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    logger.error(f"原始响应内容长度: {len(content)}")
                    logger.error(f"原始响应前500字符: {content[:500]}")
                    # 返回原始内容而不是None
                    logger.warning("返回原始文本内容...")
                    return {"raw_response": content}
                    # time.sleep(2 ** attempt)
                    # continue

            except Exception as e:
                logger.error(f"请求异常 (第 {attempt + 1} 次): {str(e)}")
                logger.error("请参考文档：https://help.aliyun.com/model-studio/developer-reference/error-code")
                time.sleep(2 ** attempt)

        logger.error(f"API调用失败，已尝试 {self.max_retry} 次")
        return None

    def extract_gene_info(self, pdf_text: str) -> Optional[Dict[str, Any]]:
        """
        提取文献中的基因信息
        
        Args:
            pdf_text: PDF文本内容
            
        Returns:
            提取的基因信息JSON数据，失败返回None
        """
        try:
            logger.info("开始构建提示词...")
            user_prompt = build_prompt(pdf_text)
            logger.info(f"提示词构建完成，长度: {len(user_prompt)} 字符")
            return self.call_api(SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error(f"构建提示词或调用API时出错: {str(e)}")
            return None