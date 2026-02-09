"""
vision_processor.py
视觉处理器主模块
"""

import cv2
import numpy as np
import logging
import time
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
from enum import Enum

from src.config.manager import init_config, get_dict_config

logger = logging.getLogger(__name__)

class CaptureMode(Enum):
    """捕捉模式枚举"""
    FULL_SCREEN = "full_screen"
    REGION = "region"
    WINDOW = "window"

class CropMethod(Enum):
    """裁剪方法枚举"""
    EDGE_DETECTION = "edge_detection"      # 边缘检测
    CONTOUR_DETECTION = "contour_detection" # 轮廓检测
    ML_MODEL = "ml_model"                  # 机器学习模型
    HYBRID = "hybrid"                      # 混合方法

@dataclass
class CaptureConfig:
    """捕捉配置"""
    mode: CaptureMode = CaptureMode.FULL_SCREEN
    region: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
    delay: float = 0.5  # 捕捉前延迟
    save_captures: bool = False
    save_dir: str = "captures"
    preprocessing: Dict[str, Any] = field(default_factory=lambda: {
        "resize_factor": 1.0,
        "grayscale": False,
        "denoise": True,
        "enhance_contrast": True
    })

@dataclass
class CropConfig:
    """裁剪配置"""
    method: CropMethod = CropMethod.HYBRID
    min_card_width: int = 360
    min_card_height: int = 650
    max_card_width: int = 370
    max_card_height: int = 665
    min_aspect_ratio: float = 0.1  # 宽高比最小值
    max_aspect_ratio: float = 6.0  # 宽高比最大值
    edge_threshold_low: int = 50
    edge_threshold_high: int = 150
    contour_min_area: int = 10000
    contour_max_area: int = 200000
    overlap_threshold: float = 0.3  # 重叠抑制阈值
    save_crops: bool = False
    save_dir: str = "crops"

@dataclass
class ProductCard:
    """商品卡片数据类"""
    index: int
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) 对角坐标
    confidence: float = 0.0
    image: Optional[np.ndarray] = None
    features: Dict[str, Any] = field(default_factory=dict)

class CaptureModule:
    """捕捉模块"""
    
    def __init__(self, config: CaptureConfig):
        self.config = config
        if self.config.save_captures:
            Path(self.config.save_dir).mkdir(parents=True, exist_ok=True)
    
    def capture(self) -> np.ndarray:
        """
        捕捉屏幕或区域
        
        Returns:
            捕捉的图像 (BGR格式)
        """
        logger.info(f"开始捕捉，模式: {self.config.mode}")
        
        # 捕捉前延迟
        if self.config.delay > 0:
            time.sleep(self.config.delay)
        
        try:
            if self.config.mode == "full_screen":
                image = self._capture_full_screen()
            elif self.config.mode == "region":
                if self.config.region:
                    image = self._capture_region(self.config.region)
                else:
                    raise ValueError("区域捕捉模式需要指定region参数")
            else:
                raise ValueError(f"不支持的捕捉模式: {self.config.mode}")
            
            # 图像预处理
            image = self._preprocess_image(image)
            
            # 保存捕捉结果
            if self.config.save_captures:
                timestamp = int(time.time())
                filename = f"capture_{timestamp}.png"
                save_path = Path(self.config.save_dir) / filename
                cv2.imwrite(str(save_path), image)
                logger.debug(f"捕捉图像已保存: {save_path}")
            
            logger.info(f"捕捉完成，图像尺寸: {image.shape}")
            return image
            
        except Exception as e:
            logger.error(f"捕捉失败: {e}")
            raise
    
    def _capture_full_screen(self) -> np.ndarray:
        """捕捉整个屏幕"""
        try:
            # 使用PIL的ImageGrab，更稳定
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            return image
        except Exception as e:
            logger.error(f"全屏捕捉失败: {e}")
            # 备选方案：使用mss
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]  # 主显示器
                    screenshot = sct.grab(monitor)
                    image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                    return image
            except Exception as e2:
                logger.error(f"备选捕捉方案也失败: {e2}")
                raise
    
    def _capture_region(self, region: Tuple[int, int, int, int]) -> np.ndarray:
        """捕捉指定区域"""
        x1, y1, x2, y2 = region
        width = x2 - x1
        height = y2 - y1
        
        if width <= 0 or height <= 0:
            raise ValueError(f"无效的区域: {region}")
        
        try:
            from PIL import ImageGrab
            bbox = (x1, y1, x2, y2)
            screenshot = ImageGrab.grab(bbox=bbox)
            image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            return image
        except Exception as e:
            logger.error(f"区域捕捉失败: {e}")
            raise
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """图像预处理"""
        processed = image.copy()
        preprocess = self.config.preprocessing
        
        # 调整大小
        if preprocess.get("resize_factor", 1.0) != 1.0:
            factor = preprocess["resize_factor"]
            h, w = processed.shape[:2]
            new_w = int(w * factor)
            new_h = int(h * factor)
            processed = cv2.resize(processed, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 转换为灰度图
        if preprocess.get("grayscale", False):
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)  # 保持3通道
        
        # 去噪
        if preprocess.get("denoise", False):
            processed = cv2.fastNlMeansDenoisingColored(processed, None, 10, 10, 7, 21)
        
        # 增强对比度
        if preprocess.get("enhance_contrast", False):
            # 使用CLAHE（限制对比度自适应直方图均衡化）
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            processed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return processed

