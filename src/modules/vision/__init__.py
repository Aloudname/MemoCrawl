"""
src/modules/vision/__init__.py
视觉识别与定位模块

提供基于计算机视觉的商品识别能力，替代原有的
"人工选定坐标 + Chrome插件导出CSV"方案。

核心功能：
- 屏幕截图捕捉
- 商品卡片检测与裁剪
- OCR文字识别（商品名、价格）
- 商品图片分类
- CSV导出（与 data_processor.py 兼容）

快速开始：
    >>> from src.modules.vision import VisionEngine, VisionConfig
    >>> 
    >>> # 使用默认配置
    >>> engine = VisionEngine()
    >>> result = engine.capture_and_recognize()
    >>> 
    >>> # 从全局config创建
    >>> engine = VisionEngine.from_munch_config(global_config)

模块结构：
    vision/
    ├── __init__.py          # 本文件 - 模块导出
    ├── models.py            # 数据模型定义
    ├── capture.py           # 屏幕捕捉子模块
    ├── ocr_engine.py        # OCR文字识别引擎
    ├── detector.py          # 页面元素检测器
    ├── classifier.py        # 商品图片分类器
    ├── debug_visualizer.py  # 调试可视化工具
    ├── csv_exporter.py      # CSV导出器
    └── vision_engine.py     # 统一API入口
"""

# 数据模型
from src.modules.vision.models import (
    VisionConfig,
    BoundingBox,
    TextRegion,
    ImageRegion,
    ProductCard,
    PageRecognitionResult,
    RegionType,
    ProductCategory,
    CardDetectionMethod,
)

# 子模块
from src.modules.vision.capture import ScreenCapture
from src.modules.vision.ocr_engine import OCREngine
from src.modules.vision.detector import ElementDetector
from src.modules.vision.classifier import ProductClassifier
from src.modules.vision.debug_visualizer import DebugVisualizer
from src.modules.vision.csv_exporter import CSVExporter

# 统一入口
from src.modules.vision.vision_engine import VisionEngine

__all__ = [
    # 核心引擎
    'VisionEngine',
    
    # 数据模型
    'VisionConfig',
    'BoundingBox',
    'TextRegion',
    'ImageRegion',
    'ProductCard',
    'PageRecognitionResult',
    'RegionType',
    'ProductCategory',
    'CardDetectionMethod',
    
    # 子模块
    'ScreenCapture',
    'OCREngine',
    'ElementDetector',
    'ProductClassifier',
    'DebugVisualizer',
    'CSVExporter',
]
