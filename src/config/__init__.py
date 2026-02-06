"""
配置模块
提供统一的配置管理接口
"""

from typing import Any, Dict

from .manager import (
    ConfigManager,
    init_config,
    get_config_manager,
    get_config,
    get_dict_config
)

from .models import (
    AppConfig,
    ConfigAccessor,
    HumanSimulatorConfig,
    BrowserConfig,
    JDAccountConfig,
    SearchConfig,
    VisionConfig,
    DatabaseConfig,
    SchedulerConfig,
    MonitoringConfig,
    AntiDetectionConfig,
    PriceAlertConfig,
    LoginMethod,
    DatabaseType,
    SortMethod
)

from .exceptions import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    ConfigTemplateError,
    ConfigEncryptionError
)

__version__ = "2.0.0"

__all__ = [
    # 管理器
    'ConfigManager',
    'init_config',
    'get_config_manager',
    'get_config',
    'get_dict_config',
    
    # 数据模型
    'AppConfig',
    'ConfigAccessor',
    'HumanSimulatorConfig',
    'BrowserConfig',
    'JDAccountConfig',
    'SearchConfig',
    'VisionConfig',
    'DatabaseConfig',
    'SchedulerConfig',
    'MonitoringConfig',
    'AntiDetectionConfig',
    'PriceAlertConfig',
    
    # 枚举
    'LoginMethod',
    'DatabaseType',
    'SortMethod',
    
    # 异常
    'ConfigError',
    'ConfigFileNotFoundError',
    'ConfigValidationError',
    'ConfigTemplateError',
    'ConfigEncryptionError',
]

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
