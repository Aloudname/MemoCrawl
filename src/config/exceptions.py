"""
exceptions.py
配置模块自定义异常
"""

class ConfigError(Exception):
    """配置基础异常"""
    pass

class ConfigFileNotFoundError(ConfigError):
    """配置文件未找到异常"""
    pass

class ConfigValidationError(ConfigError):
    """配置验证异常"""
    pass

class ConfigTemplateError(ConfigError):
    """配置模板异常"""
    pass

class ConfigEncryptionError(ConfigError):
    """配置加密异常"""
    pass