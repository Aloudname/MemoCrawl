"""
main_controller.py
总控制器模块
整合自动化登录、数据采集、数据处理和数据库存储
"""

from datetime import datetime
from typing import Dict, Any, Optional
import os, time, schedule, threading, logging

from src.database.web_app import app
from src.modules.auto_browser import AutoBrowser
from src.database.database import ProductDatabase
from src.config.manager import init_config, get_config
from src.modules.data_processor import CSVDataProcessor


class MainController:
    """主控制器"""
    
    def __init__(self):
        """
        初始化主控制器
        """

        init_config()
        self.config = get_config()
        
        # 初始化模块
        self.auto_browser = None
        self.data_processor = None
        self.database = None
        
        # 运行状态
        self.is_running = False
        self.current_task = None
        
        # 初始化各模块
        if not self.__init_modules__():
            self.logger.error("模块初始化函数执行失败，程序退出")
            exit(1)
        
    def __init_modules__(self) -> bool:
        """初始化所有模块"""
        try:
            # 初始化数据库
            self.database = ProductDatabase(self.config)
            self.logger.info(f"数据库模块初始化成功: {self.database}")
            
            # 初始化浏览器自动化模块
            self.auto_browser = AutoBrowser(self.config)
            self.logger.info(f"浏览器自动化模块初始化成功: {self.auto_browser}")
            
            # 初始化数据处理器
            self.data_processor = CSVDataProcessor(self.config)
            self.logger.info(f"数据处理器初始化成功:{self.data_processor}")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化模块失败: {e}")
            return False
    
    def do_Crawl(self):
        """
        运行自动化任务
        包括：登录、搜索、导出CSV、导入数据库
        """
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger.info(f"开始自动化任务: {task_id}")
        
        try:
            self.logger.info("开始执行自动化流程...")
            success = self.auto_browser.envisit()
            
            if not success:
                self.logger.error("自动化流程执行失败")
                return False
            
            self.logger.info("自动化流程执行成功，CSV文件已下载")
            
            # 处理CSV数据并导入数据库
            processing_config = self.config.data_processing
            csv_path = processing_config.csv_path
            category = processing_config.default_category
            
            if os.path.exists(csv_path):
                self.logger.info(f"开始处理CSV文件: {csv_path}")
                result = self.data_processor.import2db(csv_path, category)
                
                if result['success']:
                    self.logger.info(f"数据导入成功: {result['message']}")
                    
                    # 清理旧文件
                    if processing_config.cleanup_old_files:
                        keep_files = processing_config.keep_latest_files
                        self.data_processor.cleanup_old_csv(
                            csv_path.replace('data.csv', 'data_*.csv'),
                            keep_files
                        )
                else:
                    self.logger.error(f"数据导入失败: {result['message']}")
            else:
                self.logger.warning(f"CSV文件不存在: {csv_path}")
            
            # 关闭浏览器
            if self.auto_browser:
                self.auto_browser.devisit()
                self.auto_browser = None
            
            self.logger.info(f"自动化任务完成: {task_id}")
            return True
                
        except Exception as e:
            self.logger.error(f"自动化任务执行失败: {e}")
            if self.auto_browser:
                self.auto_browser.devisit()
            return False
    
    def do_Schedule(self):
        """
        启动定时任务
        
        Args:
            hour: 执行小时
            minute: 执行分钟
        """
        self.is_running = True
        hour = self.config.mainC.schedule.hour
        minute = self.config.mainC.schedule.minute
        
        # 设置定时任务
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(self.run_task)
        
        # 可选, 立即运行一次
        if self.config.mainC.schedule.run_on_start:
            self.run_task()
        
        self.logger.info(f"定时任务已启动，每天 {hour:02d}:{minute:02d} 执行")
        
        # 运行调度循环
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                self.logger.info("接收到中断信号，停止定时任务")
                break
            except Exception as e:
                self.logger.error(f"定时任务循环错误: {e}")
                time.sleep(300)  # 出错后等待5分钟
    
    def run_task(self):
        """在新线程定时执行任务"""
        # 在新线程中执行Crawl任务
        self.logger.info("开始执行定时任务")
        task_thread = threading.Thread(target=self.do_Crawl)
        task_thread.daemon = True
        task_thread.start()
        self.current_task = task_thread
        
        self.logger.info("定时任务已提交到后台执行")
    
    def stop(self):
        """停止控制器"""
        self.is_running = False
        self.logger.info("控制器正在停止...")
        
        # 等待当前任务完成
        if self.current_task and self.current_task.is_alive():
            self.logger.info("等待当前任务完成...")
            self.current_task.join(timeout=30)
        
        # 关闭浏览器
        if self.auto_browser:
            try:
                self.auto_browser.devisit()
            except:
                pass
        
        # 关闭数据库
        if self.database:
            try:
                self.database.close()
            except:
                pass
        self.logger.info("控制器已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        db_stats = self.database.get_stats() if self.database else {}
        
        return {
            'status': 'running' if self.is_running else 'stopped',
            'current_task': 'running' if (self.current_task and self.current_task.is_alive()) else 'idle',
            'database_stats': db_stats,
            'last_run': self.get_last_run(),
            'next_run': schedule.next_run() if schedule.jobs else None
        }
    
    def get_last_run(self) -> Optional[str]:
        """获取上次运行时间"""
        # 从日志/数据库中获取
        try:
            with open(self.config.mainC.save_as, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines[-100:]):  # 检查最后100行
                    if '自动化任务完成' in line:
                        return line.split(' - ')[0]
        except:
            pass
        return None
    
    def start_web(self, port: int = 5050):
        """启动Web界面"""
        try:
            def run_web():
                app.run(host='0.0.0.0', port=port, debug=False)
            
            web_thread = threading.Thread(target=run_web)
            web_thread.daemon = True
            web_thread.start()
            
            self.logger.info(f"Web界面已启动: http://localhost:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动Web界面失败: {e}")
            return False

if __name__ == "__main__":
    # 测试主控制器
    controller = MainController()
    
    try:
        # 启动Web界面
        controller.start_web(5050)
        
        # 运行一次自动化任务
        controller.do_Crawl()
        
        # # 或者启动定时任务
        # controller.do_Schedule(hour=9, minute=0)
        
    except KeyboardInterrupt:
        controller.stop()