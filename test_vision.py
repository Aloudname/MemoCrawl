"""
测试视觉处理模块
"""

import numpy as np
import cv2, sys, logging
from pathlib import Path

from src.modules.vision_processor import VisionProcessor, CaptureMode, create_vision_processor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_capture_and_crop():
    """测试捕捉和裁剪功能"""
    print("=== 测试捕捉和裁剪功能 ===")
    
    try:
        # 创建视觉处理器
        processor = create_vision_processor()
        
        # 方法1: 完整流程（捕捉+裁剪）
        print("\n1. 执行完整视觉处理流程...")
        cards = processor.process()
        
        if cards:
            print(f"检测到 {len(cards)} 个商品卡片")
            for i, card in enumerate(cards):
                x1, y1, x2, y2 = card.bbox
                width = x2 - x1
                height = y2 - y1
                print(f"  卡片 {i+1}: 位置({x1}, {y1}, {x2}, {y2}), "
                      f"尺寸({width}x{height}), 置信度: {card.confidence:.2f}")
        else:
            print("未检测到商品卡片")
        
        # 获取统计信息
        stats = processor.get_stats()
        print(f"\n处理统计:")
        print(f"  已处理次数: {stats['processed_count']}")
        
        # 方法2: 处理已有图像
        print("\n2. 测试处理已有图像...")
        
        # 创建一个测试图像（模拟商品卡片）
        test_image = np.ones((800, 1200, 3), dtype=np.uint8) * 240
        
        # 在图像中添加一些模拟的商品卡片
        test_cards = [
            (100, 100, 400, 400),   # 卡片1
            (500, 100, 800, 400),   # 卡片2
            (100, 450, 400, 750),   # 卡片3
            (500, 450, 800, 750),   # 卡片4
        ]
        
        for i, (x1, y1, x2, y2) in enumerate(test_cards):
            # 绘制卡片背景（不同颜色）
            color = [
                (255, 200, 200),  # 浅红
                (200, 255, 200),  # 浅绿
                (200, 200, 255),  # 浅蓝
                (255, 255, 200),  # 浅黄
            ][i % 4]
            
            test_image[y1:y2, x1:x2] = color
            
            # 绘制卡片边框
            cv2.rectangle(test_image, (x1, y1), (x2, y2), (0, 0, 0), 2)
            
            # 添加卡片标签
            cv2.putText(test_image, f"Product {i+1}", (x1+10, y1+30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        # 处理测试图像
        cards_from_image = processor.process_image(test_image)
        
        if cards_from_image:
            print(f"从测试图像中检测到 {len(cards_from_image)} 个商品卡片")
            
            # 可视化结果
            vis_image = processor.visualize_results(test_image, cards_from_image)
            
            # 保存结果
            results = processor.save_results(test_image, cards_from_image, "test_results")
            print(f"结果已保存到: test_results/")
            
            # 显示图像（如果有GUI环境）
            try:
                cv2.imshow("检测结果", vis_image)
                cv2.waitKey(3000)
                cv2.destroyAllWindows()
            except:
                print("无法显示图像（可能是无GUI环境）")
         
        
        print("\n✅ 捕捉和裁剪测试完成!")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_with_real_screenshot():
    """使用真实屏幕截图测试"""
    print("\n=== 使用真实屏幕截图测试 ===")
    
    try:
        # 创建视觉处理器
        processor = create_vision_processor()
        
        # 修改配置，保存更多调试信息
        processor.capture_module.config.save_captures = True
        processor.crop_module.config.save_crops = True
        
        print("请打开一个包含商品卡片的网页（如京东搜索页面）")
        print("5秒后开始捕捉...")
        import time
        time.sleep(5)
        
        # 执行捕捉和裁剪
        cards = processor.process()
        
        if cards:
            print(f"\n✅ 成功检测到 {len(cards)} 个商品卡片!")
            
            # 显示检测到的卡片信息
            for i, card in enumerate(cards):
                x1, y1, x2, y2 = card.bbox
                width = x2 - x1
                height = y2 - y1
                aspect_ratio = width / height
                
                print(f"\n卡片 {i+1}:")
                print(f"  位置: ({x1}, {y1}) 到 ({x2}, {y2})")
                print(f"  尺寸: {width} x {height} (宽高比: {aspect_ratio:.2f})")
                print(f"  置信度: {card.confidence:.2f}")
                print(f"  检测方法: {card.features.get('method', 'unknown')}")
            
            # 保存详细结果
            print(f"\n详细结果已保存到 captures/ 和 crops/ 目录")
            
        else:
            print("\n❌ 未检测到商品卡片")
            print("可能的原因:")
            print("  1. 网页上可能没有明显的商品卡片")
            print("  2. 卡片尺寸或形状超出预设范围")
            print("  3. 需要调整检测参数")
            
            # 显示当前配置
            crop_config = processor.crop_module.config
            print(f"\n当前裁剪配置:")
            print(f"  最小卡片尺寸: {crop_config.min_card_width}x{crop_config.min_card_height}")
            print(f"  最大卡片尺寸: {crop_config.max_card_width}x{crop_config.max_card_height}")
            print(f"  宽高比范围: {crop_config.min_aspect_ratio:.1f} - {crop_config.max_aspect_ratio:.1f}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("=" * 60)
    print("视觉处理模块测试")
    print("=" * 60)
    
    try:
        # 测试基本功能
        test_capture_and_crop()
        
        # 询问是否进行真实截图测试
        response = input("\n是否进行真实屏幕截图测试？(y/n): ").strip().lower()
        if response == 'y':
            test_with_real_screenshot()
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()