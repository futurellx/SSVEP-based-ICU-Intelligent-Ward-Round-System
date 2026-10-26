import pyautogui
from screeninfo import get_monitors
class ScreenController:
    def __init__(self):
        self.monitors = get_monitors()
        self.primary_monitor = self.find_primary_monitor()
        self.secondary_monitor = self.find_secondary_monitor()
        self.last_primary_position = self.get_last_primary_position()

    def find_primary_monitor(self):
        """查找主屏幕"""
        for monitor in self.monitors:
            if monitor.is_primary:
                return monitor
        return None

    def find_secondary_monitor(self):
        """查找副屏幕"""
        for monitor in self.monitors:
            if not monitor.is_primary:
                return monitor
        return None

    def get_last_primary_position(self):
        """获取鼠标在主屏幕上的最后一个位置"""
        if self.primary_monitor:
            current_position = pyautogui.position()
            if self.is_position_on_monitor(current_position, self.primary_monitor):
                return current_position
            else:
                # 如果当前鼠标不在主屏幕上，返回主屏幕的中心点
                return (self.primary_monitor.x + self.primary_monitor.width // 2,
                        self.primary_monitor.y + self.primary_monitor.height // 2)
        return None

    def is_position_on_monitor(self, position, monitor):
        """检查给定位置是否在指定的显示器上"""
        x, y = position
        return (monitor.x <= x < monitor.x + monitor.width and
                monitor.y <= y < monitor.y + monitor.height)

    def click_secondary_screen_center(self):
        """移动鼠标到副屏幕中心并点击两次，然后移动到主屏幕上次停留的位置"""
        if self.secondary_monitor:
            # 计算副屏幕的中心点
            center_x = self.secondary_monitor.x + self.secondary_monitor.width - 5
            center_y = self.secondary_monitor.y + self.secondary_monitor.height - 5

            # 移动鼠标到副屏幕的中心点并点击两次
            pyautogui.moveTo(center_x, center_y)
            pyautogui.click()
            pyautogui.click()

            # 移动鼠标到主屏幕的上次停留位置
            if self.primary_monitor and self.last_primary_position:
                pyautogui.moveTo(self.last_primary_position)
        else:
            print("没有检测到副屏幕")

# 示例用法
# if __name__ == "__main__":
#     controller = ScreenController()
#     controller.click_secondary_screen_center()
