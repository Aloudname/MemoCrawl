"""
配置模块
提供统一的配置管理接口
"""

from .manager import ConfigManager, get_config, init_config
from .models import (
    AppConfig,
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
from .validator import ConfigValidator
from .loader import ConfigLoader
from .encryption import ConfigEncryptor, SimpleEncryptor

__version__ = "1.0.0"

__all__ = [
    # 主类
    'ConfigManager',
    'get_config',
    'init_config',
    
    # 数据模型
    'AppConfig',
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
    
    # 工具类
    'ConfigValidator',
    'ConfigLoader',
    'ConfigEncryptor',
    'SimpleEncryptor',
]