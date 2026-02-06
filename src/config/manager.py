"""
manager.py
配置管理器主类
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime

from .exceptions import ConfigError, ConfigFileNotFoundError, ConfigValidationError
from .models import AppConfig, ConfigAccessor
from .loader import ConfigLoader
from .validator import ConfigValidator
from .template import ConfigTemplate

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    配置管理器
    负责加载、验证和管理配置
    """
    
    def __init__(self, 
                 config_path: Union[str, Path] = "config.yaml",
                 template_path: Union[str, Path] = "templates/config.yaml.template",
                 auto_create: bool = True,
                 strict_validation: bool = True):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
            template_path: 模板文件路径
            auto_create: 是否自动创建配置文件（如果不存在）
            strict_validation: 是否严格验证配置结构
        """
        self.config_path = Path(config_path)
        self.template_path = Path(template_path)
        self.strict_validation = strict_validation
        
        # 初始化组件
        self.loader = ConfigLoader()
        self.validator = ConfigValidator()
        self.template_manager = ConfigTemplate(self.template_path.parent)
        
        # 配置数据
        self._config: Optional[AppConfig] = None
        self._dict_config: Dict[str, Any] = {}
        self._accessor: Optional[ConfigAccessor] = None
        
        # 加载配置
        self._load_config(auto_create)
        
        # 创建访问器
        self._accessor = ConfigAccessor(self._dict_config)
        
        logger.info(f"配置管理器初始化完成，环境: {self._config.environment}")
    
    def _load_config(self, auto_create: bool) -> None:
        """加载配置"""
        # 1. 检查配置文件是否存在
        if not self.config_path.exists():
            if auto_create:
                self._create_config_from_template()
            else:
                raise ConfigFileNotFoundError(
                    f"配置文件不存在: {self.config_path}"
                )
        
        # 2. 加载配置文件
        try:
            self._dict_config = self.loader.load_file(self.config_path)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            if auto_create:
                self._create_config_from_template()
                self._dict_config = self.loader.load_file(self.config_path)
            else:
                raise
        
        # 3. 加载模板
        template_dict = self.template_manager.load_template()
        
        # 4. 验证配置结构
        if self.strict_validation:
            is_valid, errors = self.validator.validate_structure(
                self._dict_config, template_dict
            )
            if not is_valid:
                error_msg = "配置结构验证失败:\n" + "\n".join(f"  - {error}" for error in errors)
                logger.error(error_msg)
                raise ConfigValidationError(error_msg)
        
        # 5. 验证配置数据
        is_valid, errors = self.validator.validate_schema(self._dict_config)
        if not is_valid:
            error_msg = "配置数据验证失败:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)
        
        # 6. 转换为Pydantic模型
        try:
            self._config = AppConfig(**self._dict_config)
        except Exception as e:
            logger.error(f"配置数据转换失败: {e}")
            raise ConfigValidationError(f"配置数据格式错误: {e}")
    
    def _create_config_from_template(self) -> None:
        """从模板创建配置文件"""
        logger.info(f"配置文件不存在，从模板创建: {self.config_path}")
        
        # 确保目录存在
        self.loader.ensure_config_directory(self.config_path)
        
        # 从模板创建配置文件
        success = self.template_manager.create_config_from_template(
            self.config_path
        )
        
        if not success:
            raise ConfigError(f"无法从模板创建配置文件: {self.config_path}")
        
        logger.info(f"已创建配置文件，请编辑后重新运行程序")
        print(f"已创建配置文件: {self.config_path.absolute()}")
        print("请编辑配置文件并填写必要信息后再运行程序。")
        exit(0)
    
    @property
    def config(self) -> ConfigAccessor:
        """获取配置访问器（支持点号访问）"""
        if self._accessor is None:
            self._accessor = ConfigAccessor(self._dict_config)
        return self._accessor
    
    @property
    def dict_config(self) -> Dict[str, Any]:
        """获取字典形式的配置"""
        return self._dict_config.copy()
    
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
        value = self._dict_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any, save: bool = False) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键，支持点号分隔
            value: 配置值
            save: 是否立即保存
            
        Returns:
            是否成功
        """
        try:
            keys = key.split('.')
            current = self._dict_config
            
            # 导航到父级
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                elif not isinstance(current[k], dict):
                    # 如果当前值不是字典，则覆盖为字典
                    current[k] = {}
                current = current[k]
            
            # 设置值
            current[keys[-1]] = value
            
            # 更新Pydantic模型
            self._config = AppConfig(**self._dict_config)
            
            # 更新访问器
            self._accessor = ConfigAccessor(self._dict_config)
            
            # 保存配置
            if save:
                self.save()
            
            logger.debug(f"设置配置: {key} = {'***' if 'password' in key.lower() else value}")
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
            if backup and self.config_path.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = self.config_path.with_suffix(f".backup.{timestamp}")
                self.config_path.rename(backup_file)
                logger.debug(f"已创建备份: {backup_file}")
            
            # 转换为字典
            config_dict = self._config.dict(exclude_unset=True)
            
            # 保存到文件
            self.loader.save_yaml(config_dict, self.config_path)
            
            logger.info(f"配置已保存到: {self.config_path}")
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
            self._load_config(auto_create=False)
            self._accessor = ConfigAccessor(self._dict_config)
            logger.info("配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False
    
    def validate(self) -> Dict[str, Any]:
        """
        验证当前配置
        
        Returns:
            验证结果字典
        """
        # 验证结构
        template_dict = self.template_manager.load_template()
        struct_valid, struct_errors = self.validator.validate_structure(
            self._dict_config, template_dict
        )
        
        # 验证数据
        data_valid, data_errors = self.validator.validate_schema(self._dict_config)
        
        # Pydantic模型验证（如果存在）
        model_errors = []
        try:
            # 尝试重新创建模型来验证
            AppConfig(**self._dict_config)
        except Exception as e:
            model_errors.append(str(e))
        
        return {
            'is_valid': struct_valid and data_valid and len(model_errors) == 0,
            'structure_errors': struct_errors,
            'data_errors': data_errors,
            'model_errors': model_errors,
            'differences': self.template_manager.compare_with_template(
                self._dict_config, template_dict
            )
        }
    
    def get_safe_dict(self, hide_sensitive: bool = True) -> Dict[str, Any]:
        """
        获取安全的配置字典（隐藏敏感信息）
        
        Args:
            hide_sensitive: 是否隐藏敏感信息
            
        Returns:
            安全的配置字典
        """
        config_dict = self._config.dict()
        
        if hide_sensitive:
            # 隐藏敏感字段
            sensitive_fields = [
                'browser.jd_account.password',
                'database.password',
                'monitoring.error_notification.telegram_token',
            ]
            
            for field in sensitive_fields:
                keys = field.split('.')
                current = config_dict
                
                for i, k in enumerate(keys):
                    if k in current:
                        if i == len(keys) - 1:
                            current[k] = "***HIDDEN***"
                        else:
                            current = current[k]
        
        return config_dict
    
    def update(self, updates: Dict[str, Any], save: bool = False) -> bool:
        """
        批量更新配置
        
        Args:
            updates: 更新字典
            save: 是否立即保存
            
        Returns:
            是否成功
        """
        try:
            # 深度合并配置
            from .loader import ConfigLoader
            merged_dict = ConfigLoader.merge_configs(self._dict_config, updates)
            
            # 验证合并后的配置
            self._config = AppConfig(**merged_dict)
            self._dict_config = merged_dict
            self._accessor = ConfigAccessor(self._dict_config)
            
            if save:
                self.save()
            
            logger.info("配置已批量更新")
            return True
            
        except Exception as e:
            logger.error(f"批量更新配置失败: {e}")
            return False
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ConfigManager(config_path={self.config_path}, environment={self._config.environment})"


# 全局配置管理器实例
_global_config_manager = None

def init_config(config_file: str = "config.yaml",
                template_file: str = "templates/config.yaml.template",
                auto_create: bool = True) -> ConfigManager:
    """
    初始化全局配置管理器
    
    Args:
        config_file: 配置文件路径
        template_file: 模板文件路径
        auto_create: 是否自动创建配置文件
        
    Returns:
        ConfigManager实例
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(
            config_path=config_file,
            template_path=template_file,
            auto_create=auto_create
        )
    
    return _global_config_manager

def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Returns:
        ConfigManager实例
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        raise ConfigError("配置管理器未初始化，请先调用 init_config()")
    
    return _global_config_manager

def get_config() -> ConfigAccessor:
    """
    获取配置访问器
    
    Returns:
        ConfigAccessor实例
    """
    return get_config_manager().config

def get_dict_config() -> Dict[str, Any]:
    """
    获取字典形式的配置
    
    Returns:
        配置字典
    """
    return get_config_manager().dict_config