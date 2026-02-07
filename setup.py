# setup.py

"""
对于包内测试，出现相对导入错误如
ModuleNotFoundError: No module named 'src.config'
在命令行中切换到当前目录(.../MemoCrawl)下运行
pip install -e .
来解决。
"""


from setuptools import setup, find_packages

setup(
    name="memocrawl",
    packages=find_packages(),
)