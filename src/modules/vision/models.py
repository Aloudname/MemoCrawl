"""
models.py
视觉识别模块的数据模型定义

定义了所有子模块之间传递数据的标准结构，确保模块间接口清晰统一。
"""

import numpy as np
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


class RegionType(Enum):
    """区域类型枚举"""
    IMAGE = "image"           # 商品图片区域
    TEXT = "text"             # 文字区域
    PRICE = "price"           # 价格区域
    TITLE = "title"           # 商品标题区域
    UNKNOWN = "unknown"       # 未知区域


class ProductCategory(Enum):
    """商品分类枚举（可通过图片库扩展）"""
    KNOWN = "known"           # 已知商品类型
    UNKNOWN = "unknown"       # 未知商品


class CardDetectionMethod(Enum):
    """卡片检测方法枚举"""
    CONTOUR = "contour"       # 基于轮廓检测
    EDGE = "edge"             # 基于边缘检测
    COLOR = "color"           # 基于颜色分割
    TEMPLATE = "template"     # 基于模板匹配
    GRID = "grid"             # 基于网格分割


@dataclass
class BoundingBox:
    """
    边界框定义
    用于表示图像中某区域的矩形范围
    
    Attributes:
        x1: 左上角 x 坐标
        y1: 左上角 y 坐标
        x2: 右下角 x 坐标
        y2: 右下角 y 坐标
        confidence: 检测置信度 (0.0 ~ 1.0)
        label: 区域标签
    """
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = 1.0
    label: str = ""
    
    @property
    def width(self) -> int:
        return self.x2 - self.x1
    
    @property
    def height(self) -> int:
        return self.y2 - self.y1
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)
    
    @property
    def top_left(self) -> Tuple[int, int]:
        """对角坐标 - 左上角"""
        return (self.x1, self.y1)
    
    @property
    def bottom_right(self) -> Tuple[int, int]:
        """对角坐标 - 右下角"""
        return (self.x2, self.y2)
    
    def contains(self, x: int, y: int) -> bool:
        """判断某点是否在此边界框内"""
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2
    
    def overlap_ratio(self, other: 'BoundingBox') -> float:
        """计算与另一边界框的重叠率 (IoU)"""
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)
        
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        union_area = self.area + other.area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def crop_from(self, image: np.ndarray) -> np.ndarray:
        """从图像中裁剪出该区域"""
        h, w = image.shape[:2]
        # 边界约束
        y1 = max(0, min(self.y1, h))
        y2 = max(0, min(self.y2, h))
        x1 = max(0, min(self.x1, w))
        x2 = max(0, min(self.x2, w))
        return image[y1:y2, x1:x2].copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x1": self.x1, "y1": self.y1,
            "x2": self.x2, "y2": self.y2,
            "width": self.width, "height": self.height,
            "confidence": self.confidence,
            "label": self.label
        }
    
    def __repr__(self) -> str:
        return (f"BoundingBox(({self.x1},{self.y1})->({self.x2},{self.y2}), "
                f"{self.width}x{self.height}, conf={self.confidence:.2f}, "
                f"label='{self.label}')")


@dataclass
class TextRegion:
    """
    文字识别区域结果
    
    Attributes:
        bbox: 文字区域的边界框
        text: 识别出的文字内容
        confidence: OCR识别置信度
        region_type: 区域类型 (标题/价格/其它文字)
    """
    bbox: BoundingBox
    text: str
    confidence: float = 0.0
    region_type: RegionType = RegionType.TEXT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "confidence": self.confidence,
            "region_type": self.region_type.value
        }


@dataclass
class ImageRegion:
    """
    图片区域结果
    
    Attributes:
        bbox: 图片区域的边界框
        image: 裁剪出的图片 (numpy数组)
        category: 分类结果
        category_name: 分类名称
        match_score: 匹配分数
    """
    bbox: BoundingBox
    image: Optional[np.ndarray] = None
    category: ProductCategory = ProductCategory.UNKNOWN
    category_name: str = "未知商品"
    match_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.to_dict(),
            "category": self.category.value,
            "category_name": self.category_name,
            "match_score": self.match_score
        }


