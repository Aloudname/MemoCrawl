"""
配置模块
提供统一的配置管理接口
"""

from src.config.manager import (
    ConfigManager,
    init_config,
    get_config_manager,
    get_config,
    get_dict_config
)

from src.config.models import (
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

from src.config.exceptions import (
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