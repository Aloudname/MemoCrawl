"""
manager.py
配置管理器主类
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime

from src.config.models import AppConfig
from src.config.loader import ConfigLoader, EnvironmentLoader
from src.config.validator import ConfigValidator
from src.config.encryption import SimpleEncryptor

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    配置管理器
    负责加载、验证、管理和提供配置
    """
    
    # 敏感字段（需要加密）
    SENSITIVE_FIELDS = [
        'browser.jd_account.password',
        'database.password',
        'monitoring.error_notification.telegram_token',
    ]
    
    def __init__(self, 
                 config_file: Union[str, Path] = "config.yaml",
                 env_prefix: str = "PRICE_TRACKER_",
                 auto_save: bool = True):
        """
        初始化配置管理器
        
        Args:
            config_file: 主配置文件路径
            env_prefix: 环境变量前缀
            auto_save: 是否自动保存修改
        """
        self.config_file = Path(config_file)
        self.env_prefix = env_prefix
        self.auto_save = auto_save
        
        # 初始化组件
        self.loader = ConfigLoader()
        self.env_loader = EnvironmentLoader(prefix=env_prefix)
        self.validator = ConfigValidator()
        self.encryptor = SimpleEncryptor()
        
        # 加载配置
        self.config = self._load_config()   
        logger.info(f"配置管理器初始化完成，环境: {self.config.environment}")
    
    def _load_config(self) -> AppConfig:
        """加载配置"""
        config_dict = {}
        
        # 1. 加载默认配置
        default_config = AppConfig()
        config_dict = default_config.to_dict()
        
        # 2. 加载配置文件（如果存在）
        if self.config_file.exists():
            try:
                file_config = self.loader.load_file(self.config_file)
                config_dict = self.loader.merge_configs(config_dict, file_config)
                
                # 解密敏感字段
                config_dict = self._decrypt_sensitive_fields(config_dict)
                
                logger.info(f"已加载配置文件: {self.config_file}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
        
        # 3. 加载环境变量
        env_config = self.env_loader.load_environment_variables()
        if env_config:
            config_dict = self.loader.merge_configs(config_dict, env_config)
            logger.debug("已应用环境变量配置")
        
        # 4. 创建配置对象
        config_obj = AppConfig.from_dict(config_dict)
        # 5. 验证配置
        is_valid, errors, warnings = self.validator.validate(config_obj.to_dict())
        
        if warnings:
            for warning in warnings:
                logger.warning(f"配置警告: {warning}")
        
        if not is_valid:
            error_msg = "配置验证失败:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error(error_msg)
            
            # 如果配置无效，尝试使用默认值修复
            if self._try_fix_config(config_obj, errors):
                logger.warning("已尝试自动修复配置问题")
            else:
                raise ValueError(error_msg)
        
        return config_obj
    
    def _decrypt_sensitive_fields(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """解密敏感字段"""
        result = config_dict.copy()
        
        for field in self.SENSITIVE_FIELDS:
            value = self._get_nested_value(result, field)
            if value and isinstance(value, str):
                try:
                    decrypted = self.encryptor.decrypt(value)
                    self._set_nested_value(result, field, decrypted)
                except Exception:
                    # 如果不是加密的字符串，保持原样
                    pass
        
        return result
    
    def _encrypt_sensitive_fields(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """加密敏感字段"""
        result = config_dict.copy()
        
        for field in self.SENSITIVE_FIELDS:
            value = self._get_nested_value(result, field)
            if value and isinstance(value, str):
                encrypted = self.encryptor.encrypt(value)
                self._set_nested_value(result, field, encrypted)
        
        return result
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """获取嵌套值"""
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def _set_nested_value(self, config: Dict[str, Any], key: str, value: Any) -> None:
        """设置嵌套值"""
        keys = key.split('.')
        current = config
        
        for i, k in enumerate(keys[:-1]):
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _try_fix_config(self, config: AppConfig, errors: List[str]) -> bool:
        """尝试修复配置问题"""
        fixed = False
        
        for error in errors:
            if "应为" in error and "类型" in error:
                # 尝试修复类型错误
                field_match = error.split("'")[1] if "'" in error else None
                if field_match:
                    # 这里可以添加特定的修复逻辑
                    pass
        
        return fixed
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = getattr(value, k)
            return value
        except AttributeError:
            return default
    
    def set(self, key: str, value: Any, encrypt: bool = False) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            encrypt: 是否加密（如果字段是敏感字段）
            
        Returns:
            是否成功
        """
        try:
            keys = key.split('.')
            obj = self.config
            
            # 导航到父对象
            for k in keys[:-1]:
                obj = getattr(obj, k)
            
            # 设置值
            setattr(obj, keys[-1], value)
            
            # 如果设置了自动保存，则保存配置
            if self.auto_save:
                self.save()
            
            logger.debug(f"设置配置: {key} = {'***' if encrypt else value}")
            return True
            
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
            return False
    
    def save(self, backup: bool = True) -> bool:
        """
        保存配置到文件
        
        Args:
            backup: 是否备份原文件
            
        Returns:
            是否成功
        """
        try:
            # 创建备份
            if backup and self.config_file.exists():
                backup_file = self.config_file.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                self.config_file.rename(backup_file)
                logger.debug(f"已创建备份: {backup_file}")
            
            # 转换为字典并加密敏感字段
            config_dict = self.config.to_dict()
            config_dict = self._encrypt_sensitive_fields(config_dict)
            
            # 保存到文件
            self.loader.save_file(config_dict, self.config_file, format='yaml')
            
            logger.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def reload(self) -> bool:
        """
        重新加载配置
        
        Returns:
            是否成功
        """
        try:
            new_config = self._load_config()
            self.config = new_config
            logger.info("配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        验证当前配置
        
        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        config_dict = self.config.to_dict()
        return self.validator.validate(config_dict)
    
    def create_template(self, output_file: Union[str, Path], include_comments: bool = True) -> bool:
        """
        创建配置模板
        
        Args:
            output_file: 输出文件路径
            include_comments: 是否包含注释
            
        Returns:
            是否成功
        """
        try:
            template = self.config.to_dict()
            
            # 清空敏感信息和个性化设置
            template['jd_account']['username'] = ""
            template['jd_account']['password'] = ""
            template['database']['password'] = ""
            template['monitoring']['error_notification']['telegram_token'] = ""
            
            # 添加注释（YAML格式）
            if include_comments and str(output_file).endswith(('.yaml', '.yml')):
                template = self._add_yaml_comments(template)
            
            # 保存模板
            self.loader.save_file(template, output_file, format='yaml')
            
            logger.info(f"配置模板已创建: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"创建配置模板失败: {e}")
            return False
    
    def _add_yaml_comments(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """为YAML配置添加注释"""
        # 这里可以添加详细的注释
        # 由于YAML不支持在保存时添加注释，我们可以返回一个带注释的字符串
        # 简化处理：在manager.py中创建完整的带注释模板
        
        # 实际实现中，可以读取模板文件或硬编码注释
        return config_dict
    
    def get_all(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        获取所有配置
        
        Args:
            include_sensitive: 是否包含敏感信息
            
        Returns:
            所有配置的字典
        """
        config_dict = self.config.to_dict()
        
        if not include_sensitive:
            # 隐藏敏感信息
            for field in self.SENSITIVE_FIELDS:
                if self._get_nested_value(config_dict, field):
                    self._set_nested_value(config_dict, field, "***HIDDEN***")
        
        return config_dict
    
    def update_from_dict(self, updates: Dict[str, Any]) -> bool:
        """
        从字典批量更新配置
        
        Args:
            updates: 更新字典
            
        Returns:
            是否成功
        """
        try:
            # 深度合并配置
            current_dict = self.config.to_dict()
            updated_dict = self.loader.merge_configs(current_dict, updates)
            
            # 验证更新后的配置
            is_valid, errors, warnings = self.validator.validate(updated_dict)
            if not is_valid:
                logger.error(f"更新配置验证失败: {errors}")
                return False
            
            # 应用更新
            self.config = AppConfig.from_dict(updated_dict)
            
            if self.auto_save:
                self.save()
            
            logger.info("配置已批量更新")
            return True
            
        except Exception as e:
            logger.error(f"批量更新配置失败: {e}")
            return False


# 全局配置实例（单例模式）
_global_config = None

def get_config(config_file: str = "config.yaml") -> ConfigManager:
    """
    获取全局配置管理器实例（单例）
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        ConfigManager实例
    """
    global _global_config
    
    if _global_config is None:
        _global_config = ConfigManager(config_file)
    
    return _global_config


def init_config(config_file: str = "config.yaml", create_template: bool = False) -> ConfigManager:
    """
    初始化配置
    
    Args:
        config_file: 配置文件路径
        create_template: 如果配置文件不存在，是否创建模板
        
    Returns:
        ConfigManager实例
    """
    global _global_config
    
    config_path = Path(config_file)
    
    # 如果配置文件不存在且需要创建模板
    if not config_path.exists() and create_template:
        config_dir = config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建默认配置
        default_config = AppConfig()
        config_dict = default_config.to_dict()
        
        # 保存模板
        loader = ConfigLoader()
        loader.save_file(config_dict, config_path, format='yaml')
        
        print(f"已创建配置文件模板: {config_file}")
        print("请编辑配置文件并填写必要信息后再运行程序。")
        exit(0)
    
    _global_config = ConfigManager(config_file)
    return _global_config