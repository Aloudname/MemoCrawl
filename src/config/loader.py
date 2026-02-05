"""
loader.py
配置加载器，支持多种格式
"""

import json
import yaml
import os
import toml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置字典
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的格式
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        
        # 根据扩展名选择加载方式
        suffix = path.suffix.lower()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if suffix == '.json':
                    return json.load(f)
                elif suffix in ['.yaml', '.yml']:
                    return yaml.safe_load(f)
                elif suffix == '.toml':
                    return toml.load(f)
                else:
                    raise ValueError(f"不支持的配置文件格式: {suffix}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    @staticmethod
    def save_file(data: Dict[str, Any], file_path: Union[str, Path], format: str = 'yaml') -> None:
        """
        保存配置文件
        
        Args:
            data: 配置数据
            file_path: 保存路径
            format: 格式 (json, yaml, toml)
        """
        path = Path(file_path)
        
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            if format == 'json':
                json.dump(data, f, indent=2, ensure_ascii=False)
            elif format == 'yaml':
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            elif format == 'toml':
                toml.dump(data, f)
            else:
                raise ValueError(f"不支持的格式: {format}")
        
        logger.debug(f"配置已保存到: {file_path}")
    
    @staticmethod
    def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并两个配置字典
        
        Args:
            base: 基础配置
            override: 覆盖配置
            
        Returns:
            合并后的配置
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def load_multiple(files: List[Union[str, Path]]) -> Dict[str, Any]:
        """
        加载多个配置文件，后面的文件覆盖前面的
        
        Args:
            files: 配置文件列表
            
        Returns:
            合并后的配置
        """
        config = {}
        
        for file_path in files:
            if os.path.exists(file_path):
                file_config = ConfigLoader.load_file(file_path)
                config = ConfigLoader.merge_configs(config, file_config)
        
        return config


class EnvironmentLoader:
    """环境变量加载器"""
    
    def __init__(self, prefix: str = "PRICE_TRACKER_"):
        self.prefix = prefix
    
    def load_environment_variables(self) -> Dict[str, Any]:
        """
        加载环境变量到配置结构
        
        Returns:
            环境变量配置
        """
        env_config = {}
        
        # 遍历所有环境变量
        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                # 移除前缀并转换为嵌套字典结构
                config_key = key[len(self.prefix):].lower()
                
                # 将下划线分隔的键转换为嵌套字典
                keys = config_key.split('_')
                current = env_config
                
                for i, k in enumerate(keys[:-1]):
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                
                # 设置值
                current[keys[-1]] = self._parse_value(value)
        
        return env_config
    
    def _parse_value(self, value: str) -> Any:
        """解析环境变量值"""
        # 尝试解析为布尔值
        if value.lower() in ['true', 'yes', 'on', '1']:
            return True
        elif value.lower() in ['false', 'no', 'off', '0']:
            return False
        
        # 尝试解析为数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # 尝试解析为列表（逗号分隔）
        if ',' in value:
            return [self._parse_value(v.strip()) for v in value.split(',')]
        
        # 保持为字符串
        return value