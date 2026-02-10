"""
validator.py
配置验证器
"""

import re
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse
import logging
from src.config.exceptions import ConfigValidationError

logger = logging.getLogger(__name__)

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_structure(config_dict: Dict[str, Any], 
                          template_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证配置结构与模板是否一致
        
        Args:
            config_dict: 待验证的配置字典
            template_dict: 模板配置字典
            
        Returns:
            (是否一致, 错误信息列表)
        """
        errors = []
        
        def _compare_dicts(config: Dict, template: Dict, path: str = ""):
            for key, template_value in template.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in config:
                    errors.append(f"缺少必需字段: {current_path}")
                    continue
                
                config_value = config[key]
                
                if isinstance(template_value, dict):
                    if not isinstance(config_value, dict):
                        errors.append(f"字段类型不匹配: {current_path} 应为字典")
                    else:
                        _compare_dicts(config_value, template_value, current_path)
                elif isinstance(template_value, list):
                    if not isinstance(config_value, list):
                        errors.append(f"字段类型不匹配: {current_path} 应为列表")
        
        _compare_dicts(config_dict, template_dict)
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    @staticmethod
    def validate_time(time_str: str) -> bool:
        """验证时间格式 (HH:MM)"""
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
        return bool(re.match(pattern, time_str))
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_log_level(level: str) -> bool:
        """验证日志级别"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        return level.upper() in valid_levels
    
    @staticmethod
    def validate_schema(config_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证配置数据模式
        
        Args:
            config_dict: 配置字典
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 验证数据库配置
        db_config = config_dict.get('database', {})
        if db_config.get('type') != 'sqlite':
            if not db_config.get('host'):
                errors.append("数据库主机地址未设置")
            if not db_config.get('name'):
                errors.append("数据库名称未设置")
        
        # 验证时间格式
        scheduler_config = config_dict.get('scheduler', {})
        for time_str in scheduler_config.get('execution_times', []):
            if not ConfigValidator.validate_time(time_str):
                errors.append(f"时间格式无效: {time_str}，应为 HH:MM 格式")
        
        # 验证代理URL
        proxy = config_dict.get('browser', {}).get('network', {}).get('proxy')
        if proxy and not ConfigValidator.validate_url(proxy):
            errors.append(f"代理URL格式无效: {proxy}")
        
        # 验证邮箱
        email = config_dict.get('monitoring', {}).get('error_notification', {}).get('email')
        if email and not ConfigValidator.validate_email(email):
            errors.append(f"邮箱格式无效: {email}")
        
        # 验证日志级别
        log_level = config_dict.get('monitoring', {}).get('log_level')
        if log_level and not ConfigValidator.validate_log_level(log_level):
            errors.append(f"日志级别无效: {log_level}")
        
        return len(errors) == 0, errors