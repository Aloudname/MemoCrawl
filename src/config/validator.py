"""
validator.py
配置验证器
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import ipaddress
from urllib.parse import urlparse
import yaml
import logging

logger = logging.getLogger(__name__)

class ConfigValidator:
    """配置验证器"""
    
    # 验证列表
    VALIDATION_RULES = {
        'human_simulator.min_delay': {'type': float, 'min': 0.01, 'max': 5.0},
        'human_simulator.max_delay': {'type': float, 'min': 0.01, 'max': 5.0},
        'human_simulator.think_time_min': {'type': float, 'min': 0.01, 'max': 10.0},
        'human_simulator.think_time_max': {'type': float, 'min': 0.01, 'max': 10.0},
        'human_simulator.speed_min': {'type': float, 'min': 0.1, 'max': 5.0},
        'human_simulator.speed_max': {'type': float, 'min': 0.1, 'max': 5.0},
        'human_simulator.curve_factor': {'type': float, 'min': 0.0, 'max': 1.0},
        'human_simulator.jitter_factor': {'type': float, 'min': 0.0, 'max': 1.0},
        'human_simulator.error_probability': {'type': float, 'min': 0.0, 'max': 0.5},
        'human_simulator.error_correction_probability': {'type': float, 'min': 0.0, 'max': 1.0},
        
        'browser.physical.window_width': {'type': int, 'min': 800, 'max': 4096},
        'browser.physical.window_height': {'type': int, 'min': 600, 'max': 2160},
        
        'browser.network.headless': {'type': bool},
        'browser.network.disable_images': {'type': bool},
        'browser.network.max_login_attempts': {'type': int, 'min': 1, 'max': 10},
        'browser.network.login_timeout': {'type': int, 'min': 10, 'max': 300},
        'browser.network.cookies_expiry_days': {'type': int, 'min': 1, 'max': 30},
        
        'search.max_pages': {'type': int, 'min': 1, 'max': 100},
        'search.scroll_pause': {'type': float, 'min': 0.1, 'max': 10.0},
        'search.items_per_page': {'type': int, 'min': 10, 'max': 100},
        
        'vision.match_threshold': {'type': float, 'min': 0.1, 'max': 1.0},
        'vision.preprocessing.resize_factor': {'type': float, 'min': 0.5, 'max': 4.0},
        
        'database.backup_days': {'type': int, 'min': 1, 'max': 365},
        'database.connection_pool_size': {'type': int, 'min': 1, 'max': 50},
        
        'scheduler.max_runtime': {'type': int, 'min': 60, 'max': 86400},
        'scheduler.retry_attempts': {'type': int, 'min': 0, 'max': 10},
        'scheduler.retry_delay': {'type': int, 'min': 10, 'max': 3600},
        
        'price_alert.check_interval': {'type': int, 'min': 60, 'max': 86400},
        'price_alert.drop_threshold': {'type': float, 'min': 0.0, 'max': 1.0},
        'price_alert.rise_threshold': {'type': float, 'min': 0.0, 'max': 1.0},
    }
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        self.errors = []
        self.warnings = []
        
        # 验证所有规则
        self._validate_rules(config)
        
        # 自定义验证
        self._validate_custom(config)
        
        # 检查必需字段
        self._validate_required_fields(config)
        
        # 验证逻辑关系
        self._validate_logic(config)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_rules(self, config: Dict[str, Any], prefix: str = "") -> None:
        """根据规则验证配置"""
        for key, rule in self.VALIDATION_RULES.items():
            value = self._get_nested_value(config, key)
            
            if value is None:
                continue  # 字段不存在，跳过验证
            
            # 类型验证
            expected_type = rule.get('type')
            if expected_type and not isinstance(value, expected_type):
                self.errors.append(f"字段 '{key}' 应为 {expected_type.__name__} 类型，实际为 {type(value).__name__}")
                continue
            
            # 最小值验证
            if 'min' in rule and value < rule['min']:
                self.errors.append(f"字段 '{key}' 值 {value} 小于最小值 {rule['min']}")
            
            # 最大值验证
            if 'max' in rule and value > rule['max']:
                self.errors.append(f"字段 '{key}' 值 {value} 大于最大值 {rule['max']}")
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """获取嵌套字典的值"""
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def _validate_custom(self, config: Dict[str, Any]) -> None:
        """自定义验证规则"""
        # 验证邮箱格式
        if config.get('monitoring', {}).get('error_notification', {}).get('email'):
            email = config['monitoring']['error_notification']['email']
            if not self._is_valid_email(email):
                self.warnings.append(f"邮箱格式可能无效: {email}")
        
        # 验证URL格式
        if config.get('browser', {}).get('proxy'):
            proxy = config['browser']['proxy']
            if not self._is_valid_url(proxy):
                self.errors.append(f"代理URL格式无效: {proxy}")
        
        # 验证时间格式
        if config.get('scheduler', {}).get('execution_times'):
            times = config['scheduler']['execution_times']
            for time_str in times:
                if not self._is_valid_time(time_str):
                    self.errors.append(f"时间格式无效: {time_str}，应为 HH:MM 格式")
        
        # 验证数据库连接
        if config.get('database', {}).get('type') != 'sqlite':
            db_config = config['database']
            if not db_config.get('host'):
                self.errors.append("数据库主机地址未设置")
            if not db_config.get('name'):
                self.errors.append("数据库名称未设置")
    
    def _validate_required_fields(self, config: Dict[str, Any]) -> None:
        """验证必需字段"""
        required_fields = [
            # 'browser.jd_account.username',
            # 'browser.jd_account.password',
        ]
        
        for field in required_fields:
            value = self._get_nested_value(config, field)
            print(f"必需字段 '{field}' = {value}")
            if not value:
                print(f"必需字段 '{field}' 未设置")
                self.errors.append(f"必需字段 '{field}' 未设置")
    
    def _validate_logic(self, config: Dict[str, Any]) -> None:
        """验证逻辑关系"""
        # 验证最小延迟小于最大延迟
        min_delay = config.get('human_simulator', {}).get('min_delay')
        max_delay = config.get('human_simulator', {}).get('max_delay')
        
        if min_delay and max_delay and min_delay > max_delay:
            self.errors.append(f"最小延迟 {min_delay} 不能大于最大延迟 {max_delay}")
        
        # 验证思考时间范围
        think_min = config.get('human_simulator', {}).get('think_time_min')
        think_max = config.get('human_simulator', {}).get('think_time_max')
        
        if think_min and think_max and think_min > think_max:
            self.errors.append(f"最小思考时间 {think_min} 不能大于最大思考时间 {think_max}")
        
        # 验证速度范围
        speed_min = config.get('human_simulator', {}).get('speed_min')
        speed_max = config.get('human_simulator', {}).get('speed_max')
        
        if speed_min and speed_max and speed_min > speed_max:
            self.errors.append(f"最小速度 {speed_min} 不能大于最大速度 {speed_max}")
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    @staticmethod
    def _is_valid_time(time_str: str) -> bool:
        """验证时间格式 (HH:MM)"""
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
        return bool(re.match(pattern, time_str))