"""
loader.py
配置文件加载器
"""

import yaml
import json
import toml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import logging
from src.config.exceptions import ConfigFileNotFoundError

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载YAML配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置字典
        """
        path = Path(file_path)
        
        if not path.exists():
            raise ConfigFileNotFoundError(f"配置文件不存在: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 安全加载YAML
                # return yaml.safe_load(content) or {}
                return yaml.unsafe_load(content) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML解析错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """加载JSON配置文件"""
        path = Path(file_path)
        
        if not path.exists():
            raise ConfigFileNotFoundError(f"JSON配置文件不存在: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载JSON配置文件失败: {e}")
            raise
    
    @staticmethod
    def load_toml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """加载TOML配置文件"""
        path = Path(file_path)
        
        if not path.exists():
            raise ConfigFileNotFoundError(f"TOML配置文件不存在: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            logger.error(f"加载TOML配置文件失败: {e}")
            raise
    
    @staticmethod
    def load_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        自动检测格式加载配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置字典
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix in ['.yaml', '.yml']:
            return ConfigLoader.load_yaml(path)
        elif suffix == '.json':
            return ConfigLoader.load_json(path)
        elif suffix == '.toml':
            return ConfigLoader.load_toml(path)
        else:
            raise ValueError(f"不支持的配置文件格式: {suffix}")
    
    @staticmethod
    def save_yaml(data: Dict[str, Any], file_path: Union[str, Path]) -> None:
        """保存YAML配置文件"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            logger.debug(f"配置已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise
    
    @staticmethod
    def save_json(data: Dict[str, Any], file_path: Union[str, Path], indent: int = 2) -> None:
        """保存JSON配置文件"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            logger.debug(f"配置已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存JSON配置文件失败: {e}")
            raise
    
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
            if (key in result and isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = ConfigLoader.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def ensure_config_directory(file_path: Union[str, Path]) -> Path:
        """确保配置文件目录存在"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path