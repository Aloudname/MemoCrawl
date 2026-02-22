"""
vision_engine.py
视觉识别模块统一API入口

整合所有子模块（截图、检测、OCR、分类、调试）的核心引擎。
对外提供统一、简洁的接口，隐藏内部流水线细节。

这是视觉识别模块的核心类，也是其它模块（如 auto_browser.py、main_controller.py）
调用视觉功能的唯一接口。

工作流：
    截图(capture) → 卡片检测(detect) → 区域分割(segment) → 
    OCR识别(recognize) → 图片分类(classify) → 组装结果 → 输出CSV

依赖的子模块：
- capture.py:          ScreenCapture
- detector.py:         ElementDetector
- ocr_engine.py:       OCREngine
- classifier.py:       ProductClassifier
- debug_visualizer.py: DebugVisualizer
"""

import os
import time
import logging
import numpy as np

from typing import List, Optional, Callable, Dict, Any

from src.modules.vision.models import (
    VisionConfig, ProductCard, PageRecognitionResult,
    BoundingBox, TextRegion, RegionType
)
from src.modules.vision.capture import ScreenCapture
from src.modules.vision.detector import ElementDetector
from src.modules.vision.ocr_engine import OCREngine
from src.modules.vision.classifier import ProductClassifier
from src.modules.vision.debug_visualizer import DebugVisualizer

logger = logging.getLogger(__name__)