class CropModule:
    """裁剪模块"""
    
    def __init__(self, config: CropConfig):
        self.config = config
        if self.config.save_crops:
            Path(self.config.save_dir).mkdir(parents=True, exist_ok=True)
        
        # 如果使用ML模型，加载模型
        if self.config.method in [CropMethod.ML_MODEL, CropMethod.HYBRID]:
            self.ml_model = self._load_ml_model()
        else:
            self.ml_model = None
    
    def _load_ml_model(self) -> Optional[Any]:
        """加载机器学习模型"""
        # 这里可以加载训练好的模型
        # 暂时返回None，后续实现
        return None
    
    def detect_product_cards(self, image: np.ndarray) -> List[ProductCard]:
        """
        检测图像中的商品卡片
        
        Args:
            image: 输入图像
            
        Returns:
            商品卡片列表
        """
        logger.info(f"开始检测商品卡片，使用方法: {self.config.method}")
        
        if self.config.method == 'edge_detection':
            cards = self._detect_by_edges(image)
        elif self.config.method == 'contour_detection':
            cards = self._detect_by_contours(image)
        elif self.config.method == 'ml_model':
            cards = self._detect_by_ml_model(image)
        elif self.config.method == 'hybrid':
            cards = self._detect_by_hybrid(image)
        else:
            raise ValueError(f"不支持的裁剪方法: {self.config.method}")
        
        # 非极大值抑制
        cards = self._non_maximum_suppression(cards)
        
        # 裁剪图像并保存
        for i, card in enumerate(cards):
            x1, y1, x2, y2 = card.bbox
            card_image = image[y1:y2, x1:x2]
            card.image = card_image
            
            if self.config.save_crops:
                timestamp = int(time.time())
                filename = f"card_{timestamp}_{i}.png"
                save_path = Path(self.config.save_dir) / filename
                cv2.imwrite(str(save_path), card_image)
                logger.debug(f"商品卡片已保存: {save_path}")
        
        logger.info(f"检测完成，找到 {len(cards)} 个商品卡片")
        return cards
    
    def _detect_by_edges(self, image: np.ndarray) -> List[ProductCard]:
        """通过边缘检测检测商品卡片"""
        cards = []
        
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 
                             self.config.edge_threshold_low, 
                             self.config.edge_threshold_high)
            
            # 形态学操作（闭合操作，连接边缘）
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 筛选轮廓
            for i, contour in enumerate(contours):
                # 获取边界矩形
                x, y, w, h = cv2.boundingRect(contour)
                
                # 检查尺寸和宽高比
                if self._is_valid_card(w, h):
                    card = ProductCard(
                        index=i,
                        bbox=(x, y, x + w, y + h),
                        confidence=0.8,  # 基于面积和形状的置信度
                        features={
                            "method": "edge_detection",
                            "area": w * h,
                            "aspect_ratio": w / h
                        }
                    )
                    cards.append(card)
            
        except Exception as e:
            logger.error(f"边缘检测失败: {e}")
        
        return cards
    
    def _detect_by_contours(self, image: np.ndarray) -> List[ProductCard]:
        """通过轮廓检测检测商品卡片"""
        cards = []
        
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 二值化
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 查找轮廓
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 筛选轮廓
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # 根据面积筛选
                if (area >= self.config.contour_min_area and 
                    area <= self.config.contour_max_area):
                    
                    # 获取边界矩形
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 检查尺寸和宽高比
                    if self._is_valid_card(w, h):
                        card = ProductCard(
                            index=i,
                            bbox=(x, y, x + w, y + h),
                            confidence=min(area / self.config.contour_max_area, 1.0),
                            features={
                                "method": "contour_detection",
                                "area": area,
                                "perimeter": cv2.arcLength(contour, True),
                                "aspect_ratio": w / h
                            }
                        )
                        cards.append(card)
            
        except Exception as e:
            logger.error(f"轮廓检测失败: {e}")
        
        return cards
    
    def _detect_by_ml_model(self, image: np.ndarray) -> List[ProductCard]:
        """通过机器学习模型检测商品卡片"""
        cards = []
        
        try:
            # 这里可以实现机器学习模型检测
            # 暂时使用简单的替代方法
            logger.warning("ML模型检测尚未实现，使用轮廓检测作为替代")
            cards = self._detect_by_contours(image)
            
            # 为每个卡片添加ML特征标记
            for card in cards:
                card.features["method"] = "ml_model_placeholder"
                card.confidence = card.confidence * 0.9  # 降低置信度
            
        except Exception as e:
            logger.error(f"ML模型检测失败: {e}")
        
        return cards
    
    def _detect_by_hybrid(self, image: np.ndarray) -> List[ProductCard]:
        """混合方法检测商品卡片"""
        all_cards = []
        
        # 使用多种方法检测
        edge_cards = self._detect_by_edges(image)
        contour_cards = self._detect_by_contours(image)
        
        # 合并结果
        all_cards.extend(edge_cards)
        all_cards.extend(contour_cards)
        
        # 如果可用，添加ML检测结果
        if self.ml_model:
            ml_cards = self._detect_by_ml_model(image)
            all_cards.extend(ml_cards)
        
        # 移除重复的卡片（基于边界框重叠）
        unique_cards = []
        used_indices = set()
        
        for i, card1 in enumerate(all_cards):
            if i in used_indices:
                continue
                
            # 查找与当前卡片重叠的其他卡片
            overlapping_indices = [i]
            for j, card2 in enumerate(all_cards[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                # 计算IoU（交并比）
                iou = self._calculate_iou(card1.bbox, card2.bbox)
                if iou > 0.5:  # 重叠度较高
                    overlapping_indices.append(j)
            
            # 从重叠的卡片中选择置信度最高的
            if overlapping_indices:
                best_idx = max(overlapping_indices, 
                              key=lambda idx: all_cards[idx].confidence)
                unique_cards.append(all_cards[best_idx])
                used_indices.update(overlapping_indices)
        
        return unique_cards
    
    def _is_valid_card(self, width: int, height: int) -> bool:
        """检查是否为有效的商品卡片尺寸"""
        # 检查最小/最大尺寸
        if (width < self.config.min_card_width or 
            height < self.config.min_card_height or
            width > self.config.max_card_width or
            height > self.config.max_card_height):
            return False
        
        # 检查宽高比
        aspect_ratio = width / height
        if (aspect_ratio < self.config.min_aspect_ratio or 
            aspect_ratio > self.config.max_aspect_ratio):
            return False
        
        return True
    
    def _calculate_iou(self, bbox1: Tuple[int, int, int, int], 
                      bbox2: Tuple[int, int, int, int]) -> float:
        """计算两个边界框的交并比"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # 计算交集区域
        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)
        
        if x_right <= x_left or y_bottom <= y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # 计算并集区域
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def _non_maximum_suppression(self, cards: List[ProductCard]) -> List[ProductCard]:
        """非极大值抑制，移除重叠的卡片"""
        if not cards:
            return []
        
        # 按置信度排序
        cards_sorted = sorted(cards, key=lambda c: c.confidence, reverse=True)
        keep = []
        
        while cards_sorted:
            # 选择置信度最高的卡片
            current = cards_sorted.pop(0)
            keep.append(current)
            
            # 移除与当前卡片重叠的卡片
            cards_sorted = [
                card for card in cards_sorted
                if self._calculate_iou(current.bbox, card.bbox) < self.config.overlap_threshold
            ]
        
        return keep

class VisionProcessor:
    """视觉处理器主类"""
    
    def __init__(self):
        # 加载配置
        init_config()
        self.config_manager = get_dict_config()
        self.vision_config = self.config_manager.get("vision", {})
        
        # 初始化子模块
        self.capture_module = CaptureModule(
            CaptureConfig(**self.vision_config.get("capture", {}))
        )
        
        self.crop_module = CropModule(
            CropConfig(**self.vision_config.get("crop", {}))
        )
        
        # 状态跟踪
        self.last_capture_time = None
        self.last_crop_time = None
        self.processed_count = 0
        
        logger.info("视觉处理器初始化完成")
    
    def process(self, capture_mode: str = "full_screen") -> List[ProductCard]:
        """
        执行完整的视觉处理流程
        
        Args:
            capture_mode: 捕捉模式，可选值为"full_screen"（全屏）或"region"（指定区域）
        Returns:
            检测到的商品卡片列表
        """
        logger.info("开始视觉处理流程")
        start_time = time.time()
        
        try:
            # 步骤1: 捕捉
            self.capture_module.config.mode = capture_mode
            
            image = self.capture_module.capture()
            self.last_capture_time = time.time()
            
            # 步骤2: 裁剪
            cards = self.crop_module.detect_product_cards(image)
            self.last_crop_time = time.time()
            
            # 更新统计
            self.processed_count += 1
            
            # 计算处理时间
            total_time = time.time() - start_time
            logger.info(f"视觉处理完成，耗时: {total_time:.2f}秒，检测到 {len(cards)} 个商品卡片")
            
            return cards
            
        except Exception as e:
            logger.error(f"视觉处理失败: {e}")
            return []
    
    def process_image(self, image: np.ndarray) -> List[ProductCard]:
        """
        处理已有的图像
        
        Args:
            image: 输入图像
            
        Returns:
            检测到的商品卡片列表
        """
        logger.info("开始处理已有图像")
        
        try:
            # 仅执行裁剪步骤
            cards = self.crop_module.detect_product_cards(image)
            return cards
            
        except Exception as e:
            logger.error(f"图像处理失败: {e}")
            return []
    
    def visualize_results(self, image: np.ndarray, cards: List[ProductCard]) -> np.ndarray:
        """
        可视化检测结果
        
        Args:
            image: 原始图像
            cards: 商品卡片列表
            
        Returns:
            带有标注的图像
        """
        vis_image = image.copy()
        
        for i, card in enumerate(cards):
            x1, y1, x2, y2 = card.bbox
            
            # 绘制边界框
            color = (0, 255, 0)  # 绿色
            thickness = 2
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, thickness)
            
            # 绘制卡片序号
            text = f"Card {card.index}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            text_thickness = 1
            text_size = cv2.getTextSize(text, font, font_scale, text_thickness)[0]
            
            # 在边界框上方绘制文本背景
            cv2.rectangle(vis_image, 
                         (x1, y1 - text_size[1] - 5),
                         (x1 + text_size[0], y1),
                         color, -1)
            
            # 绘制文本
            cv2.putText(vis_image, text, (x1, y1 - 5),
                       font, font_scale, (255, 255, 255), text_thickness)
            
            # 绘制置信度
            conf_text = f"Conf: {card.confidence:.2f}"
            cv2.putText(vis_image, conf_text, (x1, y2 + 15),
                       font, 0.4, (255, 0, 0), 1)
        
        return vis_image
    
    def save_results(self, image: np.ndarray, cards: List[ProductCard], 
                    output_dir: str = "results") -> Dict[str, Any]:
        """
        保存处理结果
        
        Args:
            image: 原始图像
            cards: 商品卡片列表
            output_dir: 输出目录
            
        Returns:
            结果信息字典
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        results = {
            "timestamp": timestamp,
            "total_cards": len(cards),
            "cards": []
        }
        
        # 保存可视化图像
        vis_image = self.visualize_results(image, cards)
        vis_path = output_path / f"visualization_{timestamp}.png"
        cv2.imwrite(str(vis_path), vis_image)
        results["visualization_path"] = str(vis_path)
        
        # 保存每个卡片的信息
        for i, card in enumerate(cards):
            card_info = {
                "index": card.index,
                "bbox": card.bbox,
                "confidence": card.confidence,
                "width": card.bbox[2] - card.bbox[0],
                "height": card.bbox[3] - card.bbox[1],
                "features": card.features
            }
            results["cards"].append(card_info)
            
            # 保存卡片图像
            if card.image is not None:
                card_path = output_path / f"card_{timestamp}_{i}.png"
                cv2.imwrite(str(card_path), card.image)
                card_info["image_path"] = str(card_path)
        
        # 保存JSON结果
        json_path = output_path / f"results_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"结果已保存到: {output_dir}")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        return {
            "processed_count": self.processed_count,
            "last_capture_time": self.last_capture_time,
            "last_crop_time": self.last_crop_time,
            "capture_config": self.capture_module.config.__dict__,
            "crop_config": self.crop_module.config.__dict__
        }

# 工厂函数
def create_vision_processor() -> VisionProcessor:
    """创建视觉处理器实例"""
    return VisionProcessor()