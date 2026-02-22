"""
ocr_engine.py
OCR文字识别引擎

负责：
1. 对裁剪出的图像区域进行OCR文字识别
2. 对识别出的文字进行分类（商品名 / 价格 / 其它）
3. 提取和清洗价格字符串
4. 提供灵活的OCR配置接口

依赖库：
- pytesseract: Tesseract OCR的Python封装 (已在requirements.txt)
- cv2 (opencv-python): 图像预处理
- PIL (pillow): 图像格式转换
- numpy: 数组操作

外部依赖：
- Tesseract OCR 引擎 (需要单独安装)
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki
  - 需要安装中文语言包 chi_sim
"""

import re
import logging
import numpy as np

from typing import List, Dict, Optional, Tuple

try:
    import cv2
except ImportError:
    raise ImportError("请安装 opencv-python: pip install opencv-python")

try:
    from PIL import Image
except ImportError:
    raise ImportError("请安装 pillow: pip install pillow")

try:
    import pytesseract
    # pytesseract.image_to_string: 核心OCR方法
    # pytesseract.image_to_data: 返回含坐标和置信度的详细结果
    # pytesseract.Output.DICT: 指定输出为字典格式
except ImportError:
    raise ImportError("请安装 pytesseract: pip install pytesseract")

from src.modules.vision.models import (
    VisionConfig, BoundingBox, TextRegion, RegionType
)

logger = logging.getLogger(__name__)