@dataclass
class ProductCard:
    """
    商品卡片数据模型
    从搜索结果页中裁剪出的单个商品信息卡片
    
    Attributes:
        bbox: 整个卡片的边界框 (对角坐标)
        card_image: 卡片截图 (numpy数组)
        image_region: 商品图片区域
        text_regions: 文字区域列表
        product_name: 识别出的商品名
        price: 识别出的价格
        description: 商品概述
        source: 来源信息
        card_index: 卡片在页面中的序号
    """
    bbox: BoundingBox
    card_image: Optional[np.ndarray] = None
    image_region: Optional[ImageRegion] = None
    text_regions: List[TextRegion] = field(default_factory=list)
    product_name: str = ""
    price: str = ""
    description: str = ""
    source: str = "京东"
    card_index: int = 0
    
    @property
    def diagonal_coords(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """返回对角坐标 (左上角, 右下角)"""
        return (self.bbox.top_left, self.bbox.bottom_right)
    
    @property
    def is_valid(self) -> bool:
        """判断卡片信息是否有效（至少有商品名和价格）"""
        return bool(self.product_name.strip()) and bool(self.price.strip())
    
    def to_csv_row(self) -> Dict[str, str]:
        """转为CSV行数据，列名与data_processor兼容"""
        return {
            "商品名": self.product_name,
            "价格": self.price,
            "概述": self.description,
            "来源": self.source
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.to_dict(),
            "diagonal_coords": {
                "top_left": self.bbox.top_left,
                "bottom_right": self.bbox.bottom_right
            },
            "product_name": self.product_name,
            "price": self.price,
            "description": self.description,
            "source": self.source,
            "card_index": self.card_index,
            "image_region": self.image_region.to_dict() if self.image_region else None,
            "text_regions": [t.to_dict() for t in self.text_regions],
            "is_valid": self.is_valid
        }


@dataclass
class PageRecognitionResult:
    """
    整页识别结果
    
    Attributes:
        screenshot: 原始截图
        cards: 识别出的商品卡片列表
        page_index: 页码
        timestamp: 识别时间
        debug_image: 标注了检测结果的调试图像
        processing_time_ms: 处理耗时(毫秒)
        errors: 处理过程中的错误列表
    """
    screenshot: Optional[np.ndarray] = None
    cards: List[ProductCard] = field(default_factory=list)
    page_index: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    debug_image: Optional[np.ndarray] = None
    processing_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    @property
    def valid_cards(self) -> List[ProductCard]:
        """仅返回信息完整的有效卡片"""
        return [c for c in self.cards if c.is_valid]
    
    @property
    def card_count(self) -> int:
        return len(self.cards)
    
    @property
    def valid_card_count(self) -> int:
        return len(self.valid_cards)
    
    def to_csv_rows(self) -> List[Dict[str, str]]:
        """将所有有效卡片转为CSV行列表"""
        return [card.to_csv_row() for card in self.valid_cards]
    
    def summary(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "timestamp": self.timestamp,
            "total_cards": self.card_count,
            "valid_cards": self.valid_card_count,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.errors
        }


@dataclass
class VisionConfig:
    """
    视觉模块配置
    从全局config中提取的视觉相关配置，隔离外部依赖
    """
    # 截图配置
    capture_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)，None=全屏
    capture_delay: float = 0.5           # 截图前延迟(秒)
    screenshot_save_dir: str = "debug/screenshots"
    
    # 卡片检测配置
    detection_method: str = "contour"    # contour / edge / color / grid
    min_card_width: int = 200            # 商品卡片最小宽度(px)
    min_card_height: int = 150           # 商品卡片最小高度(px)
    max_card_width: int = 800            # 商品卡片最大宽度(px)
    max_card_height: int = 600           # 商品卡片最大高度(px)
    card_aspect_ratio_range: Tuple[float, float] = (0.3, 3.0)  # 宽高比范围
    iou_threshold: float = 0.3           # 重叠阈值，超过则去重
    
    # OCR配置
    ocr_lang: str = "chi_sim+eng"        # Tesseract语言包
    tesseract_cmd: str = ""              # tesseract可执行文件路径，空则使用系统PATH
    ocr_psm: int = 6                     # Tesseract页面分割模式
    ocr_confidence_threshold: float = 30.0  # OCR置信度阈值
    
    # 分类器配置
    reference_image_dir: str = "data/reference_images"   # 参考图片库目录
    feature_match_threshold: int = 10    # 特征匹配最低数量
    
    # 调试配置
    debug_mode: bool = True              # 是否开启调试模式
    save_debug_images: bool = True       # 是否保存调试图片
    debug_output_dir: str = "debug/vision"
    
    # 快捷键配置
    hotkey_capture: str = "ctrl+shift+c"  # 触发截图的快捷键
    
    @classmethod
    def from_munch(cls, config) -> 'VisionConfig':
        """
        从Munch配置对象创建VisionConfig
        
        Args:
            config: 全局Munch配置对象 (需包含 vision 字段)
        """
        vc = config.get('vision', {})
        
        kwargs = {}
        field_map = {
            'capture_region': 'capture_region',
            'capture_delay': 'capture_delay',
            'screenshot_save_dir': 'screenshot_save_dir',
            'detection_method': 'detection_method',
            'min_card_width': 'min_card_width',
            'min_card_height': 'min_card_height',
            'max_card_width': 'max_card_width',
            'max_card_height': 'max_card_height',
            'iou_threshold': 'iou_threshold',
            'ocr_lang': 'ocr_lang',
            'tesseract_cmd': 'tesseract_cmd',
            'ocr_psm': 'ocr_psm',
            'ocr_confidence_threshold': 'ocr_confidence_threshold',
            'reference_image_dir': 'reference_image_dir',
            'feature_match_threshold': 'feature_match_threshold',
            'debug_mode': 'debug_mode',
            'save_debug_images': 'save_debug_images',
            'debug_output_dir': 'debug_output_dir',
            'hotkey_capture': 'hotkey_capture',
        }
        
        for config_key, attr_name in field_map.items():
            if config_key in vc:
                kwargs[attr_name] = vc[config_key]
        
        # 处理 card_aspect_ratio_range (YAML中是列表)
        if 'card_aspect_ratio_range' in vc:
            ratio = vc['card_aspect_ratio_range']
            if isinstance(ratio, (list, tuple)) and len(ratio) == 2:
                kwargs['card_aspect_ratio_range'] = tuple(ratio)
        
        # 处理 capture_region (YAML中是列表)
        if 'capture_region' in vc:
            region = vc['capture_region']
            if isinstance(region, (list, tuple)) and len(region) == 4:
                kwargs['capture_region'] = tuple(region)
        
        return cls(**kwargs)
