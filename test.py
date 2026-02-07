import subprocess
from src.config import init_config, get_dict_config
from src.modules import HumanDelayConfig, MouseMoveConfig, HumanSimulator, BrowserController

init_config()
config = get_dict_config()

human_delay = HumanDelayConfig(
    min_delay=config.get('min_delay', 0.1),
    max_delay=config.get('max_delay', 0.5),
    think_time_min=config.get('think_time_min', 0.2),
    think_time_max=config.get('think_time_max', 1.0)
)

mouse_config = MouseMoveConfig(
    speed_min=config.get('speed_min', 0.3),
    speed_max=config.get('speed_max', 0.8),
    curve_factor=config.get('curve_factor', 0.3)
)

hs = HumanSimulator(
    human_delay=human_delay,
    mouse_config=mouse_config
)
bc = BrowserController(simulator=hs, config=config)

chrome_args = [
    bc.config.browser.path.chrome_path,
    "--start-maximized",
    "--disable-infobars",
    "--disable-notifications",
]

browser_process = subprocess.Popen(chrome_args)
bc.simulator.idle_behavior(min_duration=3, max_duration=5)