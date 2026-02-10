"""
收集商品卡片样本的工具
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import cv2
import numpy as np
import json
from datetime import datetime

from src.modules.vision_processor import create_vision_processor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class SampleCollector:
    """样本收集器"""
    
    def __init__(self, output_dir: str = "samples/product_cards"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建视觉处理器
        self.processor = create_vision_processor()
        
        # 样本计数器
        self.sample_count = 0
        self.metadata = []
    
    def collect_from_screen(self, num_samples: int = 10):
        """从屏幕收集样本"""
        print(f"开始收集 {num_samples} 个样本")
        print("请确保目标网页已打开并可见")
        
        for i in range(num_samples):
            print(f"\n收集样本 {i+1}/{num_samples}")
            print("3秒后开始捕捉...")
            import time
            time.sleep(3)
            
            try:
                # 捕捉屏幕
                cards = self.processor.process()
                
                if cards:
                    print(f"检测到 {len(cards)} 个商品卡片")
                    
                    # 保存每个卡片
                    for j, card in enumerate(cards):
                        if card.image is not None:
                            self._save_sample(card, i, j)
                    
                    # 添加元数据
                    self.metadata.append({
                        "sample_id": i,
                        "timestamp": datetime.now().isoformat(),
                        "total_cards": len(cards),
                        "capture_mode": self.processor.capture_module.config.mode.value
                    })
                else:
                    print("未检测到商品卡片，跳过此样本")
                    
            except KeyboardInterrupt:
                print("\n收集过程中断")
                break
            except Exception as e:
                print(f"收集样本 {i+1} 时出错: {e}")
                continue
        
        # 保存元数据
        self._save_metadata()
        
        print(f"\n✅ 样本收集完成！共收集 {self.sample_count} 个卡片样本")
    
    def _save_sample(self, card, sample_id: int, card_id: int):
        """保存单个样本"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sample_{timestamp}_s{sample_id}_c{card_id}.png"
        filepath = self.output_dir / filename
        
        # 保存图像
        cv2.imwrite(str(filepath), card.image)
        
        # 保存卡片信息
        info = {
            "filename": filename,
            "sample_id": sample_id,
            "card_id": card_id,
            "bbox": card.bbox,
            "confidence": card.confidence,
            "width": card.image.shape[1],
            "height": card.image.shape[0],
            "timestamp": datetime.now().isoformat(),
            "features": card.features
        }
        
        # 保存JSON元数据
        json_filename = f"sample_{timestamp}_s{sample_id}_c{card_id}.json"
        json_path = self.output_dir / json_filename
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        
        self.sample_count += 1
        print(f"  保存卡片 {card_id}: {filename}")
    
    def _save_metadata(self):
        """保存收集过程的元数据"""
        metadata_file = self.output_dir / "collection_metadata.json"
        metadata = {
            "total_samples": len(self.metadata),
            "total_cards": self.sample_count,
            "collection_date": datetime.now().isoformat(),
            "samples": self.metadata
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"元数据已保存到: {metadata_file}")

def main():
    """主函数"""
    print("=" * 60)
    print("商品卡片样本收集工具")
    print("=" * 60)
    
    try:
        # 创建样本收集器
        collector = SampleCollector()
        
        # 询问收集数量
        while True:
            try:
                num_samples = int(input("请输入要收集的样本数量 (默认10): ") or "10")
                if num_samples > 0:
                    break
                else:
                    print("请输入正整数")
            except ValueError:
                print("请输入有效的数字")
        
        # 开始收集
        collector.collect_from_screen(num_samples)
        
        print("\n" + "=" * 60)
        print("样本收集完成!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n收集过程被用户中断")
    except Exception as e:
        print(f"\n收集过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()