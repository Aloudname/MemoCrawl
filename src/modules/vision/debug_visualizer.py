"""
debug_visualizer.py
调试可视化工具

负责：
1. 在截图上标注检测到的商品卡片边界框
2. 标注文字识别结果和分类信息
3. 保存每个处理阶段的中间结果图像
4. 生成可读的处理报告

用于调试和验证视觉识别流水线的正确性。

依赖库：
- cv2 (opencv-python): 绘图与标注
- numpy: 数组操作
"""

import os
import json
import logging
import numpy as np

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

try:
    import cv2
except ImportError:
    raise ImportError("请安装 opencv-python: pip install opencv-python")

from src.modules.vision.models import (
    VisionConfig, BoundingBox, ProductCard, TextRegion,
    ImageRegion, PageRecognitionResult, RegionType
)

logger = logging.getLogger(__name__)


# 颜色常量 (BGR格式)
COLORS = {
    'card':   (0, 255, 0),     # 绿色 - 商品卡片
    'image':  (255, 165, 0),   # 橙色 - 图片区域
    'text':   (255, 255, 0),   # 青色 - 文字区域
    'price':  (0, 0, 255),     # 红色 - 价格区域
    'title':  (255, 0, 255),   # 品红 - 标题区域
    'unknown':(128, 128, 128), # 灰色 - 未知区域
    'match':  (0, 255, 255),   # 黄色 - 模板匹配
}

REGION_TYPE_COLORS = {
    RegionType.IMAGE:   COLORS['image'],
    RegionType.TEXT:     COLORS['text'],
    RegionType.PRICE:   COLORS['price'],
    RegionType.TITLE:   COLORS['title'],
    RegionType.UNKNOWN: COLORS['unknown'],
}