class OCREngine:
    """
    OCR文字识别引擎
    
    基于Tesseract OCR实现文字检测与识别，
    并提供价格/商品名的自动分类能力。
    """
    
    # 价格特征的正则表达式
    # 匹配: ¥123, ￥123.45, $99, 123.00, ¥ 3,199.00 等
    PRICE_PATTERN = re.compile(
        r'[¥￥$€£]?\s*[\d,]+\.?\d*'
        r'|[\d,]+\.?\d*\s*[元块]'
    )
    
    # 纯数字价格（不含货币符号）
    NUMERIC_PRICE_PATTERN = re.compile(r'^\s*[\d,]+\.?\d{0,2}\s*$')
    
    # 包含货币符号的强价格特征
    STRONG_PRICE_PATTERN = re.compile(r'[¥￥$€£]\s*[\d,]+\.?\d*')
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化OCR引擎
        
        Args:
            config: 视觉模块配置
        """
        self.config = config or VisionConfig()
        
        # 配置Tesseract路径
        if self.config.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_cmd
        
        # 验证Tesseract可用性
        self._validate_tesseract()
        
        logger.info(f"OCREngine 初始化完成, 语言: {self.config.ocr_lang}, "
                     f"PSM: {self.config.ocr_psm}")
    
    def _validate_tesseract(self):
        """验证Tesseract是否可用"""
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract版本: {version}")
        except Exception as e:
            logger.error(
                f"Tesseract不可用: {e}\n"
                f"请确认已安装Tesseract OCR引擎并配置了正确路径。\n"
                f"Windows安装: https://github.com/UB-Mannheim/tesseract/wiki\n"
                f"安装后需要将tesseract.exe路径加入系统PATH，"
                f"或在config.yaml中设置 vision.tesseract_cmd 参数。"
            )
    
    # ==================== 核心OCR方法 ====================
    
    def recognize_text(self, 
                       image: np.ndarray,
                       lang: Optional[str] = None,
                       psm: Optional[int] = None) -> str:
        """
        对图像进行OCR文字识别（简单接口）
        
        Args:
            image: 输入图像 (BGR 或灰度)
            lang: 语言包，None则使用配置值
            psm: 页面分割模式，None则使用配置值
                 常用值: 3=全自动, 6=假设为一个文本块, 
                         7=单行, 8=单词, 13=单行(无OSD)
            
        Returns:
            str: 识别出的文字
        """
        lang = lang or self.config.ocr_lang
        psm = psm if psm is not None else self.config.ocr_psm
        
        try:
            # 预处理
            processed = self._preprocess_for_ocr(image)
            
            # 转为PIL Image (pytesseract接受PIL Image或numpy数组)
            pil_image = Image.fromarray(processed)
            
            # OCR识别
            custom_config = f'--oem 3 --psm {psm}'
            text = pytesseract.image_to_string(
                pil_image, lang=lang, config=custom_config
            )
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            return ""
    
    def recognize_text_detailed(self, 
                                image: np.ndarray,
                                lang: Optional[str] = None,
                                psm: Optional[int] = None
                                ) -> List[TextRegion]:
        """
        对图像进行详细OCR识别，返回每个文字块的位置和置信度
        
        Args:
            image: 输入图像 (BGR 或灰度)
            lang: 语言包
            psm: 页面分割模式
            
        Returns:
            List[TextRegion]: 识别出的文字区域列表（含坐标和置信度）
        """
        lang = lang or self.config.ocr_lang
        psm = psm if psm is not None else self.config.ocr_psm
        
        try:
            processed = self._preprocess_for_ocr(image)
            pil_image = Image.fromarray(processed)
            
            custom_config = f'--oem 3 --psm {psm}'
            
            # image_to_data 返回每个单词/字符的坐标和置信度
            # 返回格式: dict, 包含 level, page_num, block_num, par_num,
            #           line_num, word_num, left, top, width, height, conf, text
            data = pytesseract.image_to_data(
                pil_image, lang=lang, config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            text_regions = []
            n_items = len(data['text'])
            
            for i in range(n_items):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                
                # 过滤空文本和低置信度结果
                if not text or conf < self.config.ocr_confidence_threshold:
                    continue
                
                bbox = BoundingBox(
                    x1=data['left'][i],
                    y1=data['top'][i],
                    x2=data['left'][i] + data['width'][i],
                    y2=data['top'][i] + data['height'][i],
                    confidence=conf / 100.0,  # Tesseract conf 范围0-100
                    label="text"
                )
                
                region_type = self.classify_text(text)
                
                text_regions.append(TextRegion(
                    bbox=bbox,
                    text=text,
                    confidence=conf / 100.0,
                    region_type=region_type
                ))
            
            logger.debug(f"详细OCR识别完成，共 {len(text_regions)} 个文字区域")
            return text_regions
            
        except Exception as e:
            logger.error(f"详细OCR识别失败: {e}")
            return []
    
    def recognize_lines(self,
                        image: np.ndarray,
                        lang: Optional[str] = None) -> List[TextRegion]:
        """
        按行识别文字，将同一行的文字合并
        
        Args:
            image: 输入图像
            lang: 语言包
            
        Returns:
            List[TextRegion]: 按行合并的文字区域列表
        """
        lang = lang or self.config.ocr_lang
        
        try:
            processed = self._preprocess_for_ocr(image)
            pil_image = Image.fromarray(processed)
            
            custom_config = f'--oem 3 --psm 6'
            data = pytesseract.image_to_data(
                pil_image, lang=lang, config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            # 按行号分组
            lines: Dict[Tuple[int, int, int], List[dict]] = {}
            n_items = len(data['text'])
            
            for i in range(n_items):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                
                if not text or conf < self.config.ocr_confidence_threshold:
                    continue
                
                # 以 (block, par, line) 作为行标识
                line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
                
                if line_key not in lines:
                    lines[line_key] = []
                
                lines[line_key].append({
                    'text': text,
                    'conf': conf,
                    'left': data['left'][i],
                    'top': data['top'][i],
                    'width': data['width'][i],
                    'height': data['height'][i]
                })
            
            # 合并每行文字
            result = []
            for line_key, words in lines.items():
                if not words:
                    continue
                
                # 合并文字
                line_text = " ".join(w['text'] for w in words)
                avg_conf = sum(w['conf'] for w in words) / len(words)
                
                # 计算整行的边界框
                min_left = min(w['left'] for w in words)
                min_top = min(w['top'] for w in words)
                max_right = max(w['left'] + w['width'] for w in words)
                max_bottom = max(w['top'] + w['height'] for w in words)
                
                bbox = BoundingBox(
                    x1=min_left, y1=min_top,
                    x2=max_right, y2=max_bottom,
                    confidence=avg_conf / 100.0,
                    label="line"
                )
                
                region_type = self.classify_text(line_text)
                
                result.append(TextRegion(
                    bbox=bbox,
                    text=line_text,
                    confidence=avg_conf / 100.0,
                    region_type=region_type
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"按行OCR识别失败: {e}")
            return []
    
    # ==================== 文字分类 ====================
    
    def classify_text(self, text: str) -> RegionType:
        """
        分类文字内容为价格/标题/普通文字
        
        判断逻辑:
        1. 含有 ¥/￥/$ 等货币符号 → PRICE
        2. 纯数字(可能是价格) → PRICE
        3. 含有"元""块"等后缀 → PRICE
        4. 其它较长文字 → TITLE / TEXT
        
        Args:
            text: 待分类文字
            
        Returns:
            RegionType: 分类结果
        """
        cleaned = text.strip()
        if not cleaned:
            return RegionType.UNKNOWN
        
        # 检查强价格特征（含货币符号）
        if self.STRONG_PRICE_PATTERN.search(cleaned):
            return RegionType.PRICE
        
        # 检查 "XX元" / "XX块" 格式
        if re.search(r'\d+\.?\d*\s*[元块]', cleaned):
            return RegionType.PRICE
        
        # 纯数字（可能是价格）
        digits_only = re.sub(r'[,.\s]', '', cleaned)
        if digits_only.isdigit() and len(digits_only) >= 2:
            # 2位以上纯数字且合理的价格范围
            try:
                val = float(cleaned.replace(',', ''))
                if 1.0 <= val <= 999999.0:
                    return RegionType.PRICE
            except ValueError:
                pass
        
        # 较长文字判断为标题
        if len(cleaned) >= 6:
            return RegionType.TITLE
        
        return RegionType.TEXT
    
    def extract_price(self, text: str) -> Optional[str]:
        """
        从文字中提取价格字符串
        
        Args:
            text: 含价格信息的文字
            
        Returns:
            str: 清洗后的价格字符串，如 "3199.00"。提取失败返回None。
        """
        if not text:
            return None
        
        # 尝试匹配价格模式
        match = self.PRICE_PATTERN.search(text)
        if match:
            price_str = match.group()
            # 清理货币符号和空格
            cleaned = re.sub(r'[¥￥$€£\s元块]', '', price_str)
            cleaned = cleaned.replace(',', '')
            
            if cleaned:
                try:
                    float(cleaned)
                    return cleaned
                except ValueError:
                    pass
        
        # 尝试直接提取数字
        numbers = re.findall(r'(\d+\.?\d*)', text)
        if numbers:
            # 取最大值（通常价格数值最大）
            try:
                values = [(float(n), n) for n in numbers]
                values.sort(reverse=True)
                return values[0][1]
            except ValueError:
                pass
        
        return None
    
    def extract_product_name(self, text_regions: List[TextRegion]) -> str:
        """
        从多个文字区域中提取商品名称
        
        策略：
        - 优先使用被分类为TITLE的区域
        - 如果没有TITLE，使用最长的非价格文字
        
        Args:
            text_regions: OCR识别出的文字区域列表
            
        Returns:
            str: 商品名称
        """
        title_texts = []
        other_texts = []
        
        for region in text_regions:
            if region.region_type == RegionType.TITLE:
                title_texts.append(region.text)
            elif region.region_type == RegionType.TEXT:
                other_texts.append(region.text)
        
        if title_texts:
            # 将所有标题类文字合并
            return " ".join(title_texts)
        elif other_texts:
            # 取最长的非价格文字
            other_texts.sort(key=len, reverse=True)
            return other_texts[0]
        
        return ""
    
    def extract_all_prices(self, text_regions: List[TextRegion]) -> List[str]:
        """
        从文字区域中提取所有价格
        
        Args:
            text_regions: OCR识别出的文字区域列表
            
        Returns:
            List[str]: 价格字符串列表
        """
        prices = []
        for region in text_regions:
            if region.region_type == RegionType.PRICE:
                price = self.extract_price(region.text)
                if price:
                    prices.append(price)
        return prices
    
    # ==================== 图像预处理 ====================
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        针对OCR优化的图像预处理流水线
        
        Args:
            image: 输入图像 (BGR或灰度)
            
        Returns:
            np.ndarray: 预处理后的灰度图像
        """
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 放大小图（小于100px高度的图片放大2倍提升识别率）
        h, w = gray.shape[:2]
        if h < 100:
            scale = max(2, 100 // h)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
        
        # 去噪
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 自适应二值化 (对于文字识别效果较好)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    # ==================== 泛用API ====================
    
    def locate_text_in_image(self,
                             image: np.ndarray,
                             target_text: str,
                             lang: Optional[str] = None,
                             fuzzy: bool = True) -> List[TextRegion]:
        """
        在图像中定位指定文字的位置
        
        这是一个泛用API，可用于定位页面上的任意文字元素。
        
        Args:
            image: 输入图像 (BGR)
            target_text: 要查找的目标文字
            lang: 语言包
            fuzzy: 是否模糊匹配（包含匹配）
            
        Returns:
            List[TextRegion]: 匹配到的文字区域列表
        """
        all_regions = self.recognize_text_detailed(image, lang=lang)
        
        results = []
        for region in all_regions:
            if fuzzy:
                if target_text.lower() in region.text.lower():
                    results.append(region)
            else:
                if target_text == region.text:
                    results.append(region)
        
        logger.debug(f"在图像中搜索 '{target_text}', "
                     f"找到 {len(results)} 个匹配")
        return results
    
    def locate_price_regions(self, image: np.ndarray) -> List[TextRegion]:
        """
        在图像中定位所有价格区域
        
        Args:
            image: 输入图像 (BGR)
            
        Returns:
            List[TextRegion]: 价格文字区域列表
        """
        all_regions = self.recognize_text_detailed(image)
        return [r for r in all_regions if r.region_type == RegionType.PRICE]
