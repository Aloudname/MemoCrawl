# cfg_main.py
import logging
from src.config import init_config, get_config
from src.config.manager import get_config_manager
from typing import Any, Dict

def get_dict_config() -> Dict[str, Any]:
    """
    获取字典形式的配置
    
    Returns:
        配置字典
    """
    return get_config_manager().dict_config


# 初始化配置（如果配置文件不存在，会从模板创建）
config_manager = init_config(
    config_file="config.yaml",
    template_file="templates/config.yaml.template",
    auto_create=True
)

# 获取配置访问器（支持点号访问）
config = get_config()
chrome_path = config.browser.chrome_path
username = config.browser.jd_account.username
max_pages = config.search.max_pages

# 获取字典形式的配置
dict_config = get_dict_config()
username_dict = dict_config['browser']['jd_account']['username']

# 设置配置值
config_manager.set("search.max_pages", 5)
config_manager.set("browser.jd_account.password", "new_password")

# 验证配置
validation_result = config_manager.validate()
if not validation_result['is_valid']:
    print("配置错误:", validation_result['structure_errors'])
    print("数据错误:", validation_result['data_errors'])

# 保存配置
config_manager.save()

# 获取安全的配置字典（隐藏敏感信息）
safe_config = config_manager.get_safe_dict(hide_sensitive=True)
print("当前配置（安全）:", safe_config)