class DebugVisualizer:
    """
    调试可视化工具
    
    提供丰富的可视化标注功能，帮助调试视觉识别流水线。
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化调试可视化工具
        
        Args:
            config: 视觉模块配置
        """
        self.config = config or VisionConfig()
        
        # 确保输出目录存在
        os.makedirs(self.config.debug_output_dir, exist_ok=True)
        
        # 会话目录（每次运行创建新目录）
        self._session_dir = None
        
        logger.info(f"DebugVisualizer 初始化完成, "
                     f"输出目录: {self.config.debug_output_dir}")
    
    def _get_session_dir(self) -> str:
        """获取或创建当前会话的输出目录"""
        if self._session_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_dir = os.path.join(
                self.config.debug_output_dir, f"session_{timestamp}"
            )
            os.makedirs(self._session_dir, exist_ok=True)
        return self._session_dir
    
    def new_session(self):
        """开始新的调试会话"""
        self._session_dir = None
        self._get_session_dir()
        logger.info(f"新调试会话: {self._session_dir}")
    
    # ==================== 图像标注方法 ====================
    
    def draw_bboxes(self, 
                    image: np.ndarray,
                    bboxes: List[BoundingBox],
                    color: Tuple[int, int, int] = COLORS['card'],
                    thickness: int = 2,
                    show_label: bool = True,
                    show_confidence: bool = True
                    ) -> np.ndarray:
        """
        在图像上绘制边界框
        
        Args:
            image: 输入图像 (BGR)，不会被修改
            bboxes: 边界框列表
            color: 边框颜色 (BGR)
            thickness: 边框线宽
            show_label: 是否显示标签
            show_confidence: 是否显示置信度
            
        Returns:
            np.ndarray: 标注后的图像副本
        """
        annotated = image.copy()
        
        for bbox in bboxes:
            # 绘制矩形
            cv2.rectangle(
                annotated, 
                bbox.top_left, bbox.bottom_right,
                color, thickness
            )
            
            # 标签文字
            if show_label or show_confidence:
                parts = []
                if show_label and bbox.label:
                    parts.append(bbox.label)
                if show_confidence:
                    parts.append(f"{bbox.confidence:.2f}")
                label_text = " | ".join(parts)
                
                if label_text:
                    self._put_text_with_bg(
                        annotated, label_text,
                        (bbox.x1, bbox.y1 - 5),
                        color=color
                    )
        
        return annotated
    
    def draw_product_cards(self,
                           image: np.ndarray,
                           cards: List[ProductCard],
                           show_index: bool = True,
                           show_regions: bool = True
                           ) -> np.ndarray:
        """
        在图像上标注商品卡片检测结果
        
        会绘制：
        - 卡片外框（绿色）
        - 卡片序号
        - 商品名 + 价格
        - 内部区域划分（可选）
        
        Args:
            image: 原始截图 (BGR)
            cards: 检测到的商品卡片列表
            show_index: 是否显示卡片序号
            show_regions: 是否显示内部区域划分
            
        Returns:
            np.ndarray: 标注后的图像副本
        """
        annotated = image.copy()
        
        for card in cards:
            # 绘制卡片外框
            cv2.rectangle(
                annotated,
                card.bbox.top_left, card.bbox.bottom_right,
                COLORS['card'], 2
            )
            
            # 卡片序号
            if show_index:
                self._put_text_with_bg(
                    annotated, f"#{card.card_index}",
                    (card.bbox.x1 + 5, card.bbox.y1 + 20),
                    color=COLORS['card'],
                    font_scale=0.7
                )
            
            # 商品信息
            info_y = card.bbox.y2 + 15
            if card.product_name:
                name_display = card.product_name[:30] + "..." if len(card.product_name) > 30 else card.product_name
                self._put_text_with_bg(
                    annotated, f"名: {name_display}",
                    (card.bbox.x1, info_y),
                    color=COLORS['title'],
                    font_scale=0.5
                )
                info_y += 18
            
            if card.price:
                self._put_text_with_bg(
                    annotated, f"价: ¥{card.price}",
                    (card.bbox.x1, info_y),
                    color=COLORS['price'],
                    font_scale=0.5
                )
            
            # 内部区域
            if show_regions and card.text_regions:
                for text_region in card.text_regions:
                    region_color = REGION_TYPE_COLORS.get(
                        text_region.region_type, COLORS['unknown']
                    )
                    # 区域框需要加上卡片偏移
                    abs_bbox = BoundingBox(
                        x1=card.bbox.x1 + text_region.bbox.x1,
                        y1=card.bbox.y1 + text_region.bbox.y1,
                        x2=card.bbox.x1 + text_region.bbox.x2,
                        y2=card.bbox.y1 + text_region.bbox.y2,
                    )
                    cv2.rectangle(
                        annotated,
                        abs_bbox.top_left, abs_bbox.bottom_right,
                        region_color, 1
                    )
        
        return annotated
    
    def draw_text_regions(self,
                          image: np.ndarray,
                          text_regions: List[TextRegion],
                          show_text: bool = True
                          ) -> np.ndarray:
        """
        标注文字识别区域
        
        Args:
            image: 输入图像
            text_regions: OCR识别的文字区域列表
            show_text: 是否显示识别出的文字
            
        Returns:
            np.ndarray: 标注后的图像
        """
        annotated = image.copy()
        
        for region in text_regions:
            color = REGION_TYPE_COLORS.get(region.region_type, COLORS['unknown'])
            
            cv2.rectangle(
                annotated,
                region.bbox.top_left, region.bbox.bottom_right,
                color, 1
            )
            
            if show_text and region.text:
                display_text = region.text[:20]
                self._put_text_with_bg(
                    annotated, display_text,
                    (region.bbox.x1, region.bbox.y1 - 3),
                    color=color,
                    font_scale=0.4
                )
        
        return annotated
    
    # ==================== 阶段保存 ====================
    
    def save_stage(self,
                   image: np.ndarray,
                   stage_name: str,
                   extra_info: Optional[Dict[str, Any]] = None) -> str:
        """
        保存处理流水线中某个阶段的中间结果
        
        Args:
            image: 该阶段的图像
            stage_name: 阶段名称 (如 "01_capture", "02_detection", etc.)
            extra_info: 额外信息（将写入同名.json文件）
            
        Returns:
            str: 保存的图像路径
        """
        if not self.config.save_debug_images:
            return ""
        
        session_dir = self._get_session_dir()
        
        # 保存图像
        img_path = os.path.join(session_dir, f"{stage_name}.png")
        cv2.imwrite(img_path, image)
        
        # 保存额外信息
        if extra_info:
            json_path = os.path.join(session_dir, f"{stage_name}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(extra_info, f, ensure_ascii=False, indent=2, default=str)
        
        logger.debug(f"调试图像已保存: {img_path}")
        return img_path
    
    def save_card_crops(self, cards: List[ProductCard]) -> List[str]:
        """
        保存每个检测到的商品卡片的裁剪图
        
        Args:
            cards: 商品卡片列表
            
        Returns:
            List[str]: 保存的文件路径列表
        """
        if not self.config.save_debug_images:
            return []
        
        session_dir = self._get_session_dir()
        cards_dir = os.path.join(session_dir, "cards")
        os.makedirs(cards_dir, exist_ok=True)
        
        paths = []
        for card in cards:
            if card.card_image is not None:
                filename = f"card_{card.card_index:03d}.png"
                filepath = os.path.join(cards_dir, filename)
                cv2.imwrite(filepath, card.card_image)
                paths.append(filepath)
                
                # 保存卡片信息
                info_path = os.path.join(cards_dir, f"card_{card.card_index:03d}.json")
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(card.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        
        logger.debug(f"已保存 {len(paths)} 个卡片裁剪图到 {cards_dir}")
        return paths
    
    def save_recognition_report(self, result: PageRecognitionResult) -> str:
        """
        保存完整的识别结果报告
        
        Args:
            result: 页面识别结果
            
        Returns:
            str: 报告文件路径
        """
        session_dir = self._get_session_dir()
        report_path = os.path.join(session_dir, "report.json")
        
        report = {
            "summary": result.summary(),
            "cards": [card.to_dict() for card in result.cards],
            "valid_cards": [card.to_csv_row() for card in result.valid_cards],
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"识别报告已保存: {report_path}")
        
        # 同时在控制台输出摘要
        summary = result.summary()
        logger.info(
            f"━━━ 识别报告 ━━━\n"
            f"  页码: {summary['page_index']}\n"
            f"  时间: {summary['timestamp']}\n"
            f"  检测卡片: {summary['total_cards']}\n"
            f"  有效卡片: {summary['valid_cards']}\n"
            f"  处理耗时: {summary['processing_time_ms']:.0f}ms\n"
            f"  错误数: {len(summary['errors'])}"
        )
        
        if summary['errors']:
            for err in summary['errors']:
                logger.warning(f"  ⚠ {err}")
        
        return report_path
    
    # ==================== 工具方法 ====================
    
    @staticmethod
    def _put_text_with_bg(image: np.ndarray,
                          text: str,
                          position: Tuple[int, int],
                          color: Tuple[int, int, int] = (0, 255, 0),
                          font_scale: float = 0.5,
                          thickness: int = 1):
        """
        在图像上绘制带背景的文字
        
        Args:
            image: 图像 (会被就地修改)
            text: 文字内容
            position: 文字位置 (x, y)
            color: 文字颜色
            font_scale: 字体大小
            thickness: 字体粗细
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # 获取文字大小
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )
        
        x, y = position
        
        # 绘制背景矩形
        cv2.rectangle(
            image,
            (x, y - text_h - baseline - 2),
            (x + text_w + 4, y + 2),
            (0, 0, 0),  # 黑色背景
            cv2.FILLED
        )
        
        # 绘制文字
        cv2.putText(
            image, text, (x + 2, y - baseline),
            font, font_scale, color, thickness, cv2.LINE_AA
        )
    
    @staticmethod
    def create_comparison(images: List[np.ndarray],
                          labels: List[str],
                          max_width: int = 1920) -> np.ndarray:
        """
        创建图像对比图（将多个图像水平排列）
        
        Args:
            images: 图像列表
            labels: 对应标签列表
            max_width: 最大总宽度
            
        Returns:
            np.ndarray: 拼接后的对比图
        """
        if not images:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        
        # 计算统一高度
        target_h = min(img.shape[0] for img in images)
        
        resized = []
        for img, label in zip(images, labels):
            h, w = img.shape[:2]
            scale = target_h / h
            new_w = int(w * scale)
            r = cv2.resize(img, (new_w, target_h))
            
            # 添加标签
            cv2.putText(r, label, (10, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            resized.append(r)
        
        # 水平拼接
        comparison = np.hstack(resized)
        
        # 如果超过最大宽度，缩小
        if comparison.shape[1] > max_width:
            scale = max_width / comparison.shape[1]
            comparison = cv2.resize(comparison, None, fx=scale, fy=scale)
        
        return comparison
