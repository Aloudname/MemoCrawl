
"""
总控程序, run this
"""

from datetime import datetime
import os, sys, logging, argparse
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))


from src.config.manager import init_config, get_config
init_config()
config = get_config()

def setup_logging():
    """设置日志"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"MemoCrawl_{datetime.now().strftime('%Y%m%d')}.log")
    
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
    parser.add_argument('--mode', '-m', choices=['run', 'web', 'process', 'test'], 
                       default='web', help='运行模式')
    
    args = parser.parse_args()
    logger = setup_logging()
    
    try:
        if args.mode == 'web':
            # 仅启动Web界面
            from src.database.web_app import app
            logger.info(f"启动Web界面，端口: {config.database.port}")
            app.run(host='0.0.0.0', port=config.database.port, debug=False)
            
        elif args.mode == 'process':
            # 仅处理CSV文件
            if not config.data_processing.csv_path or not os.path.exists(config.data_processing.csv_path):
                logger.error("请提供有效的CSV文件路径")
                return
            
            from src.modules.data_processor import CSVDataProcessor
            CSVDataProcessor = CSVDataProcessor(config)
            result = CSVDataProcessor.import2db(config.data_processing.csv_path, "内存条")
            logger.info(f"CSV处理结果: {result}")
            
        elif args.mode == 'test':
            # 测试模式
            logger.info("开始测试...")
            
            # 测试数据库连接
            from src.database.database import ProductDatabase
            init_config()
            ProductDatabase = ProductDatabase(get_config())
            stats = ProductDatabase.get_stats()
            logger.info(f"数据库统计: {stats}")
            ProductDatabase.close()
            
            # 测试数据处理器
            from src.modules.data_processor import CSVDataProcessor
            CSVDataProcessor = CSVDataProcessor(config)
            
            # 如果有测试CSV文件
            test_csv = config.data_processing.csv_path
            if test_csv and os.path.exists(test_csv):
                result = CSVDataProcessor.import2db(test_csv, "内存条")
                logger.info(f"测试导入结果: {result}")
            
            logger.info("测试完成")
            
        else:  # run模式
            # 启动完整系统
            from src.modules.main_controller import MainController
            controller = MainController()
            logger.info("MemoCrawl 系统启动")
            
            # 启动Web界面
            controller.start_web(config.database.port)
            
            # 启动定时任务
            if config.mainC.schedule.enabled:
                controller.do_Schedule()
            else:
                # 运行一次自动化任务
                logger.info("循环关闭, 执行一次自动化任务...")
                success = controller.run_task()
                
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
