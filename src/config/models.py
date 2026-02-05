"""
models.py
配置数据模型定义
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum

class LoginMethod(str, Enum):
    """登录方式枚举"""
    PASSWORD = "password"
    QR_CODE = "qr_code"
    SMS = "sms"

class DatabaseType(str, Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"

class SortMethod(str, Enum):
    """排序方式枚举"""
    DEFAULT = "default"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    SALES = "sales"

@dataclass
class HumanSimulatorConfig:
    """人类行为模拟配置"""
    min_delay: float = 0.1
    max_delay: float = 0.5
    think_time_min: float = 0.2
    think_time_max: float = 1.0
    speed_min: float = 0.3
    speed_max: float = 0.8
    curve_factor: float = 0.3
    jitter_factor: float = 0.05
    error_probability: float = 0.01
    error_correction_probability: float = 0.8

@dataclass
class BrowserConfig:
    """浏览器配置"""
    chrome_path: Optional[str] = None
    window_width: int = 1366
    window_height: int = 768
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    headless: bool = False
    disable_images: bool = True
    proxy: Optional[str] = None
    user_data_dir: Optional[str] = None  # 用户数据目录，用于保存cookies

@dataclass
class JDAccountConfig:
    """京东账户配置"""
    username: str = ""
    password: str = ""
    login_method: LoginMethod = LoginMethod.PASSWORD
    max_login_attempts: int = 3
    login_timeout: int = 60
    save_cookies: bool = True
    cookies_expiry_days: int = 7

@dataclass
class FilterConditions:
    """筛选条件配置"""
    brands: List[str] = field(default_factory=list)
    price_range: Tuple[float, float] = (0, 9999)
    seller_type: str = "all"  # all, jd_self, third_party
    min_rating: float = 0.0
    min_sales: int = 0

@dataclass
class SearchConfig:
    """搜索配置"""
    keywords: List[str] = field(default_factory=lambda: ["ddr4内存 笔记本电脑组件 32G"])
    max_pages: int = 3
    scroll_pause: float = 1.0
    items_per_page: int = 30
    sort_method: SortMethod = SortMethod.DEFAULT
    filter_conditions: FilterConditions = field(default_factory=FilterConditions)
    smart_scroll: bool = True  # 是否智能滚动以加载更多商品

@dataclass
class VisionPreprocessingConfig:
    """视觉预处理配置"""
    denoise: bool = True
    binarization: bool = True
    contrast_enhance: bool = True
    resize_factor: float = 2.0  # 图像放大倍数，提高OCR准确率

@dataclass
class VisionConfig:
    """视觉识别配置"""
    templates_dir: str = "templates"
    match_threshold: float = 0.8
    ocr_language: str = "chi_sim+eng"
    preprocessing: VisionPreprocessingConfig = field(default_factory=VisionPreprocessingConfig)
    debug_save_images: bool = False  # 是否保存调试图像
    debug_save_dir: str = "debug_images"

@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: DatabaseType = DatabaseType.SQLITE
    path: str = "data/price_data.db"
    host: str = "localhost"
    port: int = 3306
    name: str = "price_tracker"
    user: str = ""
    password: str = ""
    backup_days: int = 7
    auto_backup: bool = True
    backup_dir: str = "backups"
    connection_pool_size: int = 5

@dataclass
class SchedulerConfig:
    """定时任务配置"""
    enabled: bool = True
    execution_times: List[str] = field(default_factory=lambda: ["10:00", "16:00", "22:00"])
    max_runtime: int = 1800  # 秒
    retry_attempts: int = 3
    retry_delay: int = 300  # 秒
    timezone: str = "Asia/Shanghai"

@dataclass
class ErrorNotificationConfig:
    """错误通知配置"""
    enabled: bool = False
    email: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""
    notify_on_errors: List[str] = field(default_factory=lambda: ["critical", "error"])

@dataclass
class MonitoringConfig:
    """监控配置"""
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: str = "logs/price_tracker.log"
    max_log_size: int = 10485760  # 10MB
    backup_count: int = 5
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    performance_monitoring: bool = True
    error_notification: ErrorNotificationConfig = field(default_factory=ErrorNotificationConfig)

@dataclass
class RandomBehaviorConfig:
    """随机行为配置"""
    mouse_movement: bool = True
    click_offset: bool = True
    typing_speed_variation: bool = True
    idle_behavior: bool = True
    scroll_variation: bool = True

@dataclass
class IPRotationConfig:
    """IP轮换配置"""
    enabled: bool = False
    proxy_list: List[str] = field(default_factory=list)
    change_interval: int = 3600  # 秒
    proxy_type: str = "http"  # http, socks5

@dataclass
class AntiDetectionConfig:
    """反检测配置"""
    rotate_user_agent: bool = True
    user_agents_pool: List[str] = field(default_factory=list)
    random_behavior: RandomBehaviorConfig = field(default_factory=RandomBehaviorConfig)
    ip_rotation: IPRotationConfig = field(default_factory=IPRotationConfig)
    mimic_human_pattern: bool = True

@dataclass
class PriceAlertConfig:
    """价格提醒配置"""
    enabled: bool = False
    check_interval: int = 3600  # 秒
    drop_threshold: float = 0.1  # 降价10%提醒
    rise_threshold: float = 0.2  # 涨价20%提醒
    notification_methods: List[str] = field(default_factory=lambda: ["console"])

@dataclass
class AppConfig:
    """应用程序主配置"""
    version: str = "1.0.0"
    environment: str = "development"  # development, testing, production
    debug: bool = False
    
    human_simulator: HumanSimulatorConfig = field(default_factory=HumanSimulatorConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    jd_account: JDAccountConfig = field(default_factory=JDAccountConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    price_alert: PriceAlertConfig = field(default_factory=PriceAlertConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """从字典创建实例"""
        return cls(**data)