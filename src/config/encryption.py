"""
encryption.py
配置加密工具
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional, Dict, Any, List
import getpass

class ConfigEncryptor:
    """配置加密器"""
    
    def __init__(self, key_file: str = "config_key.key", use_password: bool = False):
        """
        初始化加密器
        
        Args:
            key_file: 密钥文件路径
            use_password: 是否使用用户密码保护密钥
        """
        self.key_file = key_file
        self.use_password = use_password
        self.cipher = None
        self._init_encryption()
    
    def _init_encryption(self) -> None:
        """初始化加密"""
        if os.path.exists(self.key_file):
            # 加载现有密钥
            with open(self.key_file, 'rb') as f:
                key_data = f.read()
            
            if self.use_password:
                # 需要用户输入密码来解密密钥
                password = getpass.getpass("请输入解密密码: ")
                key = self._derive_key_from_password(password, key_data[:16])
                self.cipher = Fernet(key)
            else:
                self.cipher = Fernet(key_data)
        else:
            # 生成新密钥
            if self.use_password:
                password = getpass.getpass("请设置加密密码: ")
                verify_password = getpass.getpass("请确认密码: ")
                
                if password != verify_password:
                    raise ValueError("密码不匹配")
                
                salt = os.urandom(16)
                key = self._derive_key_from_password(password, salt)
                
                # 保存盐和加密后的密钥
                with open(self.key_file, 'wb') as f:
                    f.write(salt + key)
            else:
                key = Fernet.generate_key()
                with open(self.key_file, 'wb') as f:
                    f.write(key)
            
            self.cipher = Fernet(key)
            
            # 设置文件权限
            os.chmod(self.key_file, 0o600)
    
    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_value(self, value: str) -> str:
        """加密值"""
        if not self.cipher:
            raise RuntimeError("加密器未初始化")
        
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """解密值"""
        if not self.cipher:
            raise RuntimeError("加密器未初始化")
        
        try:
            encrypted = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"解密失败: {e}")
    
    def encrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """加密字典中的指定字段"""
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt_value(str(result[field]))
        return result
    
    def decrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """解密字典中的指定字段"""
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.decrypt_value(str(result[field]))
        return result


class SimpleEncryptor:
    """简单加密器（用于不需要密码的情况）"""
    
    def __init__(self, key_file: str = "simple_key.key"):
        self.key_file = key_file
        self.cipher = None
        self._load_or_create_key()
    
    def _load_or_create_key(self):
        """加载或创建密钥"""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            os.chmod(self.key_file, 0o600)
        
        self.cipher = Fernet(key)
    
    def encrypt(self, value: str) -> str:
        """加密"""
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_value: str) -> str:
        """解密"""
        encrypted = base64.b64decode(encrypted_value.encode())
        return self.cipher.decrypt(encrypted).decode()