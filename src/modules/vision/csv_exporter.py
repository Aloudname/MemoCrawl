"""
csv_exporter.py
CSV导出器

将视觉识别的商品结果导出为CSV文件，
列格式与data_processor.py中的process()方法兼容:
    商品名, 价格, 概述, 来源

依赖库：
- pandas: CSV读写
"""

import os
import logging
import pandas as pd

from typing import List, Optional
from datetime import datetime

from src.modules.vision.models import PageRecognitionResult, ProductCard

logger = logging.getLogger(__name__)


class CSVExporter:
    """
    视觉识别结果CSV导出器
    
    输出的CSV格式与现有 data_processor.py 的输入格式完全兼容，
    确保视觉模块可以无缝替代原有的Chrome插件导出方案。
    """
    
    # CSV列名（与 data_processor.process() 中使用的列名一致）
    CSV_COLUMNS = ["商品名", "价格", "概述", "来源"]
    
    def __init__(self, output_dir: str = ""):
        """
        初始化CSV导出器
        
        Args:
            output_dir: CSV输出目录，空则使用当前目录
        """
        self.output_dir = output_dir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
    
    def export_result(self,
                      result: PageRecognitionResult,
                      filepath: Optional[str] = None,
                      append: bool = False
                      ) -> str:
        """
        将页面识别结果导出为CSV文件
        
        Args:
            result: 页面识别结果
            filepath: 输出文件路径，None则自动生成
            append: 是否追加到已有文件
            
        Returns:
            str: 导出的CSV文件路径
        """
        rows = result.to_csv_rows()
        return self._write_csv(rows, filepath, append)
    
    def export_cards(self,
                     cards: List[ProductCard],
                     filepath: Optional[str] = None,
                     append: bool = False
                     ) -> str:
        """
        将商品卡片列表导出为CSV文件
        
        Args:
            cards: 商品卡片列表
            filepath: 输出文件路径
            append: 是否追加
            
        Returns:
            str: CSV文件路径
        """
        rows = [card.to_csv_row() for card in cards if card.is_valid]
        return self._write_csv(rows, filepath, append)
    
    def _write_csv(self,
                   rows: List[dict],
                   filepath: Optional[str] = None,
                   append: bool = False
                   ) -> str:
        """
        实际写入CSV的内部方法
        
        Args:
            rows: 字典列表（每个字典对应一行CSV）
            filepath: 文件路径
            append: 是否追加
            
        Returns:
            str: CSV文件路径
        """
        if not rows:
            logger.warning("没有有效数据可导出")
            return ""
        
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data_{timestamp}.csv"
            filepath = os.path.join(self.output_dir, filename) if self.output_dir else filename
        
        df = pd.DataFrame(rows, columns=self.CSV_COLUMNS)
        
        if append and os.path.exists(filepath):
            # 追加模式
            existing_df = pd.read_csv(filepath, encoding='utf-8')
            df = pd.concat([existing_df, df], ignore_index=True)
        
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        logger.info(f"CSV导出完成: {filepath}, 共 {len(df)} 条记录")
        return filepath
    
    @staticmethod
    def export_to_data_csv(result: PageRecognitionResult,
                           csv_path: str) -> str:
        """
        直接导出到data_processor期望的csv_path位置
        
        这个方法专门用于与main_controller.py中的
        do_Crawl()方法衔接，替代原有Chrome插件的CSV输出。
        
        Args:
            result: 识别结果
            csv_path: 目标CSV路径（通常是config中的data_processing.csv_path）
            
        Returns:
            str: CSV文件路径
        """
        rows = result.to_csv_rows()
        
        if not rows:
            logger.warning("没有有效商品数据，不导出CSV")
            return ""
        
        df = pd.DataFrame(rows, columns=["商品名", "价格", "概述", "来源"])
        
        # 确保目录存在
        dir_path = os.path.dirname(csv_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        logger.info(f"已导出至data.csv: {csv_path}, 共 {len(df)} 条商品")
        return csv_path
