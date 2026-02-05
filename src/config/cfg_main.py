# cfg_main.py
import logging

from src.config.manager import init_config, get_config

# 初始化配置（如果配置文件不存在会创建模板）
config = init_config("config.yaml", create_template=True)

# 或者直接获取全局配置
config = get_config("config.yaml")

# 获取配置值
username = config.get("browser.jd_account.username")
password = config.get("browser.jd_account.password")
max_pages = config.get("search.max_pages")

# 设置配置值
config.set("search.max_pages", 5)
config.set("browser.jd_account.password", "new_password", encrypt=True)

# 验证配置
is_valid, errors, warnings = config.validate()
if not is_valid:
    print("配置错误:", errors)

# 保存配置
config.save()

# 获取所有配置（不包含敏感信息）
all_config = config.get_all(include_sensitive=False)
print("当前配置:", all_config)