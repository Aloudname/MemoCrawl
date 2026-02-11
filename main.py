
"""
测试脚本 - 总控程序
"""
import sys
import os
import argparse
import logging
from datetime import datetime

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def setup_logging():
    """设置日志"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"memo_crawl_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MemoCrawl - 商品价格监控系统')
    parser.add_argument('--config', '-c', default='src/config/config.yaml', help='配置文件路径')
    parser.add_argument('--mode', '-m', choices=['run', 'web', 'process', 'test'], 
                       default='web', help='运行模式')
    parser.add_argument('--csv', type=str, help='CSV文件路径（process模式使用）')
    parser.add_argument('--port', '-p', type=int, default=5050, help='Web服务端口')
    parser.add_argument('--schedule', '-s', action='store_true', help='启动定时任务')
    parser.add_argument('--hour', type=int, default=9, help='定时任务执行小时')
    parser.add_argument('--minute', type=int, default=0, help='定时任务执行分钟')
    
    args = parser.parse_args()
    logger = setup_logging()
    
    try:
        if args.mode == 'web':
            # 仅启动Web界面
            from src.database.web_app import app
            logger.info(f"启动Web界面，端口: {args.port}")
            app.run(host='0.0.0.0', port=args.port, debug=False)
            
        elif args.mode == 'process':
            # 仅处理CSV文件
            if not args.csv or not os.path.exists(args.csv):
                logger.error("请提供有效的CSV文件路径")
                return
            
            from src.modules.data_processor import CSVDataProcessor
            processor = CSVDataProcessor("products.db")
            
            result = processor.import_csv_to_db(args.csv, "内存条")
            logger.info(f"CSV处理结果: {result}")
            
        elif args.mode == 'test':
            # 测试模式
            logger.info("开始测试...")
            
            # 测试数据库连接
            from src.database.database import ProductDatabase
            db = ProductDatabase("products.db")
            stats = db.get_statistics()
            logger.info(f"数据库统计: {stats}")
            db.close()
            
            # 测试数据处理器
            from src.modules.data_processor import CSVDataProcessor
            processor = CSVDataProcessor("products.db")
            
            # 如果有测试CSV文件
            test_csv = "data.csv" if os.path.exists("data.csv") else args.csv
            if test_csv and os.path.exists(test_csv):
                result = processor.import_csv_to_db(test_csv, "内存条")
                logger.info(f"测试导入结果: {result}")
            
            logger.info("测试完成")
            
        else:  # run模式
            # 启动完整系统
            from src.modules.main_controller import MainController
            
            controller = MainController(args.config)
            logger.info("MemoCrawl 系统启动")
            
            # 启动Web界面
            controller.start_web_interface(args.port)
            
            if args.schedule:
                # 启动定时任务
                controller.start_scheduled_task(args.hour, args.minute)
            else:
                # 运行一次自动化任务
                logger.info("开始运行自动化任务...")
                success = controller.run_automation_task()
                
                if success:
                    logger.info("自动化任务执行成功")
                else:
                    logger.error("自动化任务执行失败")
                
                # 显示状态
                status = controller.get_status()
                logger.info(f"系统状态: {status}")
                
                # 保持运行以提供Web服务
                import time
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    controller.stop()
                    
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()