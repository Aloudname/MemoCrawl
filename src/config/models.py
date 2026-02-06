"""
models.py
配置数据模型定义（基于Pydantic）
"""

from pydantic import BaseModel, Field, field_validator, SecretStr
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import os

# 枚举类型保持不变...
class LoginMethod(str, Enum):
    PASSWORD = "password"
    QR_CODE = "qr_code"
    SMS = "sms"

class DatabaseType(str, Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"

class SortMethod(str, Enum):
    DEFAULT = "default"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    SALES = "sales"

# 嵌套配置模型
class HumanSimulatorConfig(BaseModel):
    """人类行为模拟配置"""
    min_delay: float = Field(0.1, ge=0.01, le=5.0)
    max_delay: float = Field(0.5, ge=0.01, le=5.0)
    think_time_min: float = Field(0.2, ge=0.01, le=10.0)
    think_time_max: float = Field(1.0, ge=0.01, le=10.0)
    speed_min: float = Field(0.3, ge=0.1, le=5.0)
    speed_max: float = Field(0.8, ge=0.1, le=5.0)
    curve_factor: float = Field(0.3, ge=0.0, le=1.0)
    jitter_factor: float = Field(0.05, ge=0.0, le=1.0)
    error_probability: float = Field(0.01, ge=0.0, le=0.5)
    error_correction_probability: float = Field(0.8, ge=0.0, le=1.0)

    @field_validator('max_delay')
    def max_greater_than_min_delay(cls, v, values):
        if 'min_delay' in values and v <= values['min_delay']:
            raise ValueError('max_delay必须大于min_delay')
        return v

    @field_validator('think_time_max')
    def think_max_greater_than_min(cls, v, values):
        if 'think_time_min' in values and v <= values['think_time_min']:
            raise ValueError('think_time_max必须大于think_time_min')
        return v

    @field_validator('speed_max')
    def speed_max_greater_than_min(cls, v, values):
        if 'speed_min' in values and v <= values['speed_min']:
            raise ValueError('speed_max必须大于speed_min')
        return v

class JDAccountConfig(BaseModel):
    """京东账户配置"""
    username: str = ""
    password: SecretStr = SecretStr("")  # 使用SecretStr保护密码
    login_method: LoginMethod = LoginMethod.PASSWORD
    max_login_attempts: int = Field(3, ge=1, le=10)
    login_timeout: int = Field(60, ge=10, le=300)
    save_cookies: bool = True
    cookies_expiry_days: int = Field(7, ge=1, le=30)

class NetworkConfig(BaseModel):
    """网络配置"""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    headless: bool = False
    disable_images: bool = True
    proxy: Optional[str] = None
    user_data_dir: Optional[str] = None
    
    @field_validator('proxy')
    def validate_proxy(cls, v):
        if v and not v.startswith(('http://', 'https://', 'socks5://')):
            raise ValueError('代理格式不正确，应为http://, https://或socks5://开头')
        return v

class BrowserConfig(BaseModel):
    """浏览器配置"""
    chrome_path: Optional[str] = None
    window_width: int = Field(1366, ge=800, le=4096)
    window_height: int = Field(768, ge=600, le=2160)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    jd_account: JDAccountConfig = Field(default_factory=JDAccountConfig)

# 其他模型类似地转换为Pydantic BaseModel...
# 这里只展示关键部分，其他模型转换方式相同

class FilterConditions(BaseModel):
    """筛选条件配置"""
    brands: List[str] = []
    price_range: Tuple[float, float] = (0, 9999)
    seller_type: str = "all"
    min_rating: float = Field(0.0, ge=0.0, le=5.0)
    min_sales: int = Field(0, ge=0)

class SearchConfig(BaseModel):
    """搜索配置"""
    keywords: List[str] = ["ddr4内存 笔记本电脑组件 32G"]
    max_pages: int = Field(3, ge=1, le=100)
    scroll_pause: float = Field(1.0, ge=0.1, le=10.0)
    items_per_page: int = Field(30, ge=10, le=100)
    sort_method: SortMethod = SortMethod.DEFAULT
    filter_conditions: FilterConditions = Field(default_factory=FilterConditions)
    smart_scroll: bool = True

class VisionPreprocessingConfig(BaseModel):
    """视觉预处理配置"""
    denoise: bool = True
    binarization: bool = True
    contrast_enhance: bool = True
    resize_factor: float = Field(2.0, ge=0.5, le=4.0)

class VisionConfig(BaseModel):
    """视觉识别配置"""
    templates_dir: str = "templates"
    match_threshold: float = Field(0.8, ge=0.1, le=1.0)
    ocr_language: str = "chi_sim+eng"
    preprocessing: VisionPreprocessingConfig = Field(default_factory=VisionPreprocessingConfig)
    debug_save_images: bool = False
    debug_save_dir: str = "debug_images"

class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: DatabaseType = DatabaseType.SQLITE
    path: str = "data/price_data.db"
    host: str = "localhost"
    port: int = Field(3306, ge=1, le=65535)
    name: str = "price_tracker"
    user: str = ""
    password: SecretStr = SecretStr("")  # 使用SecretStr保护密码
    backup_days: int = Field(7, ge=1, le=365)
    auto_backup: bool = True
    backup_dir: str = "backups"
    connection_pool_size: int = Field(5, ge=1, le=50)

class ErrorNotificationConfig(BaseModel):
    """错误通知配置"""
    enabled: bool = False
    email: str = ""
    telegram_token: SecretStr = SecretStr("")  # 使用SecretStr保护令牌
    telegram_chat_id: str = ""
    webhook_url: str = ""
    notify_on_errors: List[str] = ["critical", "error"]

class MonitoringConfig(BaseModel):
    """监控配置"""
    log_level: str = "INFO"
    log_file: str = "logs/price_tracker.log"
    max_log_size: int = Field(10485760, ge=102400, le=1073741824)  # 100KB到1GB
    backup_count: int = Field(5, ge=1, le=100)
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    performance_monitoring: bool = True
    error_notification: ErrorNotificationConfig = Field(default_factory=ErrorNotificationConfig)

class RandomBehaviorConfig(BaseModel):
    """随机行为配置"""
    mouse_movement: bool = True
    click_offset: bool = True
    typing_speed_variation: bool = True
    idle_behavior: bool = True
    scroll_variation: bool = True

class IPRotationConfig(BaseModel):
    """IP轮换配置"""
    enabled: bool = False
    proxy_list: List[str] = []
    change_interval: int = Field(3600, ge=60, le=86400)
    proxy_type: str = "http"

class AntiDetectionConfig(BaseModel):
    """反检测配置"""
    rotate_user_agent: bool = True
    user_agents_pool: List[str] = []
    random_behavior: RandomBehaviorConfig = Field(default_factory=RandomBehaviorConfig)
    ip_rotation: IPRotationConfig = Field(default_factory=IPRotationConfig)
    mimic_human_pattern: bool = True

class PriceAlertConfig(BaseModel):
    """价格提醒配置"""
    enabled: bool = False
    check_interval: int = Field(3600, ge=60, le=86400)
    drop_threshold: float = Field(0.1, ge=0.0, le=1.0)
    rise_threshold: float = Field(0.2, ge=0.0, le=1.0)
    notification_methods: List[str] = ["console"]

class SchedulerConfig(BaseModel):
    """定时任务配置"""
    enabled: bool = True
    execution_times: List[str] = ["10:00", "16:00", "22:00"]
    max_runtime: int = Field(1800, ge=60, le=86400)
    retry_attempts: int = Field(3, ge=0, le=10)
    retry_delay: int = Field(300, ge=10, le=3600)
    timezone: str = "Asia/Shanghai"
    
    @field_validator('execution_times')
    def validate_execution_times(cls, v):
        import re
        time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$')
        for time_str in v:
            if not time_pattern.match(time_str):
                raise ValueError(f'时间格式无效: {time_str}，应为 HH:MM 格式')
        return v

class AppConfig(BaseModel):
    """应用程序主配置"""
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    
    human_simulator: HumanSimulatorConfig = Field(default_factory=HumanSimulatorConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    anti_detection: AntiDetectionConfig = Field(default_factory=AntiDetectionConfig)
    price_alert: PriceAlertConfig = Field(default_factory=PriceAlertConfig)
    
    class Config:
        # 允许任意字段，但会验证已知字段
        extra = "ignore"
        
        # 自定义JSON编码
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None
        }

# 辅助类，用于简化嵌套访问
class ConfigAccessor:
    """配置访问器，支持点号访问"""
    
    def __init__(self, config_dict):
        self._config = config_dict
    
    def __getattr__(self, name):
        if name in self._config:
            value = self._config[name]
            if isinstance(value, dict):
                return ConfigAccessor(value)
            return value
        raise AttributeError(f"配置中没有属性 '{name}'")
    
    def __repr__(self):
        return f"ConfigAccessor({self._config})"