class VisionEngine:
    """
    视觉识别引擎 — 统一API入口
    
    提供从截图到商品信息提取的完整流水线，
    同时暴露各子模块的独立API以支持灵活调用。
    
    使用示例:
        >>> from src.modules.vision import VisionEngine, VisionConfig
        >>> config = VisionConfig(debug_mode=True)
        >>> engine = VisionEngine(config)
        >>> 
        >>> # 方式1: 一键执行完整流水线
        >>> result = engine.capture_and_recognize()
        >>> for card in result.valid_cards:
        ...     print(f"{card.product_name}: ¥{card.price}")
        >>> 
        >>> # 方式2: 分步调用
        >>> screenshot = engine.capture.capture_fullscreen()
        >>> cards = engine.detector.detect_product_cards(screenshot)
        >>> # ... 自定义后续处理
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化视觉识别引擎
        
        Args:
            config: 视觉模块配置，None则使用默认配置
        """
        self.config = config or VisionConfig()
        
        # 初始化各子模块
        self.capture = ScreenCapture(self.config)
        self.detector = ElementDetector(self.config)
        self.ocr = OCREngine(self.config)
        self.classifier = ProductClassifier(self.config)
        self.debugger = DebugVisualizer(self.config)
        
        # 回调函数（用于触发模式下的结果通知）
        self._on_result_callback: Optional[Callable[[PageRecognitionResult], None]] = None
        
        logger.info("VisionEngine 初始化完成, 所有子模块就绪")
    
    @classmethod
    def from_munch_config(cls, global_config) -> 'VisionEngine':
        """
        从全局Munch配置对象创建VisionEngine
        
        Args:
            global_config: 全局配置对象 (Munch)
        
        Returns:
            VisionEngine: 引擎实例
        """
        vision_config = VisionConfig.from_munch(global_config)
        return cls(vision_config)
    
    # ==================== 核心流水线 ====================
    
    def capture_and_recognize(self,
                              image: Optional[np.ndarray] = None,
                              page_index: int = 0,
                              source: str = "京东"
                              ) -> PageRecognitionResult:
        """
        执行完整的视觉识别流水线
        
        流程:
        1. 截图（如果未提供image参数）
        2. 预处理
        3. 检测商品卡片
        4. 对每个卡片进行区域分割
        5. OCR识别文字（区分商品名与价格）
        6. 分类商品图片
        7. 组装结果并输出
        
        Args:
            image: 输入图像（BGR），None则自动截图
            page_index: 页码标识
            source: 来源标识（默认"京东"）
            
        Returns:
            PageRecognitionResult: 完整的识别结果
        """
        start_time = time.time()
        result = PageRecognitionResult(page_index=page_index)
        
        if self.config.debug_mode:
            self.debugger.new_session()
        
        try:
            # ===== 阶段1: 截图 =====
            if image is None:
                logger.info("[阶段1/6] 正在截图...")
                image = self.capture.capture_with_config()
            else:
                logger.info("[阶段1/6] 使用提供的图像")
            
            result.screenshot = image
            
            if self.config.debug_mode:
                self.debugger.save_stage(image, "01_screenshot")
            
            # ===== 阶段2: 预处理 =====
            logger.info("[阶段2/6] 图像预处理...")
            processed = self.capture.preprocess(
                image, denoise=True, sharpen=False, adjust_contrast=False
            )
            
            if self.config.debug_mode:
                self.debugger.save_stage(processed, "02_preprocessed")
            
            # ===== 阶段3: 检测商品卡片 =====
            logger.info("[阶段3/6] 检测商品卡片...")
            cards = self.detector.detect_product_cards(processed)
            
            if not cards:
                result.errors.append("未检测到任何商品卡片")
                logger.warning("未检测到商品卡片")
                
                if self.config.debug_mode:
                    annotated = self.debugger.draw_bboxes(image, [])
                    self.debugger.save_stage(annotated, "03_detection_empty")
                
                result.processing_time_ms = (time.time() - start_time) * 1000
                return result
            
            logger.info(f"检测到 {len(cards)} 个商品卡片")
            
            if self.config.debug_mode:
                annotated = self.debugger.draw_bboxes(
                    image, [c.bbox for c in cards]
                )
                self.debugger.save_stage(annotated, "03_detection", {
                    "card_count": len(cards)
                })
                self.debugger.save_card_crops(cards)
            
            # ===== 阶段4-5: 逐卡片处理 =====
            logger.info("[阶段4-5/6] 逐卡片OCR识别与分类...")
            for i, card in enumerate(cards):
                try:
                    self._process_single_card(card, source)
                    logger.debug(f"卡片#{i}: name='{card.product_name}', "
                                f"price='{card.price}'")
                except Exception as e:
                    error_msg = f"处理卡片#{i}失败: {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)
            
            result.cards = cards
            
            # ===== 阶段6: 生成调试图像和报告 =====
            logger.info("[阶段6/6] 生成结果...")
            
            if self.config.debug_mode:
                debug_image = self.debugger.draw_product_cards(
                    image, cards, show_index=True, show_regions=True
                )
                result.debug_image = debug_image
                self.debugger.save_stage(debug_image, "06_final_result")
                self.debugger.save_recognition_report(result)
            
        except Exception as e:
            error_msg = f"视觉识别流水线异常: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"识别完成: {result.valid_card_count}/{result.card_count} 有效, "
                     f"耗时 {result.processing_time_ms:.0f}ms")
        
        return result
    
    def _process_single_card(self, card: ProductCard, source: str = "京东"):
        """
        处理单个商品卡片：区域分割 → OCR → 分类
        
        Args:
            card: 商品卡片对象（会被就地修改）
            source: 来源标识
        """
        if card.card_image is None:
            return
        
        card_img = card.card_image
        
        # ---- 区域分割 ----
        regions = self.detector.segment_card_regions(card_img)
        
        image_region_img = None
        text_region_img = None
        
        for bbox, region_type in regions:
            if region_type == RegionType.IMAGE:
                image_region_img = bbox.crop_from(card_img)
            elif region_type in (RegionType.TEXT, RegionType.TITLE):
                text_region_img = bbox.crop_from(card_img)
        
        # ---- OCR识别 ----
        if text_region_img is not None and text_region_img.size > 0:
            text_regions = self.ocr.recognize_lines(text_region_img)
        else:
            # 对整个卡片做OCR
            text_regions = self.ocr.recognize_lines(card_img)
        
        card.text_regions = text_regions
        
        # 提取商品名
        card.product_name = self.ocr.extract_product_name(text_regions)
        
        # 提取价格
        prices = self.ocr.extract_all_prices(text_regions)
        if prices:
            card.price = prices[0]  # 取第一个识别到的价格
        else:
            # 尝试从整个卡片中寻找价格
            all_text = self.ocr.recognize_text(card_img)
            price = self.ocr.extract_price(all_text)
            if price:
                card.price = price
        
        # 生成概述
        non_price_texts = [
            r.text for r in text_regions 
            if r.region_type not in (RegionType.PRICE, RegionType.UNKNOWN)
        ]
        card.description = " | ".join(non_price_texts[:3])  # 取前3个文字段
        
        # 来源
        card.source = source
        
        # ---- 图片分类 ----
        if image_region_img is not None and image_region_img.size > 0:
            classification = self.classifier.classify(image_region_img)
            card.image_region = classification
    
    # ==================== 触发模式API ====================
    
    def start_hotkey_capture(self,
                             callback: Optional[Callable[[PageRecognitionResult], None]] = None,
                             hotkey: Optional[str] = None) -> bool:
        """
        启动快捷键触发模式
        
        当用户按下指定快捷键时，自动截图并启动完整识别流水线。
        
        Args:
            callback: 识别完成后的回调函数
            hotkey: 快捷键组合字符串 (如 "ctrl+shift+c")
            
        Returns:
            bool: 是否注册成功
        """
        self._on_result_callback = callback
        
        def _on_capture(screenshot: np.ndarray):
            result = self.capture_and_recognize(image=screenshot)
            if self._on_result_callback:
                self._on_result_callback(result)
        
        return self.capture.register_hotkey(_on_capture, hotkey)
    
    def stop_hotkey_capture(self):
        """停止快捷键触发模式"""
        self.capture.unregister_hotkey()
        self._on_result_callback = None
        logger.info("快捷键触发模式已停止")
    
    # ==================== 泛用定位API ====================
    
    def locate_element_on_screen(self,
                                 template: np.ndarray,
                                 threshold: float = 0.8,
                                 region: Optional[BoundingBox] = None
                                 ) -> List[BoundingBox]:
        """
        在当前屏幕上定位指定模板元素
        
        泛用API：可用于定位页面上的按钮、图标、文字等任意视觉元素。
        
        Args:
            template: 要查找的模板图像 (BGR)
            threshold: 匹配阈值(0-1)
            region: 搜索区域，None则搜索全屏
            
        Returns:
            List[BoundingBox]: 找到的元素位置列表
        """
        if region:
            screenshot = self.capture.capture_bbox(region)
            results = self.detector.locate_element(
                screenshot, template, threshold, multi_match=True
            )
            # 将坐标偏移回全局坐标
            for bbox in results:
                bbox.x1 += region.x1
                bbox.y1 += region.y1
                bbox.x2 += region.x1
                bbox.y2 += region.y1
        else:
            screenshot = self.capture.capture_fullscreen()
            results = self.detector.locate_element(
                screenshot, template, threshold, multi_match=True
            )
        
        return results
    
    def locate_text_on_screen(self,
                              target_text: str,
                              region: Optional[BoundingBox] = None,
                              fuzzy: bool = True
                              ) -> List[TextRegion]:
        """
        在当前屏幕上定位指定文字
        
        泛用API：可用于查找页面上特定文字的位置。
        
        Args:
            target_text: 要查找的文字
            region: 搜索区域，None则搜索全屏
            fuzzy: 是否模糊匹配
            
        Returns:
            List[TextRegion]: 找到的文字区域列表（含坐标）
        """
        if region:
            screenshot = self.capture.capture_bbox(region)
            results = self.ocr.locate_text_in_image(
                screenshot, target_text, fuzzy=fuzzy
            )
            # 坐标偏移
            for r in results:
                r.bbox.x1 += region.x1
                r.bbox.y1 += region.y1
                r.bbox.x2 += region.x1
                r.bbox.y2 += region.y1
        else:
            screenshot = self.capture.capture_fullscreen()
            results = self.ocr.locate_text_in_image(
                screenshot, target_text, fuzzy=fuzzy
            )
        
        return results
    
    def locate_price_on_screen(self,
                               region: Optional[BoundingBox] = None
                               ) -> List[TextRegion]:
        """
        在当前屏幕上定位所有价格元素
        
        泛用API：快速找到页面上的所有价格标签。
        
        Args:
            region: 搜索区域
            
        Returns:
            List[TextRegion]: 价格文字区域列表
        """
        if region:
            screenshot = self.capture.capture_bbox(region)
            results = self.ocr.locate_price_regions(screenshot)
            for r in results:
                r.bbox.x1 += region.x1
                r.bbox.y1 += region.y1
                r.bbox.x2 += region.x1
                r.bbox.y2 += region.y1
        else:
            screenshot = self.capture.capture_fullscreen()
            results = self.ocr.locate_price_regions(screenshot)
        
        return results
    
    def locate_colored_element(self,
                               lower_hsv: tuple,
                               upper_hsv: tuple,
                               min_area: int = 100,
                               region: Optional[BoundingBox] = None
                               ) -> List[BoundingBox]:
        """
        在当前屏幕上定位指定颜色的UI元素
        
        泛用API：如定位红色价格标签、蓝色按钮等。
        
        Args:
            lower_hsv: HSV颜色下界
            upper_hsv: HSV颜色上界
            min_area: 最小面积
            region: 搜索区域
            
        Returns:
            List[BoundingBox]: 找到的彩色区域
        """
        if region:
            screenshot = self.capture.capture_bbox(region)
        else:
            screenshot = self.capture.capture_fullscreen()
        
        results = self.detector.locate_colored_region(
            screenshot, lower_hsv, upper_hsv, min_area
        )
        
        if region:
            for bbox in results:
                bbox.x1 += region.x1
                bbox.y1 += region.y1
                bbox.x2 += region.x1
                bbox.y2 += region.y1
        
        return results
    
    # ==================== 状态与信息 ====================
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎状态信息"""
        return {
            "config": {
                "detection_method": self.config.detection_method,
                "ocr_lang": self.config.ocr_lang,
                "debug_mode": self.config.debug_mode,
            },
            "classifier": self.classifier.get_library_info(),
            "screen_size": self.capture.get_screen_size(),
        }
