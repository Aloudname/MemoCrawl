"""
template.py
配置模板管理
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging
from src.config.models import AppConfig

logger = logging.getLogger(__name__)

class ConfigTemplate:
    """配置模板管理器"""
    
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.template_file = self.template_dir / "config.yaml.template"
    
    def load_template(self) -> Dict[str, Any]:
        """
        加载配置模板
        
        Returns:
            模板配置字典
        """
        if not self.template_file.exists():
            return self._create_default_template()
        
        try:
            with open(self.template_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载配置模板失败: {e}")
            return self._create_default_template()
    
    def _create_default_template(self) -> Dict[str, Any]:
        """创建默认配置模板"""
        default_config = AppConfig()
        template_dict = default_config.dict(exclude_unset=True)
        
        # 清理敏感信息
        template_dict['browser']['jd_account']['password'] = ""
        template_dict['database']['password'] = ""
        template_dict['monitoring']['error_notification']['telegram_token'] = ""
        
        # 确保模板目录存在
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存模板
        with open(self.template_file, 'w', encoding='utf-8') as f:
            yaml.dump(template_dict, f, allow_unicode=True, default_flow_style=False)
        
        logger.info(f"已创建默认配置模板: {self.template_file}")
        return template_dict
    
    def create_config_from_template(self, 
                                   output_path: Union[str, Path],
                                   template_dict: Optional[Dict[str, Any]] = None) -> bool:
        """
        从模板创建配置文件
        
        Args:
            output_path: 输出文件路径
            template_dict: 模板字典，为None则加载默认模板
            
        Returns:
            是否成功
        """
        try:
            if template_dict is None:
                template_dict = self.load_template()
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_dict, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"已从模板创建配置文件: {output_path}")
            return True
        except Exception as e:
            logger.error(f"从模板创建配置文件失败: {e}")
            return False
    
    def compare_with_template(self, 
                             config_dict: Dict[str, Any],
                             template_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        比较配置与模板的差异
        
        Args:
            config_dict: 配置字典
            template_dict: 模板字典
            
        Returns:
            差异信息字典
        """
        if template_dict is None:
            template_dict = self.load_template()
        
        differences = {
            'missing_fields': [],
            'extra_fields': [],
            'type_mismatches': []
        }
        
        def _compare(config: Dict, template: Dict, path: str = ""):
            for key, template_value in template.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in config:
                    differences['missing_fields'].append(current_path)
                    continue
                
                config_value = config[key]
                
                if isinstance(template_value, dict):
                    if not isinstance(config_value, dict):
                        differences['type_mismatches'].append(f"{current_path}: 应为字典")
                    else:
                        _compare(config_value, template_value, current_path)
                elif isinstance(template_value, list):
                    if not isinstance(config_value, list):
                        differences['type_mismatches'].append(f"{current_path}: 应为列表")
            
            # 检查额外字段
            for key in config:
                if key not in template:
                    current_path = f"{path}.{key}" if path else key
                    differences['extra_fields'].append(current_path)
        
        _compare(config_dict, template_dict)
        return differences