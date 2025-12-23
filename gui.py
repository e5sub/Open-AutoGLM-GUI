import subprocess
import time
import re
from typing import Optional, Tuple


def _adb_shell(cmd: str, adb: str = "adb", timeout: int = 5) -> str:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        p = subprocess.run([adb, 'shell', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, creationflags=creationflags)
        return p.stdout.decode(errors='ignore')
    except Exception:
        return ""


def is_screen_on(adb: str = "adb") -> bool:
    """检查设备屏幕是否点亮。返回 True 表示亮屏。

    使用 `dumpsys power` 的输出进行多种模式解析，提高兼容性。
    """
    out = _adb_shell('dumpsys power', adb)
    if not out:
        return False

    m = re.search(r'mWakefulness=(\w+)', out)
    if m:
        return m.group(1).lower() == 'awake'

    m = re.search(r'mScreenOn=(true|false)', out, re.I)
    if m:
        return m.group(1).lower() == 'true'

    m = re.search(r'Display Power: state=(\w+)', out, re.I)
    if m:
        return m.group(1).lower() != 'off'

    # 兜底：如果包含 Awake 关键字则认为是亮屏
    if 'awake' in out.lower():
        return True

    return False


def wake_and_unlock(adb: str = "adb", max_attempts: int = 3, swipe: Optional[Tuple[int, int, int, int]] = None, password: Optional[str] = None) -> bool:
    """唤醒并尝试解锁屏幕。

    顺序：发送 WAKEUP -> 发送 MENU (或解锁键) -> 可选滑动解锁。
    返回 True 表示检测到屏幕已点亮。
    """
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    for _ in range(max_attempts):
        subprocess.run([adb, 'shell', 'input', 'keyevent', '224'], creationflags=creationflags)  # KEYCODE_WAKEUP
        time.sleep(0.4)
        subprocess.run([adb, 'shell', 'input', 'keyevent', '82'], creationflags=creationflags)   # KEYCODE_MENU (通常可解锁)
        time.sleep(0.4)
        if swipe:
            x1, y1, x2, y2 = swipe
            subprocess.run([adb, 'shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2)], creationflags=creationflags)
            time.sleep(0.5)

        # 如果提供了密码，尝试通过输入密码解锁（在滑动或按键后）
        if password:
            try:
                # input text 对空格的处理需要替换为 %s
                esc = str(password).replace(' ', '%s')
                subprocess.run([adb, 'shell', 'input', 'text', esc], creationflags=creationflags)
                time.sleep(0.3)
                # 按回车或确认键
                subprocess.run([adb, 'shell', 'input', 'keyevent', '66'], creationflags=creationflags)
                time.sleep(0.6)
            except Exception:
                pass

        if is_screen_on(adb):
            return True

        # 备用：短按电源键（某些机型需要）
        subprocess.run([adb, 'shell', 'input', 'keyevent', '26'], creationflags=creationflags)
        time.sleep(0.6)

    return is_screen_on(adb)


def ensure_awake_and_unlocked(adb: str = "adb", swipe: Optional[Tuple[int, int, int, int]] = None, password: Optional[str] = None) -> bool:
    """在继续执行前确保屏幕已唤醒并尽量解锁。

    返回 True 表示屏幕已唤醒（或已成功解锁）。
    """
    try:
        if is_screen_on(adb):
            return True
        return wake_and_unlock(adb, swipe=swipe, password=password)
    except Exception:
        return False

#!/usr/bin/env python3
"""
GUI for Phone Agent - AI-powered phone automation.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import os
import sys

# 隐藏控制台窗口（仅在Windows上有效）
if sys.platform == 'win32' and 'python.exe' in sys.executable:
    import ctypes
    try:
        # 尝试隐藏控制台窗口
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass
import sys
import json
from datetime import datetime
import re

# 导入任务精简器
from task_simplifier import TaskSimplifierManager


class PhoneAgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("鸡哥手机助手 v1.8 - 更多好玩的工具请关注微信公众号：菜芽创作小助手")
        self.root.geometry("1200x750")
        self.root.minsize(1100, 650)
        
        # 显示快速启动提示
        self.show_startup_message()
        
        # 设置样式
        self.setup_styles()
        
        # 变量存储
        self.base_url = tk.StringVar(value="https://open.bigmodel.cn/api/paas/v4")
        self.model = tk.StringVar(value="autoglm-phone")
        self.apikey = tk.StringVar(value="your-bigmodel-api-key")
        self.task = tk.StringVar(value="输入你想要执行的任务，例如：打开美团搜索附近的火锅店")
        self.max_steps = tk.StringVar(value="200")
        self.temperature = tk.StringVar(value="0.0")  # 新增temperature参数
        self.device_type = tk.StringVar(value="安卓")  # 默认为安卓
        
        self.process = None
        self.running = False
        self.config_file = "gui_config.json"
        
        # 设备相关变量
        self.connected_devices = []
        self.selected_device_id = tk.StringVar(value="")
        # 支持环境变量 PHONE_AGENT_DEVICE_ID
        self.env_device_id = os.getenv("PHONE_AGENT_DEVICE_ID", "")
        # iOS设备IP地址
        self.ios_device_ip = tk.StringVar(value="localhost")
        
        # 窗口控制变量
        self.qrcode_window = None
        self.adb_connection_window = None
        self.device_details_window = None
        self.remote_desktop_window = None
        
        # 设备类型防重复变量
        self._last_device_type = None
        # iOS IP对话框状态标志
        self._ios_ip_dialog_open = False

        # 初始化任务精简器
        self.task_simplifier = TaskSimplifierManager()
        
        # 任务历史记录
        self.task_history_file = "task_history.json"
        self.task_history = []
        self.load_task_history()
        
        # 快速创建基础界面
        self.create_basic_widgets()
        
        # 更新界面显示完成
        self.root.update_idletasks()
        
        # 异步加载剩余组件和配置
        threading.Thread(target=self.async_initialization, daemon=True).start()
        
        # 设置程序关闭时的自动保存
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def show_startup_message(self):
        """显示启动提示"""
        startup_label = tk.Label(self.root, text="🚀 正在启动...", 
                                 font=('Microsoft YaHei', 12), 
                                 fg='#2E86AB', bg='white')
        startup_label.place(relx=0.5, rely=0.5, anchor='center')
        self.startup_label = startup_label
        self.root.update_idletasks()
    
    def async_initialization(self):
        """异步初始化剩余组件"""
        try:
            # 延迟创建完整界面
            self.root.after(50, self.create_full_widgets)
            
            # 延迟加载配置
            self.root.after(150, self.load_config_async)
            
        except Exception as e:
            print(f"异步初始化错误: {e}")

    def _prepare_device_on_startup(self, adb: str = 'adb', swipe: Optional[Tuple[int, int, int, int]] = (300, 1000, 300, 300)):
        """在后台检查设备屏幕并尝试唤醒/解锁，避免阻塞 GUI 启动。

        使用已有的 `ensure_awake_and_unlocked` 函数。
        """
        try:
            try:
                self.root.after(0, lambda: self.startup_label.config(text='🔌 检查并唤醒设备...'))
            except Exception:
                pass

            try:
                import os
                pwd = os.getenv('PHONE_AGENT_LOCK_PASSWORD', '')
            except Exception:
                pwd = ''
            ok = ensure_awake_and_unlocked(adb=adb, swipe=swipe, password=pwd if pwd else None)

            if ok:
                msg = '✅ 设备已唤醒并尽量解锁'
            else:
                msg = '⚠️ 无法唤醒设备，请手动检查'

            try:
                # 如果 status_var 可用则更新，否则更新 startup_label
                if hasattr(self, 'status_var'):
                    self.root.after(0, lambda: self.status_var.set(msg))
                else:
                    self.root.after(0, lambda: self.startup_label.config(text=msg))
            except Exception:
                pass
        except Exception as e:
            print(f"设备准备失败: {e}")
    
    def load_config_async(self):
        """异步加载配置，避免阻塞启动"""
        threading.Thread(target=self._background_load_config, daemon=True).start()
                
    def _background_load_config(self):
        """后台线程中加载配置"""
        try:
            config_data = None
            config_file_path = self.config_file
            
            # 检查配置文件是否存在
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            
            # 在主线程中应用配置
            if config_data:
                self.root.after(0, lambda: self._apply_config(config_data))
            else:
                self.root.after(0, self._create_default_config)
                
        except Exception as e:
            print(f"后台加载配置失败: {str(e)}")
            if hasattr(self, 'status_var'):
                self.root.after(0, lambda: self.status_var.set("⚠️ 配置加载失败"))
                
    def _apply_config(self, config):
        """在主线程中应用配置"""
        try:
            self.base_url.set(config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4'))
            self.model.set(config.get('model', 'autoglm-phone'))
            self.apikey.set(config.get('apikey', 'your-bigmodel-api-key'))
            task_text = config.get('task', '输入你想要执行的任务，例如：打开美团搜索附近的火锅店')
            self.task.set(task_text)
            self.max_steps.set(str(config.get('max_steps', '200')))
            self.temperature.set(str(config.get('temperature', '0.0')))  # 添加temperature加载
            device_type_value = config.get('device_type', 'adb')
            # 将保存的英文值转换为中文显示
            if device_type_value == 'adb':
                self.device_type.set('安卓')
            elif device_type_value == 'ios':
                self.device_type.set('iOS')
            else:
                self.device_type.set('鸿蒙')
            
            # 加载iOS设备IP配置
            ios_ip = config.get('ios_device_ip', 'localhost')
            if hasattr(self, 'ios_device_ip'):
                self.ios_device_ip.set(ios_ip)
            
            # 如果界面已创建，更新任务文本框
            if hasattr(self, 'task_text'):
                self.task_text.delete("1.0", tk.END)
                self.task_text.insert("1.0", task_text)
            
            # 恢复选中的设备，优先使用环境变量
            selected_device = self.env_device_id or config.get('selected_device', '')
            if selected_device and hasattr(self, 'selected_device_id'):
                self.selected_device_id.set(selected_device)
                print(f"🔍 配置加载: 设置selected_device_id为 '{selected_device}'")
            
            # 如果界面已创建，只更新界面显示，不自动扫描设备
            if hasattr(self, 'adb_frame'):
                current_device_type = self.device_type.get()
                self._last_device_type = current_device_type  # 更新防重复标志
                
                # 只更新界面显示，不执行设备扫描
                if hasattr(self, 'adb_control_frame'):
                    # 将中文选项转换为英文值用于内部处理
                    if current_device_type == "安卓":
                        device_type_en = "adb"
                    elif current_device_type == "鸿蒙":
                        device_type_en = "hdc"
                    elif current_device_type == "iOS":
                        device_type_en = "ios"
                    else:
                        device_type_en = "adb"  # 默认
                    
                    # 只更新标题和按钮文本，不扫描设备
                    if device_type_en == "hdc":
                        self.adb_frame.config(text="📱 HDC设备管理")
                    elif device_type_en == "ios":
                        self.adb_frame.config(text="🍎 iOS设备管理")
                        if hasattr(self, 'device_status_label'):
                            current_ip = self.ios_device_ip.get()
                            if current_ip and current_ip != "localhost":
                                self.device_status_label.config(text=f"iOS设备IP: {current_ip}")
                            else:
                                self.device_status_label.config(text="iOS设备未配置IP")
                    else:
                        self.adb_frame.config(text="📱 ADB设备管理")
                        if hasattr(self, 'device_status_label'):
                            if selected_device:
                                self.device_status_label.config(text=f"已连接: {selected_device}")
                            else:
                                self.device_status_label.config(text=f"未连接ADB设备")
            
            # 加载远程连接配置
            self.last_remote_connection = config.get('remote_connection', {
                'ip': '192.168.1.100',
                'port': '5555'
            })
            
            # 加载无线调试配对配置
            self.last_wireless_pair = config.get('wireless_pair', {
                'pair_address': '10.10.10.100:41717',
                'connect_address': '10.10.10.100:5555'
            })
            
            # 加载Android 10及以下无线调试配置
            self.last_legacy_wireless = config.get('legacy_wireless', {
                'ip': '192.168.1.100',
                'port': '5555'
            })
            
            # 加载锁屏密码配置
            lock_password = config.get('lock_password', '')
            if lock_password:
                import os
                os.environ['PHONE_AGENT_LOCK_PASSWORD'] = lock_password
            
            if hasattr(self, 'status_var'):
                self.status_var.set("✅ 配置已加载")
            

                
        except Exception as e:
            print(f"应用配置失败: {str(e)}")
            if hasattr(self, 'status_var'):
                self.status_var.set("⚠️ 配置应用失败")
    
    def _calculate_center_position(self, child_width, child_height):
        """计算相对于主窗口的居中位置"""
        # 确保主窗口完全更新
        self.root.update_idletasks()
        
        # 获取主窗口的位置和大小
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        # 计算居中位置
        center_x = main_x + (main_width // 2) - (child_width // 2)
        center_y = main_y + (main_height // 2) - (child_height // 2)
        
        # 确保窗口不会超出屏幕边界
        import tkinter as tk
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        if center_x < 0:
            center_x = 0
        if center_y < 0:
            center_y = 0
        if center_x + child_width > screen_width:
            center_x = screen_width - child_width
        if center_y + child_height > screen_height:
            center_y = screen_height - child_height
        
        return center_x, center_y
    
    def center_window(self, window, width=None, height=None):
        """将窗口居中显示在主窗口中间，避免闪现"""
        try:
            # 先隐藏窗口，避免闪现
            window.withdraw()
            window.update_idletasks()
            
            # 使用计算方法获取位置
            if width and height:
                center_x, center_y = self._calculate_center_position(width, height)
                window.geometry(f"{width}x{height}+{center_x}+{center_y}")
            else:
                child_width = window.winfo_width()
                child_height = window.winfo_height()
                
                # 如果窗口还没有实际大小，使用默认值
                if child_width <= 1:
                    child_width = 500
                if child_height <= 1:
                    child_height = 400
                    
                center_x, center_y = self._calculate_center_position(child_width, child_height)
                window.geometry(f"+{center_x}+{center_y}")
            
            # 最后显示窗口
            window.deiconify()
            window.update_idletasks()
            
        except Exception as e:
            print(f"居中窗口失败: {e}")
            # 如果失败，确保窗口可见
            try:
                window.deiconify()
            except:
                pass
    
    def create_centered_toplevel(self, parent, title, width, height, resizable=True):
        """创建居中显示的Toplevel窗口，避免闪现
        
        Args:
            parent: 父窗口
            title: 窗口标题
            width: 窗口宽度
            height: 窗口高度
            resizable: 是否可调整大小
        
        Returns:
            创建的Toplevel窗口
        """
        try:
            # 先计算居中位置
            center_x, center_y = self._calculate_center_position(width, height)
            
            # 创建窗口时直接设置位置
            window = tk.Toplevel(parent)
            window.title(title)
            window.geometry(f"{width}x{height}+{center_x}+{center_y}")
            
            # 设置是否可调整大小
            if resizable:
                window.resizable(True, True)
            else:
                window.resizable(False, False)
            
            # 确保窗口正确显示
            window.update_idletasks()
            
            return window
            
        except Exception as e:
            print(f"创建居中窗口失败: {e}")
            # 降级方案：使用普通的Toplevel
            window = tk.Toplevel(parent)
            window.title(title)
            window.geometry(f"{width}x{height}")
            if resizable:
                window.resizable(True, True)
            else:
                window.resizable(False, False)
            self.center_window(window, width, height)
            return window
                
    def _create_default_config(self):
        """创建默认配置"""
        if hasattr(self, 'status_var'):
            self.status_var.set("📝 使用默认配置")
        
        # 首次启动时不自动扫描设备，避免弹出CMD窗口
        # 用户手动操作时会自动触发设备扫描
        pass
        
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        
        # 设置主题
        style.theme_use('clam')
        
        # 配置颜色
        style.configure('Title.TLabel', font=('Microsoft YaHei', 18, 'bold'), foreground='#2E86AB')
        style.configure('Header.TLabel', font=('Microsoft YaHei', 12, 'bold'), foreground='#333333')
        style.configure('Success.TButton', font=('Microsoft YaHei', 10, 'bold'), 
                       foreground='white', background='#28a745')
        style.map('Success.TButton', 
                 background=[('active', '#218838'), ('pressed', '#1e7e34')])
        style.configure('Danger.TButton', font=('Microsoft YaHei', 10, 'bold'), 
                       foreground='white', background='#dc3545')
        style.map('Danger.TButton', 
                 background=[('active', '#c82333'), ('pressed', '#bd2130')])
        style.configure('Secondary.TButton', font=('Microsoft YaHei', 10, 'bold'), 
                       foreground='#333333', background='#6c757d')
        style.map('Secondary.TButton', 
                 background=[('active', '#5a6268'), ('pressed', '#545b62')])
        
        # 配置框架
        style.configure('Card.TFrame', relief='raised', borderwidth=1)
        style.configure('Output.TFrame', relief='sunken', borderwidth=2)
        
    def create_basic_widgets(self):
        """创建基础界面组件（快速显示）"""
        # 主框架
        self.main_frame = ttk.Frame(self.root, padding="15")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
    
    def create_full_widgets(self):
        """创建完整界面组件（异步加载）"""
        try:
            # 快速移除启动提示，避免界面闪烁
            if hasattr(self, 'startup_label'):
                self.startup_label.destroy()
            
            # 标题区域
            title_frame = ttk.Frame(self.main_frame)
            title_frame.grid(row=0, column=0, columnspan=3, pady=(0, 25))
            
            title_label = ttk.Label(title_frame, text="🤖 鸡哥手机助手", style='Title.TLabel')
            title_label.pack()
            
            subtitle_label = ttk.Label(title_frame, text="AI驱动的手机自动化工具", font=('Microsoft YaHei', 10))
            subtitle_label.pack()
            
            # 配置区域
            config_frame = ttk.LabelFrame(self.main_frame, text="⚙️ 配置参数", style='Card.TFrame', padding="8")
            config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))
            config_frame.columnconfigure(1, weight=1)
            
            # Base URL
            ttk.Label(config_frame, text="🌐 Base URL:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=3)
            url_entry = ttk.Entry(config_frame, textvariable=self.base_url, width=50, font=('Microsoft YaHei', 9))
            url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
            
            # Model
            ttk.Label(config_frame, text="🧠 Model:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=3)
            model_entry = ttk.Entry(config_frame, textvariable=self.model, width=50, font=('Microsoft YaHei', 9))
            model_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
            
            # API Key
            ttk.Label(config_frame, text="🔑 API Key:", font=('Microsoft YaHei', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=3)
            apikey_frame = ttk.Frame(config_frame)
            apikey_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
            apikey_frame.columnconfigure(0, weight=1)
            
            self.apikey_entry = ttk.Entry(apikey_frame, textvariable=self.apikey, width=40, show="*", font=('Microsoft YaHei', 9))
            self.apikey_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            self.show_apikey_btn = ttk.Button(apikey_frame, text="👁️", width=2, command=self.toggle_apikey_visibility)
            self.show_apikey_btn.grid(row=0, column=1, padx=(3, 0))
            
            # Task
            ttk.Label(config_frame, text="📝 Task:", font=('Microsoft YaHei', 9, 'bold')).grid(row=3, column=0, sticky=(tk.NW, tk.W), pady=3)
            
            # 任务输入框和按钮的组合框架
            task_frame = ttk.Frame(config_frame)
            task_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
            task_frame.columnconfigure(0, weight=1)
            
            self.task_text = tk.Text(task_frame, width=50, height=2, font=('Microsoft YaHei', 9), wrap=tk.WORD)
            self.task_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # 任务操作按钮框架
            task_buttons_frame = ttk.Frame(task_frame)
            task_buttons_frame.grid(row=0, column=1, padx=(5, 0))
            
            # 任务精简按钮
            self.simplify_task_button = ttk.Button(task_buttons_frame, text="🤖 AI润色", 
                                                 command=self.show_task_simplifier, 
                                                 style='Success.TButton')
            self.simplify_task_button.grid(row=0, column=1, padx=(5, 0))
            
            # 任务历史按钮（放在AI润色按钮左边）
            self.task_history_button = ttk.Button(task_buttons_frame, text="📚", 
                                                 command=self.show_task_history, 
                                                 width=2)
            self.task_history_button.grid(row=0, column=0)
            
            # 设置初始任务文本
            self.task_text.insert("1.0", self.task.get())
            self.task_text.bind("<KeyRelease>", lambda e: self.on_task_change())
            
            # Max Steps 和 Device Type 在同一排
            settings_row_frame = ttk.Frame(config_frame)
            settings_row_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
            settings_row_frame.columnconfigure(1, weight=1)
            settings_row_frame.columnconfigure(3, weight=1)
            settings_row_frame.columnconfigure(5, weight=1)
            
            # Device Type (左半部分) - 精确对齐Task输入框
            device_type_frame = ttk.Frame(settings_row_frame)
            device_type_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(0, 10))
            device_type_frame.columnconfigure(0, weight=0)  # 标签列固定宽度
            device_type_frame.columnconfigure(1, weight=1)  # 输入框列拉伸
            
            # 标签，与配置区域的标签对齐
            ttk.Label(device_type_frame, text="🔗设备类型:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # 输入框和说明文字的组合 - 使用10px的padding与Task输入框对齐
            device_type_combo_frame = ttk.Frame(device_type_frame)
            device_type_combo_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
            device_type_combo_frame.columnconfigure(0, weight=0)
            
            self.device_type_combo = ttk.Combobox(device_type_combo_frame, textvariable=self.device_type, width=15, font=('Microsoft YaHei', 9), state="readonly")
            self.device_type_combo['values'] = ('安卓', '鸿蒙', 'iOS')
            self.device_type_combo.grid(row=0, column=0, sticky=tk.W)
            self.device_type_combo.bind('<<ComboboxSelected>>', lambda e: self.on_device_type_change())
            ttk.Label(device_type_combo_frame, text="（选择设备系统类型）", font=('Microsoft YaHei', 8), foreground='gray').grid(row=0, column=1, padx=(3, 0))
            
            # Temperature (右半部分) - 在最大步数右边
            temperature_frame = ttk.Frame(settings_row_frame)
            temperature_frame.grid(row=0, column=5, columnspan=1, sticky=(tk.W, tk.E), padx=(10, 0))
            temperature_frame.columnconfigure(0, weight=0)
            temperature_frame.columnconfigure(1, weight=1)
            
            # 标签，与设备类型和最大步数保持完全一致的间距
            ttk.Label(temperature_frame, text="🌡️温度值:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # 输入框和说明文字的组合
            temperature_entry_frame = ttk.Frame(temperature_frame)
            temperature_entry_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
            temperature_entry_frame.columnconfigure(0, weight=0)
            
            self.temperature_entry = ttk.Entry(temperature_entry_frame, textvariable=self.temperature, width=8, font=('Microsoft YaHei', 9))
            self.temperature_entry.grid(row=0, column=0, sticky=tk.W)
            self.temperature_entry.bind("<FocusOut>", lambda e: self.validate_temperature())
            ttk.Label(temperature_entry_frame, text="（控制随机性，0.0-1.0）", font=('Microsoft YaHei', 8), foreground='gray').grid(row=0, column=1, padx=(3, 0))
            
            # Max Steps (右半部分)
            max_steps_frame = ttk.Frame(settings_row_frame)
            max_steps_frame.grid(row=0, column=3, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0))
            max_steps_frame.columnconfigure(0, weight=0)
            max_steps_frame.columnconfigure(1, weight=1)
            
            # 标签，与配置区域的标签对齐
            ttk.Label(max_steps_frame, text="🔢最大步数:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # 输入框和说明文字的组合 - 使用10px的padding与Task输入框对齐
            max_steps_entry_frame = ttk.Frame(max_steps_frame)
            max_steps_entry_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
            max_steps_entry_frame.columnconfigure(0, weight=0)
            
            self.max_steps_entry = ttk.Entry(max_steps_entry_frame, textvariable=self.max_steps, width=10, font=('Microsoft YaHei', 9))
            self.max_steps_entry.grid(row=0, column=0, sticky=tk.W)
            ttk.Label(max_steps_entry_frame, text="（每个任务最大执行步数）", font=('Microsoft YaHei', 8), foreground='gray').grid(row=0, column=1, padx=(3, 0))
            
            # Base URL变化时自动保存
            url_entry.bind("<KeyRelease>", lambda e: self.on_config_change())
            
            # Model变化时自动保存  
            model_entry.bind("<KeyRelease>", lambda e: self.on_config_change())
            
            # API Key变化时自动保存
            self.apikey_entry.bind("<KeyRelease>", lambda e: self.on_config_change())
            
            # Max Steps变化时自动保存
            self.max_steps_entry.bind("<KeyRelease>", lambda e: self.on_config_change())
            
            # Temperature变化时自动保存
            self.temperature_entry.bind("<KeyRelease>", lambda e: self.on_config_change())
            
            # ADB设备区域
            self.adb_frame = ttk.LabelFrame(self.main_frame, text="📱 ADB设备管理", style='Card.TFrame', padding="8")
            self.adb_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(8, 8))
            self.adb_frame.columnconfigure(1, weight=1)
            
            # ADB控制按钮
            self.adb_control_frame = ttk.Frame(self.adb_frame)
            self.adb_control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
            
            ttk.Button(self.adb_control_frame, text="🔄 刷新设备", command=self.refresh_devices).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(self.adb_control_frame, text="🔗 连接ADB", command=self.connect_adb_device).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(self.adb_control_frame, text="📋 设备详情", command=self.show_device_details).pack(side=tk.LEFT, padx=(0, 8))
            self.remote_desktop_button = ttk.Button(self.adb_control_frame, text="🖥️远程桌面", command=self.open_remote_desktop)
            self.remote_desktop_button.pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(self.adb_control_frame, text="📲 安装ADB键盘", command=self.install_adb_keyboard).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(self.adb_control_frame, text="📱 关注公众号", command=self.open_wechat_qrcode).pack(side=tk.LEFT, padx=(0, 8))
            
            # 设备选择
            ttk.Label(self.adb_frame, text="📱 选择设备:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
            
            device_select_frame = ttk.Frame(self.adb_frame)
            device_select_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(15, 0))
            device_select_frame.columnconfigure(0, weight=1)
            
            self.device_combo = ttk.Combobox(device_select_frame, textvariable=self.selected_device_id, 
                                          state="readonly", font=('Microsoft YaHei', 9))
            self.device_combo.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # 设备选择变化时自动保存配置
            self.device_combo.bind("<<ComboboxSelected>>", lambda e: self.on_device_change())
            
            self.device_status_label = ttk.Label(device_select_frame, text="未检测到设备", 
                                            font=('Microsoft YaHei', 9), foreground='red')
            self.device_status_label.grid(row=0, column=1, padx=(10, 0))
            
            # 初始化设备类型但不自动扫描设备（避免启动时弹出CMD窗口）
            # 用户手动操作时会自动触发设备扫描
            current_device_type = self.device_type.get()
            self._last_device_type = current_device_type  # 设置初始值防止重复扫描
            
            # 只更新界面显示，不扫描设备
            if hasattr(self, 'adb_frame'):
                if hasattr(self, 'adb_control_frame'):
                    # 将中文选项转换为英文值用于内部处理
                    if current_device_type == "安卓":
                        device_type_en = "adb"
                    elif current_device_type == "鸿蒙":
                        device_type_en = "hdc"
                    elif current_device_type == "iOS":
                        device_type_en = "ios"
                    else:
                        device_type_en = "adb"  # 默认
                    
                    # 只更新标题和按钮文本，不执行设备扫描
                    if device_type_en == "hdc":
                        self.adb_frame.config(text="📱 HDC设备管理")
                    elif device_type_en == "ios":
                        self.adb_frame.config(text="🍎 iOS设备管理")
                        if hasattr(self, 'device_status_label'):
                            current_ip = self.ios_device_ip.get()
                            if current_ip and current_ip != "localhost":
                                self.device_status_label.config(text=f"iOS设备IP: {current_ip}")
                            else:
                                self.device_status_label.config(text="iOS设备未配置IP")
                    else:
                        self.adb_frame.config(text="📱 ADB设备管理")
                        if hasattr(self, 'device_status_label'):
                            self.device_status_label.config(text=f"未连接ADB设备")
            
            # 按钮区域
            button_frame = ttk.Frame(self.main_frame)
            button_frame.grid(row=3, column=0, columnspan=3, pady=5)
            
            # 主要操作按钮
            main_buttons = ttk.Frame(button_frame)
            main_buttons.pack(side=tk.LEFT, padx=(0, 20))
            
            self.run_button = ttk.Button(main_buttons, text="🚀 运行", command=self.run_agent, style='Success.TButton')
            self.run_button.grid(row=0, column=0, padx=5)
            
            self.stop_button = ttk.Button(main_buttons, text="⏹️ 停止", command=self.stop_agent, state=tk.DISABLED, style='Danger.TButton')
            self.stop_button.grid(row=0, column=1, padx=5)
            
            # 锁屏密码设置按钮（用于手动设置测试密码）
            self.pwd_button = ttk.Button(main_buttons, text="🔒 自动唤醒/解锁", command=self.open_lock_password_dialog)
            self.pwd_button.grid(row=0, column=2, padx=5)
            
            # 辅助功能按钮
            aux_buttons = ttk.Frame(button_frame)
            aux_buttons.pack(side=tk.LEFT)
            
            ttk.Button(aux_buttons, text="🗑️ 清空", command=self.clear_output).grid(row=0, column=0, padx=5)
            ttk.Button(aux_buttons, text="💾 保存配置", command=self.save_config).grid(row=0, column=1, padx=5)
            ttk.Button(aux_buttons, text="📁 加载配置", command=self.load_config_dialog).grid(row=0, column=2, padx=5)
            
            # 输出区域
            output_frame = ttk.LabelFrame(self.main_frame, text="📋 输出控制台", style='Output.TFrame', padding="5")
            output_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
            output_frame.columnconfigure(0, weight=1)
            output_frame.rowconfigure(0, weight=1)
            self.main_frame.rowconfigure(4, weight=1)
            
            # 主输出文本框（移除行号）
            self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20,
                                                       font=('Microsoft YaHei', 9), bg='#1e1e1e', fg='#ffffff',
                                                       insertbackground='#ffffff')
            self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # 状态栏
            status_frame = ttk.Frame(self.main_frame)
            status_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
            status_frame.columnconfigure(1, weight=1)
            
            self.status_var = tk.StringVar(value="✅ 就绪")
            status_label = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
            status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # 微信公众号推广文字
            wechat_label = ttk.Label(status_frame, text="更多好玩的工具请关注微信公众号：菜芽创作小助手", 
                                   font=('Microsoft YaHei', 8), foreground='#666666')
            wechat_label.grid(row=0, column=1, sticky=tk.N)
            
            # 时间显示
            self.time_var = tk.StringVar(value="")
            time_label = ttk.Label(status_frame, textvariable=self.time_var, relief=tk.SUNKEN, anchor=tk.E, width=25)
            time_label.grid(row=0, column=2, sticky=(tk.E))
            
            # 更新时间
            self.update_time()
            
            # 设备扫描将在配置加载完成后进行，避免重复扫描
            # self.root.after(500, self.async_refresh_devices)  # 注释掉避免重复
            
        except Exception as e:
            print(f"创建完整界面时出错: {e}")
            # 如果失败，至少显示基本界面
            try:
                if hasattr(self, 'startup_label') and self.startup_label.winfo_exists():
                    self.startup_label.config(text="❌ 界面加载失败")
            except tk.TclError:
                # startup_label 可能已经被销毁
                pass
    
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, 'time_var'):
            self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
        
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
        
    def run_agent(self):
        if self.running:
            return
            
        # 获取参数
        base_url = self.base_url.get().strip()
        model = self.model.get().strip()
        apikey = self.apikey.get().strip()
        task = self.task_text.get("1.0", tk.END).strip()
        
        # 验证必要参数
        if not base_url:
            messagebox.showerror("错误", "请输入基础URL")
            return
        if not model:
            messagebox.showerror("错误", "请输入模型名称")
            return
        if not apikey:
            messagebox.showerror("错误", "请输入API密钥")
            return
        if not task:
            messagebox.showerror("错误", "请输入任务描述")
            return
            
        # 设置运行状态和UI
        self.running = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("🔄 正在执行任务...")
        self.clear_output()
        
        # 添加任务到历史记录
        self.add_task_to_history(task)
            
        # 获取设备ID，优先使用环境变量，其次是用户选择
        selected_device = self.env_device_id or self.selected_device_id.get()
        
        # 如果环境变量存在，输出提示信息
        if self.env_device_id:
            self._append_output(f"🔧 使用环境变量设备ID: {self.env_device_id}\n")
        elif selected_device:
            self._append_output(f"📱 使用用户选择设备ID: {selected_device}\n")
        else:
            self._append_output("⚠️ 未指定设备ID，将使用默认设备\n")

            # 对于iOS设备，直接运行，不需要唤醒检测
        if self.device_type.get() == 'iOS':
            self._append_output(f"🍎 准备运行iOS设备任务...\n")
            self.status_var.set("🍎 准备运行iOS任务...")
            self._run_ios_agent(base_url, model, apikey, task)
        else:
            # 异步执行系统检查，避免阻塞界面
            self._run_agent_async(base_url, model, apikey, task, selected_device)
        
    def _run_adb_silent(self, cmd, timeout=10):
        """静默执行ADB命令，避免弹窗"""
        import os
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=creation_flags)

    def _run_ios_agent(self, base_url, model, apikey, task):
        """运行iOS设备代理"""
        import sys
        import os
        import threading
        import traceback
        
        try:
            # 获取iOS设备IP地址
            ios_ip = self.ios_device_ip.get()
            if not ios_ip:
                messagebox.showerror("错误", "请先设置iOS设备IP地址")
                return
            
            # 构建iOS脚本路径
            ios_script_path = os.path.join(os.path.dirname(__file__), "ios.py")
            if not os.path.exists(ios_script_path):
                self._append_output("❌ 未找到ios.py脚本文件\n")
                messagebox.showerror("错误", "未找到ios.py脚本文件")
                return
            
            # 使用模块导入的方式，避免创建新进程和新窗口
            def run_ios_in_thread():
                try:
                    self._append_output(f"🍎 开始执行iOS任务...\n")
                    
                    # 模拟命令行参数
                    old_argv = sys.argv[:]
                    sys.argv = [
                        ios_script_path,
                        "--base-url", base_url,
                        "--model", model,
                        "--apikey", apikey,  # 修正参数名
                        "--wda-url", f"http://{ios_ip}:8100",
                        task
                    ]
                    
                    # 重定向stdout和stderr到GUI
                    import io
                    from contextlib import redirect_stdout, redirect_stderr
                    
                    # 创建输出捕获器
                    class OutputCapture:
                        def __init__(self, append_func):
                            self.append_func = append_func
                            self.buffer = ""
                            
                        def write(self, text):
                            # 立即写入所有文本，包括换行符
                            if text:
                                self.append_func(text)
                                self.buffer += text
                                
                        def flush(self):
                            # 刷新缓冲区（这里不需要，因为我们立即写入）
                            pass
                    
                    output_capture = OutputCapture(self._append_output)
                    
                    # 在新线程中执行ios.py并捕获输出
                    with redirect_stdout(output_capture), redirect_stderr(output_capture):
                        # 执行ios.py的main逻辑
                        import ios
                        # 显式调用main函数，因为import不会自动执行
                        ios.main()
                    
                    # 恢复原始命令行参数
                    sys.argv = old_argv
                    
                    self._append_output(f"🍎 iOS任务执行完成\n")
                    success = True
                    
                except Exception as e:
                    self._append_output(f"❌ iOS任务执行失败: {str(e)}\n")
                    self._append_output(f"详细错误: {traceback.format_exc()}\n")
                    success = False
                finally:
                    # 在主线程中更新UI状态
                    return_code = 0 if success else -1
                    self.root.after(0, lambda: self._on_process_finished(return_code))
            
            # 在新线程中运行iOS任务，避免阻塞GUI
            thread = threading.Thread(target=run_ios_in_thread, daemon=True)
            thread.start()
            
            # 设置虚拟进程对象用于停止功能
            class DummyProcess:
                def __init__(self, thread):
                    self.thread = thread
                    self.returncode = None
                    
                def poll(self):
                    if not self.thread.is_alive():
                        return 0
                    return None
                    
                def terminate(self):
                    # 无法真正终止，但设置停止标志
                    self.returncode = -2
                    
                def wait(self, timeout=None):
                    self.thread.join(timeout=timeout)
                    return self.returncode
                    
                def kill(self):
                    self.returncode = -2
                
                # 添加模拟的stdout属性，避免访问错误
                @property
                def stdout(self):
                    """模拟stdout，返回一个类似文件的对象"""
                    class DummyStdout:
                        def readline(self):
                            return ""  # 返回空字符串，表示没有更多输出
                    return DummyStdout()
            
            self.process = DummyProcess(thread)
            
        except Exception as e:
            self._append_output(f"❌ 启动iOS代理失败: {str(e)}\n")
            messagebox.showerror("错误", f"启动iOS代理失败: {str(e)}")
            self.running = False
            self.run_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("✅ 就绪")

    def _on_process_finished(self, return_code):
        """处理进程结束"""
        self.running = False
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if return_code == 0:
            self.status_var.set("✅ 任务执行完成")
            self._append_output("\n✅ 任务执行完成\n")
        else:
            self.status_var.set("⚠️ 任务执行结束")
            self._append_output(f"\n⚠️ 任务执行结束，返回码: {return_code}\n")

    def _run_agent_async(self, base_url, model, apikey, task, selected_device):
        """异步执行代理，避免阻塞界面"""
        import threading
        import time
        
        # 显示开始信息
        self._append_output("🚀 正在准备运行环境...\n")
        self.status_var.set("🔄 准备中...")
        
        # 在后台线程中执行所有检查
        def prepare_and_run():
            try:
                # 1. 设备唤醒检测（如果是安卓或鸿蒙）
                if self.device_type.get() != 'iOS':
                    import os
                    tool_name = 'adb' if self.device_type.get() == '安卓' else 'hdc'
                    self.root.after(0, lambda: self._append_output(f"🔌 检测设备状态（使用: {tool_name}）...\n"))
                    self.root.after(0, lambda: self.status_var.set("🔌 检测设备..."))
                    
                    # 使用默认滑动解锁坐标，可根据设备分辨率调整
                    pwd = os.getenv('PHONE_AGENT_LOCK_PASSWORD', '')
                    ok = ensure_awake_and_unlocked(adb=tool_name, swipe=(300, 1000, 300, 300), password=pwd if pwd else None)
                    
                    self.root.after(0, lambda: self._append_output(
                        "✅ 设备已唤醒或已解锁\n" if ok else "⚠️ 无法唤醒设备，继续尝试运行\n"))
                
                # 2. 在主线程中调用同步的运行函数
                self.root.after(0, lambda: self._run_agent_direct(base_url, model, apikey, task, selected_device))
                
            except Exception as e:
                self.root.after(0, lambda: self._append_output(f"❌ 准备失败: {str(e)}\n"))
                self.root.after(0, lambda: self.status_var.set("❌ 准备失败"))
        
        # 启动准备线程
        thread = threading.Thread(target=prepare_and_run, daemon=True)
        thread.start()

    def _run_agent_direct(self, base_url, model, apikey, task, selected_device):
        """直接运行代理（打包环境）"""
        # 导入必要模块
        from phone_agent.agent import PhoneAgent, AgentConfig
        from phone_agent.model import ModelConfig
        from phone_agent.device_factory import DeviceType, set_device_type
        # 从main.py导入检查函数
        import main
        
        # 使用线程安全的输出函数 - 移到try块外部
        def safe_output(text):
            if text:
                # 直接插入到GUI，不做任何格式化处理
                self.root.after(0, self._insert_direct_text, text)
        
        try:
            
            # 获取当前设备类型
            device_type_value = self.device_type.get()
            if device_type_value == "安卓":
                device_type = DeviceType.ADB
                device_type_str = "adb"
            elif device_type_value == "iOS":
                device_type = None  # iOS使用不同的逻辑
                device_type_str = "ios"
            else:
                device_type = DeviceType.HDC
                device_type_str = "hdc"
            set_device_type(device_type)
            safe_output(f"🔗 设备类型: {device_type_str.upper()}\n")
            
            # 解析设备ID（必须在检查系统要求之前）
            device_id = None
            if selected_device:
                device_id = selected_device.split(' ')[0]
            
            # 并行执行系统检查，提高速度
            safe_output("🔍 并行检查系统要求和API连通性...\n")
            
            import concurrent.futures
            
            # 创建线程池并行执行检查
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 提交两个检查任务
                system_check_future = executor.submit(main.check_system_requirements, device_type, device_id)
                api_check_future = executor.submit(main.check_model_api, base_url, model, apikey)
                
                # 等待两个检查完成
                system_ok = system_check_future.result()
                api_ok = api_check_future.result()
                
                # 检查结果
                if not system_ok:
                    device_text = "HDC" if device_type_str == "hdc" else "ADB"
                    safe_output(f"❌ 系统要求检查失败，请检查{device_text}和设备连接，以及相关键盘设置\n")
                    self.root.after(0, self._process_finished, -1)
                    return
                
                if not api_ok:
                    safe_output("❌ 模型API检查失败，请检查网络连接和API配置\n")
                    self.root.after(0, self._process_finished, -1)
                    return
                
                safe_output("✅ 系统检查和API连通性验证通过\n")
            

            
            # 在打包环境中设置subprocess创建标志，避免弹窗
            import subprocess
            import os
            
            # 设置环境变量，让main.py相关函数能够获取到设备ID
            if device_id:
                os.environ["PHONE_AGENT_DEVICE_ID"] = device_id
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                original_popen = subprocess.Popen
                def patched_popen(*args, **kwargs):
                    if 'creationflags' not in kwargs and os.name == 'nt':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    return original_popen(*args, **kwargs)
                subprocess.Popen = patched_popen
            
            # 创建代理实例
            safe_output("🔧 初始化PhoneAgent...\n")
            
            # 创建模型配置
            model_config = ModelConfig(
                base_url=base_url,
                model_name=model,
                api_key=apikey,
                temperature=float(self.temperature.get() or 0.0)
            )
            
            # 获取打包环境中的ADB/HDC路径
            import sys
            if getattr(sys, 'frozen', False):
                # 在打包环境中，ADB/HDC文件在exe所在目录
                import os
                exe_dir = os.path.dirname(sys.executable)
                # 根据设备类型选择正确的可执行文件
                exe_name = 'hdc.exe' if device_type_str == 'hdc' else 'adb.exe'
                adb_path = os.path.join(exe_dir, exe_name)
                if not os.path.exists(adb_path):
                    # 尝试在当前目录查找
                    import tempfile
                    adb_path = exe_name
            else:
                adb_path = 'hdc.exe' if device_type_str == 'hdc' else 'adb.exe'
            

            
            # 创建代理配置
            agent_config = AgentConfig(
                device_id=device_id,
                verbose=True,
                max_steps=int(self.max_steps.get() or os.getenv("PHONE_AGENT_MAX_STEPS", "200"))  # 优先使用GUI设置
            )
            
            # 创建并运行PhoneAgent
            safe_output("🚀 开始执行任务...\n")
            agent = PhoneAgent(
                model_config=model_config,
                agent_config=agent_config
            )
            
            # 设置ADB/HDC路径（如果需要）
            device_tool_name = "HDC" if device_type_str == 'hdc' else "ADB"
            safe_output(f"🔧 {device_tool_name}路径: {adb_path}\n")
            
            # 在单独线程中执行任务，避免阻塞GUI
            def execute_task():
                try:
                    safe_output(f"📋 开始执行: {task}\n")
                    
                    # 重定向print输出到GUI - 保持原始格式
                    import sys
                    import threading
                    original_stdout = sys.stdout
                    
                    class StreamOutputCollector:
                        """流式输出收集器 - 重新组合字符为完整输出"""
                        def __init__(self, output_func, stop_check_func):
                            self.output_func = output_func
                            self.stop_check_func = stop_check_func
                            self.char_buffer = []
                            self.last_output_time = 0
                            
                        def write(self, text):
                            # 检查是否需要停止
                            if not self.stop_check_func():
                                return
                            
                            if text:
                                import time
                                current_time = time.time()
                                
                                # 收集字符
                                for char in text:
                                    self.char_buffer.append(char)
                                
                                # 如果遇到换行符或者超过一定时间，输出缓冲内容
                                if '\n' in text or (current_time - self.last_output_time > 0.05 and len(self.char_buffer) > 10):
                                    if self.char_buffer:
                                        output_text = ''.join(self.char_buffer)
                                        self.output_func(output_text)
                                        self.char_buffer = []
                                        self.last_output_time = current_time
                                    
                        def flush(self):
                            if self.char_buffer:
                                output_text = ''.join(self.char_buffer)
                                self.output_func(output_text)
                                self.char_buffer = []
                    
                    # 检查是否继续运行
                    def is_running():
                        return self.running
                    
                    # 设置输出重定向
                    sys.stdout = StreamOutputCollector(safe_output, is_running)
                    
                    try:
                        # 手动执行步骤，以便检查停止标志
                        safe_output("🔄 开始步骤化执行...\n")
                        
                        # 第一步
                        if not self.running:
                            safe_output("🛑 任务被用户停止\n")
                            return
                            
                        result = agent.step(task)
                        safe_output(f"📊 步骤 1: {result.message}\n")
                        
                        if result.finished:
                            safe_output("✅ 任务提前完成\n")
                            sys.stdout = original_stdout
                            self.root.after(0, self._process_finished, 0)
                            return
                        
                        # 继续执行步骤
                        step_count = 2
                        while self.running and step_count <= agent_config.max_steps:
                            if not self.running:
                                safe_output("🛑 任务被用户停止\n")
                                break
                                
                            result = agent.step()
                            safe_output(f"📊 步骤 {step_count}: {result.message}\n")
                            
                            if result.finished:
                                safe_output("✅ 任务执行完成\n")
                                break
                                
                            step_count += 1
                            
                        if step_count > agent_config.max_steps:
                            safe_output("⚠️ 达到最大步数限制\n")
                            
                    finally:
                        # 恢复原始输出
                        sys.stdout = original_stdout
                        
                    if self.running:
                        self.root.after(0, self._process_finished, 0)
                    else:
                        self.root.after(0, lambda: self._process_finished(-2))  # 自定义停止代码
                    
                except Exception as e:
                    safe_output(f"❌ 任务执行出错: {str(e)}\n")
                    # 恢复原始输出（以防异常时没有恢复）
                    if 'original_stdout' in locals():
                        sys.stdout = original_stdout
                    self.root.after(0, self._process_finished, -1)
            
            # 启动任务执行线程
            threading.Thread(target=execute_task, daemon=True).start()
            
        except ImportError as e:
            safe_output(f"❌ 导入phone_agent模块失败: {str(e)}\n")
            self.root.after(0, self._process_finished, -1)
        except Exception as e:
            safe_output(f"❌ 运行代理时出错: {str(e)}\n")
            self.root.after(0, self._process_finished, -1)
    
    def _run_command(self, cmd):
        try:
            # 切换到脚本所在目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 设置环境变量，解决Unicode编码问题
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'  # 确保无缓冲输出
            
            self.process = subprocess.Popen(
                cmd,
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,  # 使用字节模式以便更好地控制缓冲
                bufsize=0,   # 无缓冲
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 实时读取输出 - 改进的读取方式
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                try:
                    # 解码字节为字符串
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    if decoded_line:
                        self.root.after(0, self._append_output, decoded_line + '\n')
                except Exception as e:
                    self.root.after(0, self._append_output, f"解码错误: {str(e)}\n")
                    
            # 等待进程结束
            return_code = self.process.wait()
            
            self.root.after(0, self._process_finished, return_code)
            
        except Exception as e:
            self.root.after(0, self._append_output, f"错误: {str(e)}\n")
            self.root.after(0, self._process_finished, -1)
            
    def _append_output(self, text):
        # 如果传入的是空文本，直接返回
        if not text:
            return
        
        # 检查output_text是否已创建
        if not hasattr(self, 'output_text'):
            return
        
        # 直接插入文本，不做额外格式化（因为输出已经带有时间戳）
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        
    def _insert_direct_text(self, text):
        """直接插入文本，完全保持原始格式"""
        if text and hasattr(self, 'output_text'):  # 插入所有内容，包括空格和空行
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
        

        
    def toggle_apikey_visibility(self):
        """切换API密钥显示/隐藏"""
        if self.apikey_entry.cget('show') == '*':
            self.apikey_entry.config(show='')
            self.show_apikey_btn.config(text='🙈')
        else:
            self.apikey_entry.config(show='*')
            self.show_apikey_btn.config(text='👁️')
            
    def save_config(self):
        """保存配置到文件"""
        try:
            # 验证温度值
            if not self.validate_temperature():
                return  # 如果温度值无效，不保存配置
                
            config = {
                'base_url': self.base_url.get(),
                'model': self.model.get(),
                'apikey': self.apikey.get(),
                'task': self.task_text.get("1.0", tk.END).strip(),
                'max_steps': int(self.max_steps.get() or 200),
                'temperature': float(self.temperature.get() or 0.0),
                'device_type': (lambda: {
                    "安卓": "adb", 
                    "iOS": "ios", 
                    "鸿蒙": "hdc"
                }.get(self.device_type.get(), "adb"))(),
                'selected_device': self.selected_device_id.get(),  # 保存用户选择的设备ID（不是环境变量）
                'remote_connection': getattr(self, 'last_remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'wireless_pair': getattr(self, 'last_wireless_pair', {
                    'pair_address': '10.10.10.100:41717',
                    'connect_address': '10.10.10.100:5555'
                }),
                'legacy_wireless': getattr(self, 'last_legacy_wireless', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'ios_device_ip': getattr(self, 'ios_device_ip', None).get() if hasattr(self, 'ios_device_ip') else "localhost"
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("成功", "配置已保存到 gui_config.json")
            self.status_var.set("✅ 配置已保存")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
            self.status_var.set("❌ 保存配置失败")
    
    def save_config_silent(self):
        """静默保存配置到文件，不显示消息"""
        try:
            # 验证温度值，如果无效则跳过保存
            try:
                temp_value = float(self.temperature.get() or 0.0)
                if temp_value < 0.0 or temp_value > 1.0:
                    return  # 温度值无效，跳过保存
            except ValueError:
                return  # 温度值不是有效数字，跳过保存
                
            # 转换设备类型
            device_type_str = self.device_type.get()
            if device_type_str == "安卓":
                device_type_value = "adb"
            elif device_type_str == "iOS":
                device_type_value = "ios"
            else:
                device_type_value = "hdc"
                
            config = {
                'base_url': self.base_url.get(),
                'model': self.model.get(),
                'apikey': self.apikey.get(),
                'task': self.task_text.get("1.0", tk.END).strip(),
                'max_steps': int(self.max_steps.get() or 200),
                'temperature': temp_value,
                'device_type': device_type_value,
                'selected_device': self.selected_device_id.get(),  # 保存用户选择的设备ID（不是环境变量）
                'remote_connection': getattr(self, 'last_remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'wireless_pair': getattr(self, 'last_wireless_pair', {
                    'pair_address': '10.10.10.100:41717',
                    'connect_address': '10.10.10.100:5555'
                }),
                'legacy_wireless': getattr(self, 'last_legacy_wireless', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'ios_device_ip': getattr(self, 'ios_device_ip', None).get() if hasattr(self, 'ios_device_ip') else "localhost"
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
        except Exception:
            pass  # 静默忽略错误

    def open_lock_password_dialog(self):
        """弹出对话框用于设置自动唤醒/解锁密码（用于运行时自动尝试解锁设备）。"""
        try:
            # 使用优化的居中窗口创建方法
            dialog = self.create_centered_toplevel(self.root, "设置自动唤醒/解锁密码", 480, 180, resizable=False)
            dialog.transient(self.root)
            dialog.grab_set()

            # 使弹窗背景与主窗口一致，并优化说明文案
            try:
                main_bg = self.root.cget('bg')
            except Exception:
                main_bg = '#f5f7fa'

            try:
                dialog.configure(bg=main_bg)
            except Exception:
                pass

            desc = ("说明：此密码将在点击“运行”时被程序读取，用于自动唤醒并输入解锁密码。"
                    " 若不希望保存到配置文件，可留空并点击“保存”。")
            tk.Label(dialog, text=desc, bg=main_bg, fg='#333333', wraplength=420, justify=tk.LEFT,
                     font=('Microsoft YaHei', 9)).grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 6))

            # 使用 tk 原生控件以保证背景色一致
            pwd_var = tk.StringVar(value='')
            tk.Label(dialog, text="自动唤醒/解锁密码:", bg=main_bg, fg='#222222', font=('Microsoft YaHei', 10)).grid(row=1, column=0, padx=8, pady=6, sticky=tk.E)
            pwd_entry = tk.Entry(dialog, textvariable=pwd_var, show='*', width=30, bg='white', fg='#000000', relief=tk.SUNKEN)
            pwd_entry.grid(row=1, column=1, padx=8, pady=6, sticky=tk.W)

            show_var = tk.BooleanVar(value=False)
            def toggle_show():
                pwd_entry.config(show='' if show_var.get() else '*')
            tk.Checkbutton(dialog, text='显示密码', variable=show_var, command=toggle_show, bg=main_bg).grid(row=2, column=1, sticky=tk.W, padx=8)

            btn_frame = tk.Frame(dialog, bg=main_bg)
            btn_frame.grid(row=3, column=0, columnspan=2, pady=(8, 12))

            def on_save():
                pwd = pwd_var.get().strip()
                self.save_lock_password(pwd)
                try:
                    dialog.destroy()
                except Exception:
                    pass

            tk.Button(btn_frame, text='保存并应用', command=on_save, bg='#2E86AB', fg='white').pack(side=tk.LEFT, padx=6)
            tk.Button(btn_frame, text='取消', command=dialog.destroy).pack(side=tk.LEFT, padx=6)

            # 居中显示
            try:
                self.center_window(dialog, width=480, height=180)
            except Exception:
                pass

        except Exception as e:
            self._append_output(f"打开密码设置对话框失败: {str(e)}\n")

    def save_lock_password(self, password: str):
        """保存锁屏密码到环境变量并写入配置文件（便于下次自动加载）。"""
        try:
            import os, json
            # 设置环境变量（仅当前进程），PhoneAgent 启动时会读取此环境变量
            if password:
                os.environ['PHONE_AGENT_LOCK_PASSWORD'] = password
            elif 'PHONE_AGENT_LOCK_PASSWORD' in os.environ:
                del os.environ['PHONE_AGENT_LOCK_PASSWORD']

            # 写入到配置文件以持久化（如果存在其它配置字段则保留）
            config = {}
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
            except Exception:
                config = {}

            if password:
                config['lock_password'] = password
            else:
                config.pop('lock_password', None)

            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            # 更新界面状态和输出（说明用途）
            if password:
                self._append_output('🔒 自动唤醒/解锁密码已保存 — 程序将在运行时使用此密码尝试解锁设备。\n')
                self.status_var.set('✅ 自动唤醒/解锁密码已设置')
            else:
                self._append_output('🔓 自动唤醒/解锁密码已移除\n')
                self.status_var.set('✅ 自动唤醒/解锁密码已移除')

        except Exception as e:
            self._append_output(f"保存锁屏密码失败: {str(e)}\n")
            
    def load_config(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.base_url.set(config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4'))
                self.model.set(config.get('model', 'autoglm-phone'))
                self.apikey.set(config.get('apikey', 'your-bigmodel-api-key'))
                task_text = config.get('task', '输入你想要执行的任务，例如：打开美团搜索附近的火锅店')
                self.task.set(task_text)
                
                # 如果界面已创建，更新任务文本框
                if hasattr(self, 'task_text'):
                    self.task_text.delete("1.0", tk.END)
                    self.task_text.insert("1.0", task_text)
                
                # 加载temperature参数
                self.temperature.set(str(config.get('temperature', 0.0)))
                
                # 恢复选中的设备，优先使用环境变量
                selected_device = self.env_device_id or config.get('selected_device', '')
                if selected_device and hasattr(self, 'selected_device_id'):
                    self.selected_device_id.set(selected_device)
                
                # 加载远程连接配置
                self.last_remote_connection = config.get('remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                })
                
            # 加载无线调试配对配置
            self.last_wireless_pair = config.get('wireless_pair', {
                'pair_address': '10.10.10.100:41717',
                'connect_address': '10.10.10.100:5555'
            })
            
            # 加载Android 10及以下无线调试配置
            self.last_legacy_wireless = config.get('legacy_wireless', {
                'ip': '192.168.1.100',
                'port': '5555'
            })
            
            # 加载锁屏密码配置
            lock_password = config.get('lock_password', '')
            if lock_password:
                import os
                os.environ['PHONE_AGENT_LOCK_PASSWORD'] = lock_password
                self._append_output(f"🔒 已加载锁屏密码配置\n")
            
            self.status_var.set("✅ 配置已加载")
                
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
            
    def load_config_dialog(self):
        """通过文件对话框加载配置"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择配置文件",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.base_url.set(config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4'))
                self.model.set(config.get('model', 'autoglm-phone'))
                self.apikey.set(config.get('apikey', 'your-bigmodel-api-key'))
                task_text = config.get('task', '输入你想要执行的任务，例如：打开美团搜索附近的火锅店')
                self.task.set(task_text)
                
                # 更新任务文本框
                self.task_text.delete("1.0", tk.END)
                self.task_text.insert("1.0", task_text)
                
                # 加载temperature参数
                self.temperature.set(str(config.get('temperature', 0.0)))
                
                # 恢复选中的设备，优先使用环境变量
                selected_device = self.env_device_id or config.get('selected_device', '')
                if selected_device:
                    self.selected_device_id.set(selected_device)
                
                # 加载远程连接配置
                self.last_remote_connection = config.get('remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                })
                
                # 加载无线调试配对配置
                self.last_wireless_pair = config.get('wireless_pair', {
                    'pair_address': '10.10.10.100:41717',
                    'connect_address': '10.10.10.100:5555'
                })
                
                # 加载锁屏密码配置
                lock_password = config.get('lock_password', '')
                if lock_password:
                    import os
                    os.environ['PHONE_AGENT_LOCK_PASSWORD'] = lock_password
                    self._append_output(f"🔒 已从文件加载锁屏密码配置\n")
                
                messagebox.showinfo("成功", "配置已成功加载")
                self.status_var.set("✅ 从文件加载配置")
                
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {str(e)}")
            self.status_var.set("❌ 加载配置失败")
    
    def on_config_change(self):
        """配置变化时自动保存（静默保存）"""
        try:
            self.save_config_silent()
        except Exception:
            pass  # 静默忽略错误，不影响用户体验
    
    def validate_temperature(self):
        """验证温度值是否在0.0-1.0范围内"""
        try:
            temp_value = float(self.temperature.get())
            if temp_value < 0.0 or temp_value > 1.0:
                messagebox.showwarning("温度值错误", "温度值必须在0.0-1.0之间\n请重新输入有效的温度值")
                # 重置为默认值0.0
                self.temperature.set("0.0")
                return False
            return True
        except ValueError:
            messagebox.showwarning("温度值错误", "请输入有效的数字\n温度值必须在0.0-1.0之间")
            # 重置为默认值0.0
            self.temperature.set("0.0")
            return False
        
    def _process_finished(self, return_code):
        self.running = False
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self._append_output(f"{'='*60}\n")
        
        if return_code == 0:
            self.status_var.set("✅ 执行成功")
            self._append_output("✅ 程序执行成功完成。\n")
        elif return_code == -2:
            self.status_var.set("🛑 任务已停止")
            self._append_output("🛑 任务被用户停止。\n")
        else:
            self.status_var.set(f"❌ 执行失败 (退出代码: {return_code})")
            self._append_output(f"❌ 程序执行失败，退出代码: {return_code}\n")
            
        self.process = None
        
    def stop_agent(self):
        if self.running:
            try:
                self.running = False  # 设置停止标志
                self._append_output("🛑 正在停止任务...\n")
                
                # 由于直接调用方式没有进程可以终止，只能通过标志位停止
                # 实际的停止会在下一次循环检查时生效
                
                # 立即更新UI状态
                self.run_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.status_var.set("🛑 任务已停止")
                
                self._append_output("✅ 停止信号已发送\n")
                
            except Exception as e:
                self._append_output(f"停止任务时出错: {str(e)}\n")
                
    def clear_output(self):
        if hasattr(self, 'output_text'):
            self.output_text.delete("1.0", tk.END)
        if hasattr(self, 'status_var'):
            self.status_var.set("✅ 输出已清空")
    
    def _run_adb_silent(self, cmd, timeout=10):
        """静默运行ADB命令，不显示控制台窗口"""
        try:
            # 在Windows上隐藏控制台窗口
            if os.name == 'nt':
                # 设置CREATE_NO_WINDOW标志来隐藏控制台窗口
                creationflags = subprocess.CREATE_NO_WINDOW
            else:
                creationflags = 0
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=timeout, creationflags=creationflags)
            return result
        except subprocess.TimeoutExpired:
            # 返回一个模拟的结果对象
            class TimeoutResult:
                def __init__(self):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = f"Command timed out after {timeout} seconds"
            return TimeoutResult()
        except Exception as e:
            # 返回一个模拟的结果对象
            class ErrorResult:
                def __init__(self, error):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = str(error)
            return ErrorResult(str(e))
    
    def _run_hdc_silent(self, cmd, timeout=10):
        """静默运行HDC命令，不显示控制台窗口"""
        try:
            # 在Windows上隐藏控制台窗口
            if os.name == 'nt':
                # 设置CREATE_NO_WINDOW标志来隐藏控制台窗口
                creationflags = subprocess.CREATE_NO_WINDOW
            else:
                creationflags = 0
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=timeout, creationflags=creationflags)
            return result
        except subprocess.TimeoutExpired:
            # 返回一个模拟的结果对象
            class TimeoutResult:
                def __init__(self):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = f"Command timed out after {timeout} seconds"
            return TimeoutResult()
        except Exception as e:
            # 返回一个模拟的结果对象
            class ErrorResult:
                def __init__(self, error):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = str(error)
            return ErrorResult(str(e))
    # ADB相关方法
    def async_refresh_devices(self):
        """异步刷新ADB设备列表，避免阻塞界面"""
        # 在后台线程中执行设备扫描
        threading.Thread(target=self._background_refresh_devices, daemon=True).start()
        
        # 立即显示"正在扫描"状态
        if hasattr(self, 'device_status_label'):
            self.device_status_label.config(text="🔄 正在扫描设备...", foreground='blue')
            
    def _background_refresh_devices(self):
        """后台线程中刷新设备列表"""
        try:
            # 获取当前设备类型
            device_type = self.device_type.get()
            device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
            device_text = "HDC" if device_type_en == "hdc" else "ADB"
            
            # 在后台线程中执行对应命令
            if device_type_en == "hdc":
                result = self._run_hdc_silent(['hdc', 'list', 'targets'])
            else:
                result = self._run_adb_silent(['adb', 'devices'])
            
            if result.returncode == 0:
                self.connected_devices = self._parse_device_list(result.stdout, device_type_en)
                # 在主线程中更新界面
                self.root.after(0, self._update_device_display)
            else:
                self.root.after(0, lambda: self._append_output(f"❌ {device_text}命令执行失败\n"))
                if hasattr(self, 'device_status_label'):
                    self.root.after(0, lambda: self.device_status_label.config(text=f"{device_text}错误", foreground='red'))
                    
        except subprocess.TimeoutExpired:
            self.root.after(0, lambda: self._append_output(f"❌ {device_text}命令超时\n"))
            if hasattr(self, 'device_status_label'):
                self.root.after(0, lambda: self.device_status_label.config(text=f"{device_text}超时", foreground='red'))
        except FileNotFoundError:
            tool_name = "HDC" if device_type_en == "hdc" else "Android SDK (ADB)"
            self.root.after(0, lambda: self._append_output(f"❌ 未找到{device_text}，请检查{tool_name}是否安装\n"))
            if hasattr(self, 'device_status_label'):
                self.root.after(0, lambda: self.device_status_label.config(text=f"{device_text}未安装", foreground='red'))
        except Exception as e:
            self.root.after(0, lambda: self._append_output(f"❌ 扫描设备失败: {str(e)}\n"))
            if hasattr(self, 'device_status_label'):
                self.root.after(0, lambda: self.device_status_label.config(text="扫描失败", foreground='red'))
                
    def refresh_devices(self):
        """刷新设备列表（ADB或HDC）"""
        try:
            device_type = self.device_type.get()
            device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
            device_text = "HDC" if device_type_en == "hdc" else "ADB"
            self._append_output(f"🔍 正在扫描{device_text}设备...\n")
            
            # 获取设备列表
            if device_type_en == "hdc":
                result = self._run_hdc_silent(['hdc', 'list', 'targets'])
            else:
                result = self._run_adb_silent(['adb', 'devices'])
            
            if result.returncode == 0:
                self.connected_devices = self._parse_device_list(result.stdout, device_type_en)
                self._update_device_display()
            else:
                self._append_output(f"❌ {device_text}命令执行失败\n")
                self.device_status_label.config(text=f"{device_text}错误", foreground='red')
                
        except subprocess.TimeoutExpired:
            self._append_output(f"❌ {device_text}命令超时\n")
            self.device_status_label.config(text=f"{device_text}超时", foreground='red')
        except FileNotFoundError:
            tool_name = "HDC" if device_type_en == "hdc" else "Android SDK (ADB)"
            self._append_output(f"❌ 未找到{device_text}，请检查{tool_name}是否安装\n")
            self.device_status_label.config(text=f"{device_text}未安装", foreground='red')
        except Exception as e:
            self._append_output(f"❌ 扫描设备失败: {str(e)}\n")
            self.device_status_label.config(text="扫描失败", foreground='red')
            
    def _parse_device_list(self, output, device_type="adb"):
        """解析设备列表输出（ADB或HDC）"""
        devices = []
        if not output:
            return devices
        
        lines = output.strip().split('\n')
        
        if device_type == "hdc":
            # HDC格式：设备ID
            for line in lines:
                line = line.strip()
                if line and not line.startswith('[Empty]'):
                    devices.append({
                        'id': line,
                        'status': 'device',
                        'info': self._get_device_info(line, device_type) if True else None
                    })
        else:
            # ADB格式：设备ID\t状态
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        device_id = parts[0].strip()
                        status = parts[1].strip()
                        devices.append({
                            'id': device_id,
                            'status': status,
                            'info': self._get_device_info(device_id, device_type) if status == 'device' else None
                        })
                    
        return devices
        
    def _get_device_info(self, device_id, device_type="adb"):
        """获取设备详细信息（ADB或HDC）"""
        try:
            info = {}
            
            if device_type == "hdc":
                # HDC设备信息获取
                # 获取设备型号
                model_result = self._run_hdc_silent(['hdc', '-t', device_id, 'shell', 'param', 'get', 'const.product.model'], timeout=5)
                if model_result.returncode == 0:
                    info['model'] = model_result.stdout.strip() if model_result.stdout else ''
                    
                # 获取系统版本
                version_result = self._run_hdc_silent(['hdc', '-t', device_id, 'shell', 'param', 'get', 'const.product.software.version'], timeout=5)
                if version_result.returncode == 0:
                    info['os_version'] = version_result.stdout.strip() if version_result.stdout else ''
                    
                # 获取设备制造商
                manufacturer_result = self._run_hdc_silent(['hdc', '-t', device_id, 'shell', 'param', 'get', 'const.product.manufacturer'], timeout=5)
                if manufacturer_result.returncode == 0:
                    info['manufacturer'] = manufacturer_result.stdout.strip() if manufacturer_result.stdout else ''
            else:
                # ADB设备信息获取
                # 获取设备型号
                model_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'], timeout=5)
                if model_result.returncode == 0:
                    info['model'] = model_result.stdout.strip() if model_result.stdout else ''
                    
                # 获取Android版本
                version_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'], timeout=5)
                if version_result.returncode == 0:
                    info['android_version'] = version_result.stdout.strip() if version_result.stdout else ''
                    
                # 获取设备制造商
                manufacturer_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.manufacturer'], timeout=5)
                if manufacturer_result.returncode == 0:
                    info['manufacturer'] = manufacturer_result.stdout.strip() if manufacturer_result.stdout else ''
                
                # 获取IP地址
                ip_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'ip', 'addr', 'show', 'wlan0'], timeout=5)
                if ip_result.returncode == 0 and ip_result.stdout:
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_result.stdout)
                    if ip_match:
                        info['ip'] = ip_match.group(1)
                    
            return info
            
        except Exception as e:
            self._append_output(f"⚠️ 获取设备 {device_id} 信息失败: {str(e)}\n")
            return None
            
    def _update_device_display(self):
        """更新设备显示"""
        if self.connected_devices:
            # 更新下拉框
            device_options = []
            device_ids = []
            env_device_index = -1
            
            for device in self.connected_devices:
                if device['status'] == 'device':
                    display_name = device['id']
                    device_ids.append(device['id'])
                    if device['info'] and 'model' in device['info']:
                        display_name += f" ({device['info']['model']})"
                    device_options.append(display_name)
                    
                    # 检查是否匹配环境变量设备ID
                    if self.env_device_id and device['id'] == self.env_device_id:
                        env_device_index = len(device_options) - 1
                    
            self.device_combo['values'] = device_options
            
            if device_options:
                # 如果用户已经有选择，保持用户选择；否则使用环境变量（如果存在且有效）
                current_selection = self.selected_device_id.get()
                
                if current_selection and current_selection in device_ids:
                    # 保持用户当前的选择
                    index = device_ids.index(current_selection)
                    self.device_combo.current(index)
                    self.device_status_label.config(text=f"已连接 {len(device_options)} 台设备 (用户选择: {current_selection})", foreground='green')
                elif env_device_index >= 0:
                    # 用户没有选择或选择无效，使用环境变量
                    self.device_combo.current(env_device_index)
                    self.selected_device_id.set(device_ids[env_device_index])
                    self.device_status_label.config(text=f"已连接 {len(device_options)} 台设备 (环境变量: {self.env_device_id})", foreground='blue')
                else:
                    # 默认选择第一个设备
                    self.device_combo.current(0)
                    if self.env_device_id:
                        self.device_status_label.config(text=f"已连接 {len(device_options)} 台设备 (环境变量设备 {self.env_device_id} 未找到)", foreground='orange')
                    else:
                        self.device_status_label.config(text=f"已连接 {len(device_options)} 台设备", foreground='green')
        else:
            self.device_combo['values'] = []
            self.device_combo.set("")
            # 如果环境变量存在但未找到设备，显示特殊状态
            if self.env_device_id:
                self.device_status_label.config(text=f"环境变量设备 {self.env_device_id} 未连接", foreground='orange')
            else:
                self.device_status_label.config(text="未检测到设备", foreground='red')
            
        device_type = self.device_type.get()
        device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
        device_text = "HDC" if device_type_en == "hdc" else "ADB"
        
        self._append_output(f"📱 {device_text}扫描完成，发现 {len(self.connected_devices)} 台设备\n")
        if self.env_device_id:
            self._append_output(f"🔧 环境变量 PHONE_AGENT_DEVICE_ID: {self.env_device_id}\n")

    def on_device_change(self):
        """处理设备选择变化"""
        selected_device = self.selected_device_id.get()
        
        # 自动保存配置
        try:
            self.save_config_silent()
        except:
            pass  # 忽略保存错误，不影响用户体验
            
        # 更新状态显示
        self.device_status_label.config(text=f"已选择设备: {selected_device}", foreground='green')
        


    def connect_adb_device(self):
        """智能设备连接功能（ADB或HDC）"""
        # 检查是否已经有连接窗口打开
        if self.adb_connection_window is not None and tk.Toplevel.winfo_exists(self.adb_connection_window):
            self._append_output("⚠️ 设备连接窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.adb_connection_window.lift()
            self.adb_connection_window.attributes('-topmost', True)
            self.adb_connection_window.after(1000, lambda: self.adb_connection_window.attributes('-topmost', False))
            return
        
        # 获取当前设备类型
        device_type = self.device_type.get()
        device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
        device_display = "HDC" if device_type_en == "hdc" else "ADB"
        
        self._append_output(f"🔍 正在检查{device_display}设备连接状态...\n")
        
        try:
            # 刷新设备列表
            self.refresh_devices()
            
            # 分析设备状态
            usb_devices = [d for d in self.connected_devices if d['status'] == 'device' and ':' not in d['id']]
            remote_devices = [d for d in self.connected_devices if d['status'] == 'device' and ':' in d['id']]
            offline_devices = [d for d in self.connected_devices if d['status'] == 'offline']
            
            # 先计算居中位置
            center_x, center_y = self._calculate_center_position(500, 600)
            
            # 创建智能连接对话框，直接设置位置避免闪现
            dialog = tk.Toplevel(self.root)
            self.adb_connection_window = dialog
            dialog.title(f"智能{device_display}连接")
            dialog.geometry(f"500x600+{center_x}+{center_y}")
            dialog.resizable(True, True)
            
            # 设置对话框始终在最前
            dialog.lift()
            dialog.attributes('-topmost', True)
            dialog.after(1000, lambda: dialog.attributes('-topmost', False))
            
            # 绑定窗口关闭事件
            dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_adb_connection_window_close(dialog))
            
            # 主框架
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 配置主框架权重，确保子组件能正确扩展
            main_frame.rowconfigure(1, weight=1)  # 让设备状态区域可扩展
            
            # 标题
            title_label = ttk.Label(main_frame, text=f"📱 {device_display}设备连接状态", 
                                   font=('Microsoft YaHei', 12, 'bold'))
            title_label.grid(row=0, column=0, pady=(0, 15), sticky=tk.N+tk.E+tk.W)
            
            # 设备状态显示区域 - 使用滚动文本框以适应多个设备
            status_frame = ttk.LabelFrame(main_frame, text="当前设备状态", padding="10")
            status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
            status_frame.columnconfigure(0, weight=1)
            
            # 创建滚动文本框来显示设备状态
            from tkinter import scrolledtext
            status_text = scrolledtext.ScrolledText(status_frame, height=8, width=50, 
                                                   font=('Microsoft YaHei', 9), 
                                                   wrap=tk.WORD, state=tk.DISABLED)
            status_text.pack(fill=tk.BOTH, expand=True)
            
            # 构建设备状态文本
            status_content = ""
            
            # USB设备状态
            if usb_devices:
                status_content += f"✅ USB设备: {len(usb_devices)} 台\n"
                for device in usb_devices:
                    status_content += f"   • {device['id']}\n"
            else:
                status_content += "❌ 未检测到USB设备\n"
            
            status_content += "\n"
            
            # 远程设备状态
            if remote_devices:
                status_content += f"✅ 远程设备: {len(remote_devices)} 台\n"
                for device in remote_devices:
                    status_content += f"   • {device['id']}\n"
            else:
                status_content += "⚪ 未连接远程设备\n"
            
            status_content += "\n"
            
            # 离线设备状态
            if offline_devices:
                status_content += f"⚠️ 离线设备: {len(offline_devices)} 台\n"
                for device in offline_devices:
                    status_content += f"   • {device['id']}\n"
            
            # 显示设备状态
            status_text.config(state=tk.NORMAL)
            status_text.insert("1.0", status_content)
            status_text.config(state=tk.DISABLED)
            
            # 操作按钮区域
            button_frame = ttk.LabelFrame(main_frame, text="连接选项", padding="10")
            button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
            button_frame.columnconfigure(0, weight=1)
            

            def do_connect_remote():
                """远程连接"""
                self._on_adb_connection_window_close(dialog)
                if device_type_en == "hdc":
                    self.connect_hdc_remote_device()
                else:
                    self.connect_wireless_pair_device()
                    
            def do_connect_wireless_pair():
                """无线调试配对连接（仅ADB）"""
                self._on_adb_connection_window_close(dialog)
                self.connect_wireless_pair_device()
            
            def do_connect_legacy_wireless():
                """传统无线调试连接（Android 10以下）"""
                self._on_adb_connection_window_close(dialog)
                self.connect_legacy_wireless_device()
                

            def do_restart_service():
                """重启ADB或HDC服务"""
                try:
                    if device_type_en == "hdc":
                        self._append_output("🔄 正在重启HDC服务...\n")
                        subprocess.run(['hdc', 'kill'], capture_output=True, timeout=5,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        subprocess.run(['hdc', 'start', '-r'], capture_output=True, timeout=5,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        self._append_output("✅ HDC服务已重启\n")
                    else:
                        self._append_output("🔄 正在重启ADB服务...\n")
                        subprocess.run(['adb', 'kill-server'], capture_output=True, timeout=5,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        subprocess.run(['adb', 'start-server'], capture_output=True, timeout=5,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        self._append_output("✅ ADB服务已重启\n")
                    self.refresh_devices()
                    dialog.after(1000, lambda: self.connect_adb_device())
                    self._on_adb_connection_window_close(dialog)
                except Exception as e:
                    service_name = "HDC" if device_type_en == "hdc" else "ADB"
                    self._append_output(f"❌ 重启{service_name}失败: {str(e)}\n")
            
            def do_disconnect_device():
                """断开设备连接"""
                # 创建断开连接对话框
                disconnect_dialog = tk.Toplevel(dialog)
                disconnect_dialog.title("断开设备连接")
                disconnect_dialog.geometry("400x300")
                disconnect_dialog.resizable(True, True)
                disconnect_dialog.transient(dialog)
                disconnect_dialog.grab_set()
                
                # 设置对话框居中显示
                disconnect_dialog.update_idletasks()
                x = (disconnect_dialog.winfo_screenwidth() // 2) - (disconnect_dialog.winfo_width() // 2)
                y = (disconnect_dialog.winfo_screenheight() // 2) - (disconnect_dialog.winfo_height() // 2)
                disconnect_dialog.geometry(f"+{x}+{y}")
                
                main_frame = ttk.Frame(disconnect_dialog, padding="15")
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                # 标题
                title_label = ttk.Label(main_frame, text="🔌 断开设备连接", 
                                       font=('Microsoft YaHei', 11, 'bold'))
                title_label.pack(pady=(0, 15))
                
                # 设备列表
                device_frame = ttk.LabelFrame(main_frame, text="当前连接的设备", padding="10")
                device_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
                
                # 创建设备列表
                all_devices = usb_devices + remote_devices
                if not all_devices:
                    ttk.Label(device_frame, text="没有可断开的连接设备", 
                            font=('Microsoft YaHei', 9)).pack(pady=20)
                else:
                    # 为每个设备创建断开按钮
                    for i, device in enumerate(all_devices):
                        device_info = f"{device['id']}"
                        if ':' in device['id']:
                            device_info += " (远程)"
                        else:
                            device_info += " (USB)"
                            
                        device_row = ttk.Frame(device_frame)
                        device_row.pack(fill=tk.X, pady=2)
                        
                        ttk.Label(device_row, text=device_info, 
                                font=('Microsoft YaHei', 9)).pack(side=tk.LEFT, padx=(0, 10))
                        
                        # 断开单个设备的按钮
                        def disconnect_single(device_id=device['id']):
                            try:
                                if device_type_en == "hdc":
                                    result = subprocess.run(['hdc', 'tdisconn', device_id], 
                                                         capture_output=True, text=True, timeout=10)
                                    command_desc = "HDC"
                                else:
                                    result = subprocess.run(['adb', 'disconnect', device_id], 
                                                         capture_output=True, text=True, timeout=10)
                                    command_desc = "ADB"
                                
                                if result.returncode == 0:
                                    self._append_output(f"✅ {command_desc}断开连接成功: {device_id}\n")
                                    if result.stdout:
                                        self._append_output(f"   {result.stdout.strip()}\n")
                                else:
                                    error_msg = result.stderr.strip() if result.stderr else f"断开失败，返回码: {result.returncode}"
                                    self._append_output(f"❌ {command_desc}断开连接失败: {device_id} - {error_msg}\n")
                                
                                # 刷新设备列表
                                self.refresh_devices()
                                # 关闭断开连接对话框
                                disconnect_dialog.destroy()
                                # 刷新主连接窗口
                                dialog.after(1000, lambda: self.connect_adb_device())
                                self._on_adb_connection_window_close(dialog)
                            except subprocess.TimeoutExpired:
                                self._append_output(f"❌ 断开连接超时: {device_id}\n")
                                messagebox.showerror("超时", f"断开连接 {device_id} 超时")
                            except Exception as e:
                                self._append_output(f"❌ 断开连接异常: {device_id} - {str(e)}\n")
                                messagebox.showerror("错误", f"断开连接异常: {str(e)}")
                        
                        ttk.Button(device_row, text="断开", 
                                  command=disconnect_single, 
                                  style='Danger.TButton').pack(side=tk.RIGHT)
                
                # 全部断开按钮
                if all_devices:
                    def disconnect_all():
                        try:
                            # 使用disconnect_result来检查断开连接结果
                            if device_type_en == "hdc":
                                # HDC断开所有连接
                                result = subprocess.run(['hdc', 'tdisconn', 'all'], 
                                                     capture_output=True, text=True, timeout=15)
                                command_desc = "HDC"
                            else:
                                # ADB断开所有连接
                                # 先尝试断开所有连接
                                disconnect_result = subprocess.run(['adb', 'disconnect'], 
                                                               capture_output=True, text=True, timeout=15)
                                
                                # 再重启ADB服务以清理状态
                                self._append_output("🔄 正在重启ADB服务以清理连接状态...\n")
                                restart_result = subprocess.run(['adb', 'kill-server'], 
                                                            capture_output=True, text=True, timeout=10)
                                if restart_result.returncode == 0:
                                    start_result = subprocess.run(['adb', 'start-server'], 
                                                                capture_output=True, text=True, timeout=10)
                                    if start_result.returncode == 0:
                                        self._append_output("✅ ADB服务已重启\n")
                                    else:
                                        self._append_output("⚠️ ADB服务启动可能失败\n")
                                else:
                                    self._append_output("⚠️ ADB服务停止可能失败\n")
                                
                                # 将disconnect_result赋值给result以便统一处理
                                result = disconnect_result
                                command_desc = "ADB"
                            
                            if result.returncode == 0:
                                self._append_output(f"✅ {command_desc}已断开所有连接\n")
                                if result.stdout:
                                    self._append_output(f"   {result.stdout.strip()}\n")
                            else:
                                error_msg = result.stderr.strip() if result.stderr else f"断开失败，返回码: {result.returncode}"
                                self._append_output(f"❌ {command_desc}断开所有连接失败: {error_msg}\n")
                            
                            # 刷新设备列表
                            self.refresh_devices()
                            # 关闭断开连接对话框
                            disconnect_dialog.destroy()
                            # 刷新主连接窗口
                            dialog.after(1000, lambda: self.connect_adb_device())
                            self._on_adb_connection_window_close(dialog)
                        except subprocess.TimeoutExpired:
                            self._append_output("❌ 断开所有连接超时\n")
                            messagebox.showerror("超时", "断开所有连接超时")
                        except Exception as e:
                            self._append_output(f"❌ 断开所有连接异常: {str(e)}\n")
                            messagebox.showerror("错误", f"断开所有连接异常: {str(e)}")
                    
                    # 全部断开按钮
                    all_button_frame = ttk.Frame(main_frame)
                    all_button_frame.pack(fill=tk.X, pady=(0, 10))
                    ttk.Button(all_button_frame, text="🔌 断开所有连接", 
                              command=disconnect_all, 
                              style='Danger.TButton').pack()
                
                # 关闭按钮
                close_frame = ttk.Frame(main_frame)
                close_frame.pack()
                ttk.Button(close_frame, text="❌ 关闭", 
                          command=disconnect_dialog.destroy, 
                          style='Secondary.TButton').pack()
            
            # 提供智能按钮建议
            buttons_row1 = ttk.Frame(button_frame)
            buttons_row1.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
            buttons_row1.columnconfigure(0, weight=1)
            
            # 第一行按钮
            row1_buttons = ttk.Frame(buttons_row1)
            row1_buttons.pack(anchor=tk.W)
            

                      
            if device_type_en == "hdc":
                ttk.Button(row1_buttons, text="🌐 远程HDC连接", 
                          command=do_connect_remote, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 8))
            else:
                ttk.Button(row1_buttons, text="🔗 Android 11+ 无线配对", 
                          command=do_connect_wireless_pair, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 8))
                ttk.Button(row1_buttons, text="📡 Android 10- 无线配对", 
                          command=do_connect_legacy_wireless, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 8))
            
            # 第二行按钮
            buttons_row2 = ttk.Frame(button_frame)
            buttons_row2.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
            buttons_row2.columnconfigure(0, weight=1)
            
            row2_buttons = ttk.Frame(buttons_row2)
            row2_buttons.pack(anchor=tk.W)
            

            
            if offline_devices or len(self.connected_devices) == 0:
                service_button_text = "🔧 重启HDC服务" if device_type_en == "hdc" else "🔧 重启ADB服务"
                ttk.Button(row2_buttons, text=service_button_text, 
                          command=do_restart_service, style='Danger.TButton').pack(side=tk.LEFT, padx=(0, 8))
            
            # 第三行按钮 - 断开连接
            if usb_devices or remote_devices:
                buttons_row3 = ttk.Frame(button_frame)
                buttons_row3.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
                buttons_row3.columnconfigure(0, weight=1)
                
                row3_buttons = ttk.Frame(buttons_row3)
                row3_buttons.pack(anchor=tk.W)
                
                ttk.Button(row3_buttons, text="🔌 断开设备连接", 
                          command=do_disconnect_device, style='Danger.TButton').pack(side=tk.LEFT, padx=(0, 8))
            

            
            # 更新状态消息
            total_devices = len(usb_devices) + len(remote_devices)
            if total_devices > 0:
                self._append_output(f"✅ 当前连接状态: {total_devices} 台设备可用\n")
            else:
                self._append_output("⚠️ 当前无可用设备，请选择连接选项\n")
                    
        except Exception as e:
            self._append_output(f"❌ 设备检查失败: {str(e)}\n")
            messagebox.showerror("错误", f"设备检查失败: {str(e)}")
            
    def show_device_details(self):
        """显示设备详细信息对话框"""
        if not self.connected_devices:
            messagebox.showinfo("设备信息", "当前没有连接的设备")
            return
        
        # 检查是否已经有设备详情窗口打开
        if self.device_details_window is not None and tk.Toplevel.winfo_exists(self.device_details_window):
            self._append_output("⚠️ 设备详情窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.device_details_window.lift()
            self.device_details_window.attributes('-topmost', True)
            self.device_details_window.after(1000, lambda: self.device_details_window.attributes('-topmost', False))
            return
            
        # 创建详情窗口
        details_window = tk.Toplevel(self.root)
        self.device_details_window = details_window
        details_window.title("设备详细信息")
        details_window.geometry("600x400")
        details_window.resizable(True, True)
        
        # 居中显示在主窗口中间
        self.center_window(details_window)
        
        # 绑定窗口关闭事件
        details_window.protocol("WM_DELETE_WINDOW", lambda: self._on_device_details_window_close(details_window))
        
        # 创建文本框显示详细信息
        details_text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, 
                                           font=('Microsoft YaHei', 9), bg='#f8f8f8')
        details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取每个设备的详细信息
        device_type = self.device_type.get()
        device_display = "HDC" if device_type == "鸿蒙" else "ADB"
        
        details_info = "=" * 50 + "\n"
        details_info += f"{device_display}设备详细信息 (共 {len(self.connected_devices)} 台)\n"
        details_info += "=" * 50 + "\n\n"
        
        for i, device in enumerate(self.connected_devices, 1):
            details_info += f"设备 {i}:\n"
            details_info += f"  ID: {device['id']}\n"
            details_info += f"  状态: {device['status']}\n"
            
            if device['info']:
                details_info += "  详细信息:\n"
                for key, value in device['info'].items():
                    details_info += f"    {key}: {value}\n"
                    
            details_info += "\n"
            
        details_text.insert("1.0", details_info)
        details_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        button_frame = ttk.Frame(details_window, style='Card.TFrame')
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="关闭", command=lambda: self._on_device_details_window_close(details_window), style='Danger.TButton').pack()
        
    def connect_device(self):
        """连接到指定IP的设备"""
        dialog = tk.Toplevel(self.root)
        dialog.title("连接设备")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        
        # 居中显示在主窗口中间
        self.center_window(dialog)
        
        # 设置对话框样式和配色，与主窗口保持一致
        dialog.configure(bg='#f0f0f0')
        
        # 主框架 - 使用与主窗口一致的padding
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置区域 - 使用与主窗口一致的LabelFrame样式
        config_frame = ttk.LabelFrame(main_frame, text="🔗 设备连接配置", style='Card.TFrame', padding="8")
        config_frame.pack(fill=tk.X, pady=(10, 15))
        
        # IP地址输入 - 使用上次连接的配置
        default_ip = getattr(self, 'last_remote_connection', {}).get('ip', '192.168.1.100')
        default_port = getattr(self, 'last_remote_connection', {}).get('port', '5555')
        default_address = f"{default_ip}:{default_port}"
        
        ttk.Label(config_frame, text="🌐 设备地址:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_var = tk.StringVar(value=default_address)
        ip_entry = ttk.Entry(config_frame, textvariable=ip_var, width=25, font=('Microsoft YaHei', 10))
        ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        config_frame.columnconfigure(1, weight=1)
        ip_entry.select_range(0, len(ip_var.get()))
        ip_entry.focus()
        
        def do_connect():
            ip_address = ip_var.get().strip()
            if ip_address:
                # 获取当前设备类型
                device_type = self.device_type.get()
                device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
                device_cmd = device_type_en
                self._append_output(f"🔗 正在连接到 {ip_address}...\n")
                try:
                    result = subprocess.run([device_cmd, 'connect', ip_address],
                                        capture_output=True, text=True, timeout=15,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if result.returncode == 0:
                        self._append_output(f"✅ 连接成功: {result.stdout.strip() if result.stdout else ''}\n")
                        
                        # 保存成功的连接信息
                        if ':' in ip_address:
                            ip, port = ip_address.rsplit(':', 1)
                            self.last_remote_connection = {
                                'ip': ip,
                                'port': port
                            }
                            # 自动保存配置
                            try:
                                self.save_config_silent()
                            except:
                                pass  # 忽略保存错误，不影响连接成功
                        
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        error_msg = result.stderr.strip() if result.stderr else f"连接失败，返回码: {result.returncode}"
                        self._append_output(f"❌ 连接失败: {error_msg}\n")
                        messagebox.showerror("连接失败", error_msg)
                except Exception as e:
                    self._append_output(f"❌ 连接异常: {str(e)}\n")
                    messagebox.showerror("连接异常", str(e))
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址")
                
        # 按钮区域 - 使用与主窗口一致的样式
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        ttk.Button(button_frame, text="🔗 连接", command=do_connect, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        
    def connect_remote_device(self):
        """远程连接ADB设备"""
        # 使用优化的居中窗口创建方法
        dialog = self.create_centered_toplevel(self.root, "远程ADB连接", 500, 250, resizable=False)
        
        # 设置对话框样式和配色，与主窗口保持一致
        dialog.configure(bg='#f0f0f0')
        
        # 主框架 - 使用与主窗口一致的padding
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置区域 - 使用与主窗口一致的LabelFrame样式
        config_frame = ttk.LabelFrame(main_frame, text="📡 远程设备配置", style='Card.TFrame', padding="8")
        config_frame.pack(fill=tk.X, pady=(10, 15))
        
        # IP地址和端口输入 - 使用上次连接的配置
        last_remote = getattr(self, 'last_remote_connection', {})
        default_ip = last_remote.get('ip', '192.168.1.100')
        default_port = last_remote.get('port', '5555')
        
        ttk.Label(config_frame, text="🌐 设备IP地址:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_var = tk.StringVar(value=default_ip)
        ip_entry = ttk.Entry(config_frame, textvariable=ip_var, width=25, font=('Microsoft YaHei', 10))
        ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        ttk.Label(config_frame, text="🔌 端口号:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        port_var = tk.StringVar(value=default_port)
        port_entry = ttk.Entry(config_frame, textvariable=port_var, width=10, font=('Microsoft YaHei', 10))
        port_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        def do_remote_connect():
            ip_address = ip_var.get().strip()
            port = port_var.get().strip()
            if ip_address and port:
                remote_address = f"{ip_address}:{port}"
                self._append_output(f"🌐 正在远程连接到 {remote_address}...\n")
                try:
                    # 首先尝试ping一下看是否能连通
                    import platform
                    if platform.system().lower() == 'windows':
                        ping_cmd = ['ping', '-n', '1', '-w', '2000', ip_address]
                    else:
                        ping_cmd = ['ping', '-c', '1', '-W', '2', ip_address]
                    
                    ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=5)
                    
                    if ping_result.returncode != 0:
                        self._append_output(f"⚠️ 无法ping通 {ip_address}，但仍尝试连接ADB...\n")
                    
                    # 获取当前设备类型
                    device_type = self.device_type.get()
                    device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
                    device_cmd = device_type_en
                    
                    # 连接设备
                    result = subprocess.run([device_cmd, 'connect', remote_address],
                                        capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        self._append_output(f"✅ 远程连接成功: {result.stdout.strip() if result.stdout else ''}\n")
                        
                        # 保存成功的连接信息
                        self.last_remote_connection = {
                            'ip': ip_address,
                            'port': port
                        }
                        # 自动保存配置
                        try:
                            self.save_config_silent()
                        except:
                            pass  # 忽略保存错误，不影响连接成功
                        
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        error_msg = result.stderr.strip() if result.stderr else f"连接失败，返回码: {result.returncode}"
                        self._append_output(f"❌ 远程连接失败: {error_msg}\n")
                        messagebox.showerror("连接失败", error_msg)
                except subprocess.TimeoutExpired:
                    self._append_output(f"❌ 连接超时: {remote_address}\n")
                    messagebox.showerror("连接超时", f"连接 {remote_address} 超时")
                except Exception as e:
                    self._append_output(f"❌ 连接异常: {str(e)}\n")
                    messagebox.showerror("连接异常", str(e))
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址和端口号")
                
        # 按钮区域 - 使用与主窗口一致的样式
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        ttk.Button(button_frame, text="🌐 远程连接", command=do_remote_connect, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        
        # 添加无线调试配对按钮
        def do_wireless_pair():
            dialog.destroy()
            self.connect_wireless_pair_device()
            
    def connect_wireless_pair_device(self):
        """无线调试配对连接（Android 11+）"""
        # 检查是否已经有无线配对窗口打开
        if hasattr(self, 'wireless_pair_window') and self.wireless_pair_window is not None and tk.Toplevel.winfo_exists(self.wireless_pair_window):
            self._append_output("⚠️ 安卓11+无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.wireless_pair_window.lift()
            self.wireless_pair_window.attributes('-topmost', True)
            self.wireless_pair_window.after(1000, lambda: self.wireless_pair_window.attributes('-topmost', False))
            return
            
        # 检查是否已经有安卓10无线配对窗口打开
        if hasattr(self, 'legacy_wireless_window') and self.legacy_wireless_window is not None and tk.Toplevel.winfo_exists(self.legacy_wireless_window):
            self._append_output("⚠️ 安卓10无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.legacy_wireless_window.lift()
            self.legacy_wireless_window.attributes('-topmost', True)
            self.legacy_wireless_window.after(1000, lambda: self.legacy_wireless_window.attributes('-topmost', False))
            return
        
        dialog = tk.Toplevel(self.root)
        self.wireless_pair_window = dialog
        dialog.title("无线调试配对连接 (Android 11+)")
        dialog.geometry("500x600")
        dialog.resizable(True, True)
        
        # 居中显示在主窗口中间
        self.center_window(dialog)
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题说明
        title_label = ttk.Label(main_frame, text="📱 Android 11+ 无线调试配对连接", 
                              font=('Microsoft YaHei', 11, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 说明文字
        info_frame = ttk.LabelFrame(main_frame, text="📋 使用说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """1. 确保Android 11+设备已开启无线调试
2. 设备需处于与PC同一WiFi网络
3. 在设备上获取配对码（通常是6位数字）
4. 输入配对地址、配对码和连接地址
5. 点击"开始配对连接"完成无线连接
6. 此方法适用于Android 11及以上版本的无线调试配对"""
        
        info_label = ttk.Label(info_frame, text=info_text, 
                              font=('Microsoft YaHei', 9), justify=tk.LEFT)
        info_label.pack(anchor=tk.W)
        
        # 连接配置区域
        config_frame = ttk.LabelFrame(main_frame, text="🔧 连接配置", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 使用上次配对的配置
        last_pair = getattr(self, 'last_wireless_pair', {})
        default_pair_address = last_pair.get('pair_address', '10.10.10.100:41717')
        default_connect_address = last_pair.get('connect_address', '10.10.10.100:5555')
        
        # 配对IP和端口
        ttk.Label(config_frame, text="🌐 配对地址 (IP:端口):", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=8)
        pair_address_var = tk.StringVar(value=default_pair_address)
        pair_address_entry = ttk.Entry(config_frame, textvariable=pair_address_var, width=30, font=('Microsoft YaHei', 10))
        pair_address_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=8)
        
        # 配对码
        ttk.Label(config_frame, text="🔑 配对码 (6位数字):", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=8)
        pair_code_var = tk.StringVar()
        pair_code_entry = ttk.Entry(config_frame, textvariable=pair_code_var, width=15, font=('Microsoft YaHei', 12))
        pair_code_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=8)
        
        # 连接地址
        ttk.Label(config_frame, text="📡 连接地址 (IP:端口):", font=('Microsoft YaHei', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=8)
        connect_address_var = tk.StringVar(value=default_connect_address)
        connect_address_entry = ttk.Entry(config_frame, textvariable=connect_address_var, width=30, font=('Microsoft YaHei', 10))
        connect_address_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=8)
        
        config_frame.columnconfigure(1, weight=1)
        
        def do_pair_connect():
            """执行配对和连接"""
            pair_address = pair_address_var.get().strip()
            pair_code = pair_code_var.get().strip()
            connect_address = connect_address_var.get().strip()
            
            if not pair_address or not pair_code or not connect_address:
                messagebox.showwarning("输入错误", "请填写所有必要信息")
                return
            
            self._append_output(f"🔗 开始配对: {pair_address}\n")
            self._append_output(f"🔑 配对码: {pair_code}\n")
            
            try:
                # 获取当前设备类型
                device_type = self.device_type.get()
                device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
                device_cmd = device_type_en
                
                # 对于ADB，先检查服务状态
                if device_type_en == "adb":
                    self._append_output("🔍 检查ADB服务状态...\n")
                    adb_check = subprocess.run(['adb', 'devices'], 
                                             capture_output=True, text=True, timeout=10,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if adb_check.returncode != 0:
                        self._append_output("⚠️ ADB服务异常，正在重启...\n")
                        subprocess.run(['adb', 'kill-server'], capture_output=True, text=True, timeout=10,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=10,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        self._append_output("✅ ADB服务已重启\n")
                
                # 第一步：配对
                pair_result = subprocess.run([device_cmd, 'pair', pair_address],
                                           input=pair_code + '\n',
                                           capture_output=True, text=True, timeout=30,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                
                if pair_result.returncode == 0:
                    self._append_output(f"✅ 配对成功: {pair_result.stdout.strip() if pair_result.stdout else ''}\n")
                    
                    # 第二步：连接
                    self._append_output(f"🌐 连接设备: {connect_address}\n")
                    connect_result = subprocess.run([device_cmd, 'connect', connect_address],
                                                  capture_output=True, text=True, timeout=15,
                                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if connect_result.returncode == 0:
                        self._append_output(f"✅ 连接成功: {connect_result.stdout.strip() if connect_result.stdout else ''}\n")
                        
                        # 保存成功的配对信息
                        self.last_wireless_pair = {
                            'pair_address': pair_address,
                            'connect_address': connect_address
                        }
                        # 同时更新远程连接配置（从连接地址中提取IP和端口）
                        if ':' in connect_address:
                            ip, port = connect_address.rsplit(':', 1)
                            self.last_remote_connection = {
                                'ip': ip,
                                'port': port
                            }
                        
                        # 自动保存配置
                        try:
                            self.save_config_silent()
                        except:
                            pass  # 忽略保存错误，不影响连接成功
                        
                        self.refresh_devices()
                        dialog.destroy()
                        messagebox.showinfo("连接成功", f"✅ 无线调试配对连接成功！\n\n📱 设备地址: {connect_address}")
                    else:
                        error_msg = connect_result.stderr.strip() if connect_result.stderr else f"连接失败，返回码: {connect_result.returncode}"
                        self._append_output(f"❌ 连接失败: {error_msg}\n")
                        
                        # 提供更详细的诊断信息
                        diagnosis_msg = f"{error_msg}\\n\\n常见问题：\\n• 如果之前点击过'断开所有连接'，请稍等片刻再重试\\n• 尝试重启ADB服务：adb kill-server && adb start-server\\n• 检查设备是否已撤销之前的配对\\n• 确认设备网络连接正常"
                        
                        messagebox.showerror("连接失败", diagnosis_msg)
                else:
                    error_msg = pair_result.stderr.strip() if pair_result.stderr else f"配对失败，返回码: {pair_result.returncode}"
                    self._append_output(f"❌ 配对失败: {error_msg}\n")
                    messagebox.showerror("配对失败", error_msg)
                    
            except Exception as e:
                self._append_output(f"❌ 操作异常: {str(e)}\n")
                messagebox.showerror("异常错误", str(e))
        
        # 按钮区域 - 确保在主框架底部可见
        button_container = ttk.Frame(main_frame)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建居中容器
        button_frame = ttk.Frame(button_container)
        button_frame.pack()
        
        # 创建按钮
        ttk.Button(button_frame, text="🔑 开始配对连接", command=do_pair_connect, 
                  style='Success.TButton', width=20).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, 
                  style='Danger.TButton', width=12).pack(side=tk.LEFT)
        
        # 设置焦点到配对码输入框
        pair_code_entry.focus()
        
        # 绑定窗口关闭事件
        dialog.protocol("WM_DELETE_WINDOW", self._on_wireless_pair_window_close)
        
    def install_adb_keyboard(self):
        """安装ADB键盘应用（仅支持安卓设备）"""
        # 检查当前设备类型
        device_type = self.device_type.get()
        if device_type == "鸿蒙":
            messagebox.showwarning("设备类型错误", "HDC设备（鸿蒙）不需要安装ADB键盘")
            return
            
        selected_device = self.selected_device_id.get()
        if not selected_device:
            messagebox.showwarning("设备选择", "请先选择一个设备")
            return
            
        # 从下拉框显示名称中提取设备ID
        device_id = selected_device.split(' ')[0]
        
        # 检查ADBKeyboard.apk文件是否存在
        apk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ADBKeyboard.apk")
        if not os.path.exists(apk_path):
            messagebox.showerror("文件不存在", f"ADBKeyboard.apk 文件不存在:\n{apk_path}")
            return
            
        # 确认安装
        result = messagebox.askyesno("确认安装", 
                                    f"确定要在设备 {device_id} 上安装 ADBKeyboard.apk 吗？\n\n"
                                    f"这个应用用于自动化输入操作。")
        if not result:
            return
            
        self._append_output(f"📲 正在为设备 {device_id} 安装ADB键盘...\n")
        
        try:
            # 安装APK
            install_result = subprocess.run(['adb', '-s', device_id, 'install', apk_path],
                                          capture_output=True, text=True, timeout=60,
                                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            if install_result.returncode == 0:
                self._append_output(f"✅ ADB键盘安装成功: {install_result.stdout.strip() if install_result.stdout else ''}\n")
                
                # 设置为默认输入法
                self._append_output("🔧 正在设置ADB键盘为默认输入法...\n")
                settings_result = subprocess.run(['adb', '-s', device_id, 'shell', 
                                               'ime enable com.android.adbkeyboard/.AdbIME'],
                                              capture_output=True, text=True, timeout=10,
                                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                
                if settings_result.returncode == 0:
                    self._append_output("✅ ADB键盘已启用\n")
                    
                    # 切换到ADB键盘
                    switch_result = subprocess.run(['adb', '-s', device_id, 'shell', 
                                                  'ime set com.android.adbkeyboard/.AdbIME'],
                                                 capture_output=True, text=True, timeout=10,
                                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if switch_result.returncode == 0:
                        self._append_output("✅ ADB键盘已设置为默认输入法\n")
                        messagebox.showinfo("安装成功", "ADB键盘安装并设置成功！")
                    else:
                        error_msg = switch_result.stderr.strip() if switch_result.stderr else f"设置失败，返回码: {switch_result.returncode}"
                        self._append_output(f"⚠️ 设置默认输入法失败: {error_msg}\n")
                        messagebox.showwarning("部分成功", "键盘安装成功，但设置为默认输入法失败，请手动设置。")
                else:
                    error_msg = settings_result.stderr.strip() if settings_result.stderr else f"启用失败，返回码: {settings_result.returncode}"
                    self._append_output(f"⚠️ 启用ADB键盘失败: {error_msg}\n")
                    messagebox.showwarning("部分成功", "键盘安装成功，但启用失败，请手动启用。")
            else:
                error_msg = install_result.stderr.strip() if install_result.stderr else f"安装失败，返回码: {install_result.returncode}"
                self._append_output(f"❌ ADB键盘安装失败: {error_msg}\n")
                messagebox.showerror("安装失败", error_msg)
                
        except subprocess.TimeoutExpired:
            self._append_output("❌ 安装超时，请检查设备连接\n")
            messagebox.showerror("安装超时", "安装过程超时，请检查设备连接状态")
        except Exception as e:
            self._append_output(f"❌ 安装异常: {str(e)}\n")
            messagebox.showerror("安装异常", str(e))
            
    def open_wechat_qrcode(self):
        """在GUI中显示微信公众号二维码"""
        try:
            # 检查是否已经有二维码窗口打开
            if self.qrcode_window is not None and tk.Toplevel.winfo_exists(self.qrcode_window):
                self._append_output("⚠️ 二维码窗口已经打开，请先关闭现有窗口\n")
                # 将现有窗口置于前台
                self.qrcode_window.lift()
                self.qrcode_window.attributes('-topmost', True)
                self.qrcode_window.after(1000, lambda: self.qrcode_window.attributes('-topmost', False))
                return
            
            self._append_output("📱 正在加载微信公众号二维码...\n")
            
            # 先计算居中位置
            center_x, center_y = self._calculate_center_position(500, 550)
            
            # 创建二维码显示窗口，直接设置位置避免闪现
            self.qrcode_window = tk.Toplevel(self.root)
            self.qrcode_window.title("关注微信公众号 - 菜芽创作小助手")
            self.qrcode_window.geometry(f"500x550+{center_x}+{center_y}")
            self.qrcode_window.resizable(False, False)
            
            # 设置窗口始终在最前
            self.qrcode_window.lift()
            self.qrcode_window.attributes('-topmost', True)
            
            # 绑定窗口关闭事件
            self.qrcode_window.protocol("WM_DELETE_WINDOW", self._on_qrcode_window_close)
            
            # 主框架 - 减少padding
            self.qrcode_main_frame = ttk.Frame(self.qrcode_window, padding="10")
            self.qrcode_main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 标题
            title_label = ttk.Label(self.qrcode_main_frame, text="📱 微信关注公众号", 
                                   font=('Microsoft YaHei', 14, 'bold'))
            title_label.pack(pady=(0, 5))
            
            # 公众号名称
            name_label = ttk.Label(self.qrcode_main_frame, text="菜芽创作小助手", 
                                  font=('Microsoft YaHei', 12))
            name_label.pack(pady=(0, 10))
            
            # 加载二维码图片
            try:
                from PIL import Image, ImageTk
                import urllib.request
                import io
                import os
                
                # 下载二维码图片
                qrcode_url = "https://docker.071717.xyz/https://raw.githubusercontent.com/e5sub/Open-AutoGLM-GUI/master/gzh.png"
                
                def load_qrcode():
                    try:
                        print(f"开始下载二维码: {qrcode_url}")
                        
                        # 使用urllib下载图片
                        image_data = None
                        download_success = False
                        
                        print("尝试使用urllib下载...")
                        
                        # 尝试多个不同的请求头
                        user_agents = [
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)',
                        ]
                        
                        for ua in user_agents:
                            if download_success:
                                break
                                
                            for attempt in range(3):
                                try:
                                    req = urllib.request.Request(qrcode_url)
                                    req.add_header('User-Agent', ua)
                                    req.add_header('Accept', 'image/png,image/*;q=0.8,*/*;q=0.5')
                                    req.add_header('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')
                                    req.add_header('Connection', 'keep-alive')
                                    
                                    # 增加超时时间
                                    with urllib.request.urlopen(req, timeout=30) as response:
                                        # 分块读取，避免IncompleteRead
                                        chunks = []
                                        while True:
                                            chunk = response.read(8192)
                                            if not chunk:
                                                break
                                            chunks.append(chunk)
                                        
                                        image_data = b''.join(chunks)
                                        print(f"urllib下载完成，数据大小: {len(image_data)} 字节")
                                        print(f"响应头: {dict(response.headers)}")
                                        
                                        if len(image_data) > 1000:
                                            download_success = True
                                            break
                                        else:
                                            print(f"下载数据太小: {len(image_data)} 字节")
                                            
                                except Exception as url_e:
                                    print(f"urllib下载失败（尝试{attempt+1}）: {str(url_e)}")
                                    print(f"URL: {qrcode_url}")
                                    print(f"User-Agent: {ua}")
                                    if attempt == 2:
                                        if ua == user_agents[-1]:  # 最后一个UA
                                            raise url_e
                                    continue
                        
                        # 检查是否获取到有效数据
                        if not download_success or image_data is None:
                            raise Exception("下载失败")
                            
                        if len(image_data) < 1000:
                            raise Exception(f"获取到的图片数据太小: {len(image_data)} 字节")
                        
                        # 检查数据开头，确认是PNG格式
                        print(f"数据开头20字节: {image_data[:20]}")
                        if not image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                            print("警告：数据不是标准PNG格式")
                            # 尝试保存到临时文件再读取
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                                temp_file.write(image_data)
                                temp_path = temp_file.name
                            
                            try:
                                print("尝试从临时文件读取...")
                                image = Image.open(temp_path)
                                print(f"图片格式: {image.format}, 大小: {image.size}")
                                os.unlink(temp_path)
                            except Exception as temp_e:
                                os.unlink(temp_path)
                                raise Exception(f"无法解析图片数据: {str(temp_e)}")
                        else:
                            print("检测到PNG格式，直接解析")
                            image = Image.open(io.BytesIO(image_data))
                            print(f"图片解析成功，格式: {image.format}, 大小: {image.size}")
                        
                        # 调整大小为430*430
                        image = image.resize((430, 430), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        
                        # 在主线程中显示图片
                        def show_image():
                            if self.qrcode_window and tk.Toplevel.winfo_exists(self.qrcode_window):
                                img_label = ttk.Label(self.qrcode_main_frame, image=photo)
                                img_label.image = photo  # 保持引用
                                img_label.pack(pady=(0, 10))
                                self.qrcode_window.after(1000, lambda: self.qrcode_window.attributes('-topmost', False))
                        
                        self.root.after(0, show_image)
                        
                    except Exception as e:
                        print(f"二维码加载详细错误: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        
                        # 在主线程中显示错误信息
                        def show_error():
                            if self.qrcode_window and tk.Toplevel.winfo_exists(self.qrcode_window):
                                error_label = ttk.Label(self.qrcode_main_frame, 
                                                      text=f"二维码加载失败\n\n错误详情:\n{str(e)}", 
                                                      font=('Microsoft YaHei', 10), 
                                                      foreground='#FF6B6B',
                                                      justify=tk.CENTER)
                                error_label.pack(pady=30)
                        
                        self.root.after(0, show_error)
                
                # 在新线程中加载图片，避免阻塞GUI
                import threading
                threading.Thread(target=load_qrcode, daemon=True).start()
                
            except ImportError:
                # 如果没有PIL库，显示安装提示
                def show_import_error():
                    if self.qrcode_window and tk.Toplevel.winfo_exists(self.qrcode_window):
                        error_label = ttk.Label(self.qrcode_main_frame, 
                                              text="无法显示二维码\n需要安装 Pillow 库\n\n请运行: pip install Pillow", 
                                              font=('Microsoft YaHei', 11), 
                                              foreground='#FF6B6B',
                                              justify=tk.CENTER)
                        error_label.pack(pady=50)
                        
                        close_btn = ttk.Button(self.qrcode_main_frame, text="关闭", 
                                             command=self._on_qrcode_window_close)
                        close_btn.pack(pady=20)
                
                self.root.after(0, show_import_error)
            
            self._append_output("✅ 二维码窗口已打开\n")
            
        except Exception as e:
            self._append_output(f"❌ 打开二维码窗口失败: {str(e)}\n")
            messagebox.showerror("打开失败", f"无法打开二维码窗口：{str(e)}")
            self.qrcode_window = None  # 重置变量
    
    def _on_qrcode_window_close(self):
        """二维码窗口关闭事件处理"""
        self.qrcode_window.destroy()
        self.qrcode_window = None
        self._append_output("✅ 二维码窗口已关闭\n")
    
    def _on_adb_connection_window_close(self, dialog):
        """ADB/HDC连接窗口关闭事件处理"""
        dialog.destroy()
        if dialog == self.adb_connection_window:
            self.adb_connection_window = None
        
        # 根据当前设备类型显示正确的消息
        device_type = self.device_type.get()
        device_display = "HDC" if device_type == "鸿蒙" else "ADB"
        self._append_output(f"✅ {device_display}连接窗口已关闭\n")
    
    def _on_device_details_window_close(self, dialog):
        """设备详情窗口关闭事件处理"""
        dialog.destroy()
        if dialog == self.device_details_window:
            self.device_details_window = None
        self._append_output("✅ 设备详情窗口已关闭\n")
    
    def _on_wireless_pair_window_close(self):
        """安卓11+无线配对窗口关闭事件处理"""
        if hasattr(self, 'wireless_pair_window') and self.wireless_pair_window:
            self.wireless_pair_window.destroy()
            self.wireless_pair_window = None
        self._append_output("✅ 安卓11+无线配对窗口已关闭\n")
    
    def _on_legacy_wireless_window_close(self):
        """安卓10无线配对窗口关闭事件处理"""
        if hasattr(self, 'legacy_wireless_window') and self.legacy_wireless_window:
            self.legacy_wireless_window.destroy()
            self.legacy_wireless_window = None
        self._append_output("✅ 安卓10无线配对窗口已关闭\n")
    
    def connect_wireless_pair_device(self):
        """无线调试配对连接（Android 11+）"""
        # 检查是否已经有无线配对窗口打开
        if hasattr(self, 'wireless_pair_window') and self.wireless_pair_window is not None and tk.Toplevel.winfo_exists(self.wireless_pair_window):
            self._append_output("⚠️ 安卓11+无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.wireless_pair_window.lift()
            self.wireless_pair_window.attributes('-topmost', True)
            self.wireless_pair_window.after(1000, lambda: self.wireless_pair_window.attributes('-topmost', False))
            return
            
        # 检查是否已经有安卓10无线配对窗口打开
        if hasattr(self, 'legacy_wireless_window') and self.legacy_wireless_window is not None and tk.Toplevel.winfo_exists(self.legacy_wireless_window):
            self._append_output("⚠️ 安卓10无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.legacy_wireless_window.lift()
            self.legacy_wireless_window.attributes('-topmost', True)
            self.legacy_wireless_window.after(1000, lambda: self.legacy_wireless_window.attributes('-topmost', False))
            return
        
        dialog = tk.Toplevel(self.root)
        self.wireless_pair_window = dialog
        dialog.title("无线调试配对连接 (Android 11+)")
        dialog.geometry("500x600")
        dialog.resizable(True, True)
        
        # 居中显示在主窗口中间
        self.center_window(dialog)
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题说明
        title_label = ttk.Label(main_frame, text="📱 Android 11+ 无线调试配对连接", 
                              font=('Microsoft YaHei', 11, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 说明文字
        info_frame = ttk.LabelFrame(main_frame, text="📋 使用说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """1. 确保Android 11+设备已开启无线调试
2. 设备需处于与PC同一WiFi网络
3. 在设备上获取配对码（通常是6位数字）
4. 输入配对地址、配对码和连接地址
5. 点击"开始配对连接"完成无线连接
6. 此方法适用于Android 11及以上版本的无线调试配对"""
        
        info_label = ttk.Label(info_frame, text=info_text, 
                              font=('Microsoft YaHei', 9), justify=tk.LEFT)
        info_label.pack(anchor=tk.W)
        
        # 连接配置区域
        config_frame = ttk.LabelFrame(main_frame, text="🔧 连接配置", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 使用上次配对的配置
        last_pair = getattr(self, 'last_wireless_pair', {})
        default_pair_address = last_pair.get('pair_address', '10.10.10.100:41717')
        default_connect_address = last_pair.get('connect_address', '10.10.10.100:5555')
        
        # 配对IP和端口
        ttk.Label(config_frame, text="🌐 配对地址 (IP:端口):", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=8)
        pair_address_var = tk.StringVar(value=default_pair_address)
        pair_address_entry = ttk.Entry(config_frame, textvariable=pair_address_var, width=30, font=('Microsoft YaHei', 10))
        pair_address_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=8)
        
        # 配对码
        ttk.Label(config_frame, text="🔑 配对码 (6位数字):", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=8)
        pair_code_var = tk.StringVar()
        pair_code_entry = ttk.Entry(config_frame, textvariable=pair_code_var, width=15, font=('Microsoft YaHei', 12))
        pair_code_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=8)
        
        # 连接地址
        ttk.Label(config_frame, text="📡 连接地址 (IP:端口):", font=('Microsoft YaHei', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=8)
        connect_address_var = tk.StringVar(value=default_connect_address)
        connect_address_entry = ttk.Entry(config_frame, textvariable=connect_address_var, width=30, font=('Microsoft YaHei', 10))
        connect_address_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=8)
        
        config_frame.columnconfigure(1, weight=1)
        
        def do_pair_connect():
            """执行配对和连接"""
            pair_address = pair_address_var.get().strip()
            pair_code = pair_code_var.get().strip()
            connect_address = connect_address_var.get().strip()
            
            if not pair_address or not pair_code or not connect_address:
                messagebox.showwarning("输入错误", "请填写所有必要信息")
                return
            
            self._append_output(f"🔗 开始配对: {pair_address}\n")
            self._append_output(f"🔑 配对码: {pair_code}\n")
            
            try:
                # 获取当前设备类型
                device_type = self.device_type.get()
                device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
                device_cmd = device_type_en
                
                # 对于ADB，先检查服务状态
                if device_type_en == "adb":
                    self._append_output("🔍 检查ADB服务状态...\n")
                    adb_check = subprocess.run(['adb', 'devices'], 
                                             capture_output=True, text=True, timeout=10,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if adb_check.returncode != 0:
                        self._append_output("⚠️ ADB服务异常，正在重启...\n")
                        subprocess.run(['adb', 'kill-server'], capture_output=True, text=True, timeout=10,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=10,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        self._append_output("✅ ADB服务已重启\n")
                
                # 第一步：配对
                pair_result = subprocess.run([device_cmd, 'pair', pair_address],
                                           input=pair_code + '\n',
                                           capture_output=True, text=True, timeout=30,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                
                if pair_result.returncode == 0:
                    self._append_output(f"✅ 配对成功: {pair_result.stdout.strip() if pair_result.stdout else ''}\n")
                    
                    # 第二步：连接
                    self._append_output(f"🌐 连接设备: {connect_address}\n")
                    connect_result = subprocess.run([device_cmd, 'connect', connect_address],
                                                  capture_output=True, text=True, timeout=15,
                                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if connect_result.returncode == 0:
                        self._append_output(f"✅ 连接成功: {connect_result.stdout.strip() if connect_result.stdout else ''}\n")
                        
                        # 保存成功的配对信息
                        self.last_wireless_pair = {
                            'pair_address': pair_address,
                            'connect_address': connect_address
                        }
                        # 同时更新远程连接配置（从连接地址中提取IP和端口）
                        if ':' in connect_address:
                            ip, port = connect_address.rsplit(':', 1)
                            self.last_remote_connection = {
                                'ip': ip,
                                'port': port
                            }
                        
                        # 自动保存配置
                        try:
                            self.save_config_silent()
                        except:
                            pass  # 忽略保存错误，不影响连接成功
                        
                        self.refresh_devices()
                        dialog.destroy()
                        messagebox.showinfo("连接成功", f"✅ 无线调试配对连接成功！\n\n📱 设备地址: {connect_address}")
                    else:
                        error_msg = connect_result.stderr.strip() if connect_result.stderr else f"连接失败，返回码: {connect_result.returncode}"
                        self._append_output(f"❌ 连接失败: {error_msg}\n")
                        
                        # 提供更详细的诊断信息
                        diagnosis_msg = f"{error_msg}\\n\\n常见问题：\\n• 如果之前点击过'断开所有连接'，请稍等片刻再重试\\n• 尝试重启ADB服务：adb kill-server && adb start-server\\n• 检查设备是否已撤销之前的配对\\n• 确认设备网络连接正常"
                        
                        messagebox.showerror("连接失败", diagnosis_msg)
                else:
                    error_msg = pair_result.stderr.strip() if pair_result.stderr else f"配对失败，返回码: {pair_result.returncode}"
                    self._append_output(f"❌ 配对失败: {error_msg}\n")
                    messagebox.showerror("配对失败", error_msg)
                    
            except Exception as e:
                self._append_output(f"❌ 操作异常: {str(e)}\n")
                messagebox.showerror("异常错误", str(e))
        
        # 按钮区域 - 确保在主框架底部可见
        button_container = ttk.Frame(main_frame)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建居中容器
        button_frame = ttk.Frame(button_container)
        button_frame.pack()
        
        # 创建按钮
        ttk.Button(button_frame, text="🔑 开始配对连接", command=do_pair_connect, 
                  style='Success.TButton', width=20).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, 
                  style='Danger.TButton', width=12).pack(side=tk.LEFT)
        
        # 设置焦点到配对码输入框
        pair_code_entry.focus()
        
        # 绑定窗口关闭事件
        dialog.protocol("WM_DELETE_WINDOW", self._on_wireless_pair_window_close)

    def connect_legacy_wireless_device(self):
        """无线调试配置连接（Android 10及以下）"""
        # 检查是否已经有安卓10无线配对窗口打开
        if hasattr(self, 'legacy_wireless_window') and self.legacy_wireless_window is not None and tk.Toplevel.winfo_exists(self.legacy_wireless_window):
            self._append_output("⚠️ 安卓10无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.legacy_wireless_window.lift()
            self.legacy_wireless_window.attributes('-topmost', True)
            self.legacy_wireless_window.after(1000, lambda: self.legacy_wireless_window.attributes('-topmost', False))
            return
            
        # 检查是否已经有安卓11+无线配对窗口打开
        if hasattr(self, 'wireless_pair_window') and self.wireless_pair_window is not None and tk.Toplevel.winfo_exists(self.wireless_pair_window):
            self._append_output("⚠️ 安卓11+无线配对窗口已经打开，请先关闭现有窗口\n")
            # 将现有窗口置于前台
            self.wireless_pair_window.lift()
            self.wireless_pair_window.attributes('-topmost', True)
            self.wireless_pair_window.after(1000, lambda: self.wireless_pair_window.attributes('-topmost', False))
            return
        
        dialog = tk.Toplevel(self.root)
        self.legacy_wireless_window = dialog
        dialog.title("无线调试配置连接 (Android 10及以下)")
        dialog.geometry("500x550")
        dialog.resizable(True, True)
        
        # 居中显示在主窗口中间
        self.center_window(dialog)
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题说明
        title_label = ttk.Label(main_frame, text="📱 Android 10及以下 无线调试配置连接", 
                              font=('Microsoft YaHei', 11, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 说明文字
        info_frame = ttk.LabelFrame(main_frame, text="📋 使用说明", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """1. 确保Android设备已开启USB调试
2. 设备需处于与PC同一WiFi网络
3. 输入设备的IP地址和端口号
4. 点击"开始配对连接"即可完成连接
5. 此方法适用于Android 10及以下版本
6. 首次使用可能需要先用USB连接执行adb tcpip 5555"""
        
        info_label = ttk.Label(info_frame, text=info_text, 
                              font=('Microsoft YaHei', 9), justify=tk.LEFT)
        info_label.pack(anchor=tk.W)
        
        # 连接配置区域
        config_frame = ttk.LabelFrame(main_frame, text="🔧 连接配置", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 使用上次连接的配置
        last_remote = getattr(self, 'last_legacy_wireless', {})
        default_ip = last_remote.get('ip', '192.168.1.100')
        default_port = last_remote.get('port', '5555')
        
        # IP地址和端口输入
        ttk.Label(config_frame, text="🌐 设备IP地址:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=8)
        ip_var = tk.StringVar(value=default_ip)
        ip_entry = ttk.Entry(config_frame, textvariable=ip_var, width=25, font=('Microsoft YaHei', 10))
        ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=8)
        config_frame.columnconfigure(1, weight=1)
        
        ttk.Label(config_frame, text="🔌 端口号:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=8)
        port_var = tk.StringVar(value=default_port)
        port_entry = ttk.Entry(config_frame, textvariable=port_var, width=10, font=('Microsoft YaHei', 10))
        port_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=8)
        
        def do_wireless_connect():
            """执行无线调试配置连接"""
            ip_address = ip_var.get().strip()
            port = port_var.get().strip()
            
            if not ip_address:
                messagebox.showwarning("输入错误", "请输入设备IP地址")
                return
            if not port:
                port = '5555'
                port_var.set(port)
            
            remote_address = f"{ip_address}:{port}"
            self._append_output(f"🔑 正在开始配对连接 {remote_address}...\\n")
            
            try:
                # 先检查ADB服务状态，必要时重启
                self._append_output("🔍 检查ADB服务状态...\\n")
                adb_check = subprocess.run(['adb', 'devices'], 
                                         capture_output=True, text=True, timeout=10)
                
                if adb_check.returncode != 0:
                    self._append_output("⚠️ ADB服务异常，正在重启...\\n")
                    subprocess.run(['adb', 'kill-server'], capture_output=True, text=True, timeout=10)
                    subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=10)
                    self._append_output("✅ ADB服务已重启\\n")
                
                # 尝试ping一下看是否能连通
                import platform
                if platform.system().lower() == 'windows':
                    ping_cmd = ['ping', '-n', '1', '-w', '2000', ip_address]
                else:
                    ping_cmd = ['ping', '-c', '1', '-W', '2', ip_address]
                
                ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=5)
                
                if ping_result.returncode != 0:
                    self._append_output(f"⚠️ 无法ping通 {ip_address}，但仍尝试连接ADB...\\n")
                else:
                    self._append_output(f"✅ 网络连通: {ip_address}\\n")
                
                # 直接连接ADB设备
                connect_result = subprocess.run(['adb', 'connect', remote_address],
                                              capture_output=True, text=True, timeout=15)
                
                if connect_result.returncode == 0 or "connected" in connect_result.stdout.lower():
                    self._append_output(f"✅ 连接成功: {connect_result.stdout.strip() if connect_result.stdout else ''}\\n")
                    
                    # 保存成功的连接信息
                    self.last_legacy_wireless = {
                        'ip': ip_address,
                        'port': port
                    }
                    # 同时更新远程连接配置
                    self.last_remote_connection = {
                        'ip': ip_address,
                        'port': port
                    }
                    
                    # 自动保存配置
                    try:
                        self.save_config_silent()
                    except:
                        pass  # 忽略保存错误，不影响连接成功
                    
                    self.refresh_devices()
                    dialog.destroy()
                    messagebox.showinfo("成功", f"✅ 配对连接成功！\n\n📱 设备地址: {remote_address}")
                else:
                    error_msg = connect_result.stderr.strip() if connect_result.stderr else connect_result.stdout.strip() or f"连接失败，返回码: {connect_result.returncode}"
                    self._append_output(f"❌ 连接失败: {error_msg}\\n")
                    
                    # 提供更详细的诊断信息
                    diagnosis_msg = f"无法连接到设备 {remote_address}\\n\\n请确保：\\n1. 设备已开启USB调试\\n2. 设备与PC在同一网络\\n3. 设备已启用网络ADB（可能需要先USB连接执行adb tcpip 5555）\\n\\n常见问题：\\n• 如果之前点击过'断开所有连接'，请稍等片刻再重试\\n• 尝试重启ADB服务：adb kill-server && adb start-server\\n• 检查设备防火墙设置"
                    
                    messagebox.showerror("连接失败", diagnosis_msg)
                    
            except subprocess.TimeoutExpired:
                self._append_output("❌ 连接超时\\n")
                messagebox.showerror("超时", "连接设备超时")
            except Exception as e:
                self._append_output(f"❌ 连接异常: {str(e)}\\n")
                messagebox.showerror("异常", f"连接异常: {str(e)}")
        
        def show_help():
            """显示帮助信息"""
            help_text = """如果连接失败，请尝试以下步骤：

1. 首次使用时，可能需要先用USB连接设备：
   - USB连接设备并开启USB调试
   - 执行命令：adb tcpip 5555
   - 断开USB，然后使用此功能连接

2. 确保设备防火墙允许ADB端口

3. 检查设备IP地址是否正确：
   - 在设备设置中查看WiFi详情获取IP
   - 或在设备终端执行：ip addr show wlan0

4. 确保PC和设备在同一网段"""
            
            messagebox.showinfo("帮助", help_text)
        
        # 按钮区域 - 确保在主框架底部可见
        button_container = ttk.Frame(main_frame)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # 创建居中容器
        button_frame = ttk.Frame(button_container)
        button_frame.pack()
        
        # 创建按钮
        ttk.Button(button_frame, text="🔑 开始配对连接", command=do_wireless_connect, 
                  style='Success.TButton', width=18).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❓ 帮助", command=show_help, 
                  width=10).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ 关闭", command=dialog.destroy, 
                  style='Danger.TButton', width=10).pack(side=tk.LEFT)
        
        # 设置焦点到IP地址输入框
        ip_entry.focus()
        
        # 绑定窗口关闭事件
        dialog.protocol("WM_DELETE_WINDOW", self._on_legacy_wireless_window_close)

    def connect_hdc_remote_device(self):
        """远程连接HDC设备"""
        dialog = tk.Toplevel(self.root)
        dialog.title("远程HDC连接")
        dialog.geometry("500x250")
        dialog.resizable(False, False)
        
        # 居中显示在主窗口中间
        self.center_window(dialog)
        
        # 设置对话框样式和配色，与主窗口保持一致
        dialog.configure(bg='#f0f0f0')
        
        # 主框架 - 使用与主窗口一致的padding
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置区域 - 使用与主窗口一致的LabelFrame样式
        config_frame = ttk.LabelFrame(main_frame, text="📡 远程鸿蒙设备配置", style='Card.TFrame', padding="8")
        config_frame.pack(fill=tk.X, pady=(10, 15))
        
        # IP地址和端口输入 - 使用上次连接的配置
        last_remote = getattr(self, 'last_remote_connection', {})
        default_ip = last_remote.get('ip', '192.168.1.100')
        default_port = last_remote.get('port', '5555')
        
        ttk.Label(config_frame, text="🌐 设备IP地址:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_var = tk.StringVar(value=default_ip)
        ip_entry = ttk.Entry(config_frame, textvariable=ip_var, width=25, font=('Microsoft YaHei', 10))
        ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        ttk.Label(config_frame, text="🔌 端口号:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        port_var = tk.StringVar(value=default_port)
        port_entry = ttk.Entry(config_frame, textvariable=port_var, width=10, font=('Microsoft YaHei', 10))
        port_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        def do_hdc_remote_connect():
            ip_address = ip_var.get().strip()
            port = port_var.get().strip()
            if ip_address and port:
                remote_address = f"{ip_address}:{port}"
                self._append_output(f"🌐 正在远程连接鸿蒙设备 {remote_address}...\n")
                try:
                    # 首先尝试ping一下看是否能连通
                    import platform
                    if platform.system().lower() == 'windows':
                        ping_cmd = ['ping', '-n', '1', '-w', '2000', ip_address]
                    else:
                        ping_cmd = ['ping', '-c', '1', '-W', '2', ip_address]
                    
                    ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=5,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    
                    if ping_result.returncode != 0:
                        self._append_output(f"⚠️ 无法ping通 {ip_address}，但仍尝试连接HDC...\n")
                    
                    # 连接HDC
                    result = subprocess.run(['hdc', 'tconn', remote_address],
                                        capture_output=True, text=True, timeout=15,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if result.returncode == 0:
                        self._append_output(f"✅ 远程连接成功: {result.stdout.strip() if result.stdout else ''}\n")
                        
                        # 保存成功的连接信息
                        self.last_remote_connection = {
                            'ip': ip_address,
                            'port': port
                        }
                        # 自动保存配置
                        try:
                            self.save_config_silent()
                        except:
                            pass  # 忽略保存错误，不影响连接成功
                        
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        error_msg = result.stderr.strip() if result.stderr else f"连接失败，返回码: {result.returncode}"
                        self._append_output(f"❌ 远程连接失败: {error_msg}\n")
                        messagebox.showerror("连接失败", error_msg)
                except Exception as e:
                    self._append_output(f"❌ 连接异常: {str(e)}\n")
                    messagebox.showerror("连接异常", str(e))
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址和端口号")
                
        # 按钮区域 - 使用与主窗口一致的样式
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        ttk.Button(button_frame, text="🔗 连接鸿蒙设备", command=do_hdc_remote_connect, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        
        # 设置焦点到IP地址输入框
        ip_entry.focus()
        
        # 绑定窗口关闭事件
        dialog.protocol("WM_DELETE_WINDOW", self._on_legacy_wireless_window_close)

    def on_config_change(self):
        """配置变化时自动保存（带防抖）"""
        # 验证 max_steps 输入
        if hasattr(self, 'max_steps_entry'):
            max_steps_value = self.max_steps.get()
            if max_steps_value and (not max_steps_value.isdigit() or int(max_steps_value) < 1):
                self.max_steps.set("200")  # 重置为默认值
        
        if not hasattr(self, '_save_timer'):
            self._save_timer = None
        
        # 取消之前的定时器
        if self._save_timer:
            self.root.after_cancel(self._save_timer)
        
        # 设置新的定时器，延迟2秒后保存
        self._save_timer = self.root.after(2000, self._auto_save_config)
    
    def on_task_change(self):
        """任务文本变化时更新变量并自动保存（带防抖）"""
        task_text = self.task_text.get("1.0", tk.END).strip()
        self.task.set(task_text)
        self.on_config_change()
    
    def on_device_change(self):
        """设备选择变化时自动保存配置"""
        self.on_config_change()
    
    def show_task_simplifier(self):
        """显示任务精简器窗口"""
        # 获取当前任务文本
        current_task = self.task_text.get("1.0", tk.END).strip()
        
        if not current_task or current_task == "输入你想要执行的任务，例如：打开美团搜索附近的火锅店":
            messagebox.showwarning("提示", "请先输入要精简的任务描述")
            return
        
        # 创建精简任务对话框
        self.show_task_simplifier_dialog(current_task)
    
    def show_task_simplifier_dialog(self, current_task):
        """显示任务精简器对话框"""
        # 使用优化的居中窗口创建方法
        dialog = self.create_centered_toplevel(self.root, "🤖 AI润色器", 850, 650)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 加载上次选择的AI平台
        last_platform = self._load_last_selected_platform()
        
        # 创建主容器，无边距
        main_container = ttk.Frame(dialog)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 绑定ESC键关闭窗口
        dialog.bind('<Escape>', lambda e: (save_platform_selection(), dialog.destroy()))
        
        # 窗口关闭时保存选择
        dialog.protocol("WM_DELETE_WINDOW", lambda: (save_platform_selection(), dialog.destroy()))
        
        # 创建笔记本控件用于分页，无边距
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # === 精简任务页面 ===
        simplify_frame = ttk.Frame(notebook)
        notebook.add(simplify_frame, text="🚀 任务润色")
        
        simplify_container = ttk.Frame(simplify_frame, padding="15")
        simplify_container.pack(fill=tk.BOTH, expand=True)
        
        # 说明文字
        info_label = ttk.Label(simplify_container, text="使用AI润色任务描述，使其更加清晰和易于理解", 
                              font=('Microsoft YaHei', 10))
        info_label.pack(pady=(0, 10))
        
        # AI平台选择
        platform_frame = ttk.Frame(simplify_container)
        platform_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(platform_frame, text="选择AI平台:", font=('Microsoft YaHei', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        # 平台显示名称映射
        platform_display_map = {
            "deepseek": "DeepSeek",
            "doubao": "豆包", 
            "yuanbao": "元宝",
            "openai": "OpenAI",
            "gemini": "Gemini",
            "claude": "Claude",
            "glm": "智谱GLM",
            "wenxin": "文心千帆",
            "tongyi": "通义千问"
        }
        
        # 反向映射（从显示名称到实际值）
        display_to_platform = {v: k for k, v in platform_display_map.items()}
        
        # 获取显示名称列表
        display_values = [platform_display_map.get(p, p) for p in ["deepseek", "doubao", "yuanbao", "openai", "gemini", "claude", "glm", "wenxin", "tongyi"]]
        
        platform_var_display = tk.StringVar(value=platform_display_map.get(last_platform, last_platform))
        platform_combo = ttk.Combobox(platform_frame, textvariable=platform_var_display, 
                                      values=display_values,
                                      state="readonly", width=15)
        platform_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        def save_platform_selection():
            """保存用户选择的AI平台"""
            selected_display = platform_var_display.get()
            selected_platform = display_to_platform.get(selected_display, selected_display)
            self._save_last_selected_platform(selected_platform)
        
        # 绑定平台选择变化事件
        platform_combo.bind('<<ComboboxSelected>>', lambda e: save_platform_selection())
        
        def jump_to_config():
            """跳转到对应AI平台的配置页面"""
            notebook.select(1)  # 切换到API配置页面
            # 更新配置页面显示为当前选择的平台
            selected_display = platform_var_display.get()
            selected_platform = display_to_platform.get(selected_display, selected_display)
            config_platform_var_display.set(selected_display)
            update_config_display()
        
        config_btn = ttk.Button(platform_frame, text="⚙️ API配置", 
                               command=jump_to_config)
        config_btn.pack(side=tk.LEFT)
        
        # 任务区域容器
        tasks_container = ttk.Frame(simplify_container)
        tasks_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        tasks_container.columnconfigure(0, weight=1)
        tasks_container.columnconfigure(1, weight=1)
        tasks_container.rowconfigure(0, weight=1)
        
        # 原始任务
        original_frame = ttk.LabelFrame(tasks_container, text="📝 原始任务", padding="10")
        original_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        original_frame.columnconfigure(0, weight=1)
        original_frame.rowconfigure(0, weight=1)
        
        original_text = scrolledtext.ScrolledText(original_frame, height=10, wrap=tk.WORD, 
                                                font=('Microsoft YaHei', 9))
        original_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        original_text.insert("1.0", current_task)
        original_text.config(state=tk.DISABLED)
        
        # 润色结果
        result_frame = ttk.LabelFrame(tasks_container, text="✨ 润色结果", padding="10")
        result_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        result_text = scrolledtext.ScrolledText(result_frame, height=10, wrap=tk.WORD, 
                                               font=('Microsoft YaHei', 9))
        result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 按钮框架
        button_frame = ttk.Frame(simplify_container)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 状态变量
        status_var = tk.StringVar(value="准备就绪")
        status_label = ttk.Label(button_frame, textvariable=status_var)
        status_label.pack(side=tk.LEFT)
        
        def start_simplify():
            """开始润色任务"""
            def simplify_worker():
                try:
                    # 在主线程中更新状态
                    selected_display = platform_var_display.get()
                    platform = display_to_platform.get(selected_display, selected_display)
                    dialog.after(0, lambda: status_var.set(f"🔍 检查{selected_display}平台配置..."))
                    
                    # 检查是否有配置
                    if not self.task_simplifier.get_provider_status().get(platform, False):
                        dialog.after(0, lambda: status_var.set("⚠️ 配置未完成"))
                        dialog.after(0, lambda: messagebox.showwarning(
                            "配置提示", 
                            f"🔧 {selected_display}平台未配置\n\n请先在API配置页面设置：\n• API密钥\n• 接口地址\n• 模型名称\n\n配置完成后重试润色"
                        ))
                        dialog.after(0, lambda: status_var.set("❌ 配置未完成"))
                        return
                    
                    dialog.after(0, lambda: status_var.set(f"🤖 使用{selected_display}润色任务..."))
                    
                    # 使用任务润色器
                    result = self.task_simplifier.simplify_task(current_task, platform)
                    
                    if result.get("success"):
                        simplified = result.get("simplified_task", current_task)
                        dialog.after(0, lambda: result_text.delete("1.0", tk.END))
                        dialog.after(0, lambda: result_text.insert("1.0", simplified))
                        dialog.after(0, lambda: status_var.set("✅ 润色完成"))
                    else:
                        error = result.get("error", "未知错误")
                        provider = result.get("provider", platform_var.get())
                        field = result.get("field", "unknown")
                        
                        # 使用友好的错误提示
                        friendly_error = self._parse_simplify_error(error)
                        
                        # 如果是特定字段错误，提供更具体的指导
                        if field != "unknown":
                            field_guide = self._get_field_specific_guide(field, provider)
                            full_error = friendly_error + "\n\n" + field_guide
                        else:
                            full_error = friendly_error
                        
                        dialog.after(0, lambda: messagebox.showerror("润色失败", full_error))
                        dialog.after(0, lambda: status_var.set("❌ 润色失败"))
                
                except Exception as e:
                    # 解析错误信息并提供友好的中文提示
                    error_msg = self._parse_simplify_error(str(e))
                    dialog.after(0, lambda: messagebox.showerror("润色失败", error_msg))
                    dialog.after(0, lambda: status_var.set("❌ 润色失败"))
            
            # 在后台线程中执行润色
            threading.Thread(target=simplify_worker, daemon=True).start()
        
        def apply_result():
            """应用润色结果到主界面"""
            simplified = result_text.get("1.0", tk.END).strip()
            if simplified:
                self.task_text.delete("1.0", tk.END)
                self.task_text.insert("1.0", simplified)
                self.task.set(simplified)
                self.on_config_change()
                dialog.destroy()
            else:
                messagebox.showwarning("提示", "没有可应用的润色结果")
        
        # 按钮
        ttk.Button(button_frame, text="🚀 开始润色", command=start_simplify).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="✅ 应用结果", command=apply_result).pack(side=tk.RIGHT, padx=(5, 0))
        
        # === API配置页面 ===
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ API配置")
        
        config_container = ttk.Frame(config_frame, padding="15")
        config_container.pack(fill=tk.BOTH, expand=True)
        
        # 配置说明
        config_info = ttk.Label(config_container, 
                               text="选择要配置的AI平台，设置API密钥、接口地址、模型等参数", 
                               font=('Microsoft YaHei', 10))
        config_info.pack(pady=(0, 15))
        
        # 平台选择
        platform_select_frame = ttk.Frame(config_container)
        platform_select_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(platform_select_frame, text="选择平台:", 
                 font=('Microsoft YaHei', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        # API配置页面的平台选择也使用中文显示
        config_platform_var_display = tk.StringVar(value=platform_display_map.get(last_platform, last_platform))
        config_platform_combo = ttk.Combobox(platform_select_frame, textvariable=config_platform_var_display, 
                                           values=display_values,
                                           state="readonly", width=15)
        config_platform_combo.pack(side=tk.LEFT, padx=(0, 10))
        def on_config_platform_change():
            """配置页面平台选择变化时的处理"""
            update_config_display()
            # 同步到润色页面的平台选择
            selected_display = config_platform_var_display.get()
            platform_var_display.set(selected_display)
            # 保存选择
            selected_platform = display_to_platform.get(selected_display, selected_display)
            self._save_last_selected_platform(selected_platform)
        
        config_platform_combo.bind('<<ComboboxSelected>>', lambda e: on_config_platform_change())
        
        # 配置详情区域
        config_details_frame = ttk.LabelFrame(config_container, text="配置详情", padding="15")
        config_details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        config_details_frame.columnconfigure(1, weight=1)
        
        # 存储配置输入框
        config_entries = {}
        
        def update_config_display():
            """更新配置显示"""
            # 清除现有控件
            for widget in config_details_frame.winfo_children():
                widget.destroy()
            
            selected_display = config_platform_var_display.get()
            platform = display_to_platform.get(selected_display, selected_display)
            config_info = self._get_platform_config_info(platform)
            
            # 平台名称和链接
            header_frame = ttk.Frame(config_details_frame)
            header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
            header_frame.columnconfigure(1, weight=1)
            
            name_label = ttk.Label(header_frame, text=config_info['display_name'], 
                                 font=('Microsoft YaHei', 11, 'bold'))
            name_label.grid(row=0, column=0, sticky=tk.W)
            
            link_btn = ttk.Button(header_frame, text="🔗 获取API密钥", 
                                command=lambda url=config_info['url']: self._open_url(url))
            link_btn.grid(row=0, column=1, sticky=tk.E)
            
            # 调换顺序：API接口地址放在前面
            # API接口地址
            ttk.Label(config_details_frame, text="接口地址:", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=8, padx=(0, 10))
            
            url_entry = ttk.Entry(config_details_frame, width=60, font=('Microsoft YaHei', 9))
            url_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=8)
            url_entry.insert(0, config_info["default_base_url"])  # 填入默认地址
            
            # API密钥
            ttk.Label(config_details_frame, text="API密钥:", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=8, padx=(0, 10))
            
            key_frame = ttk.Frame(config_details_frame)
            key_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=8)
            key_frame.columnconfigure(0, weight=1)
            
            key_entry = ttk.Entry(key_frame, show="*", width=50, font=('Microsoft YaHei', 9))
            key_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            show_btn = ttk.Button(key_frame, text="👁️", width=3, 
                                 command=lambda e=key_entry: self._toggle_visibility(e))
            show_btn.grid(row=0, column=1, padx=(5, 0))
            
            # 模型名称
            ttk.Label(config_details_frame, text="模型名称:", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=8, padx=(0, 10))
            
            model_entry = ttk.Entry(config_details_frame, width=60, font=('Microsoft YaHei', 9))
            model_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=8)
            model_entry.insert(0, config_info["default_model"])  # 填入默认模型
            
            # 其他参数
            param_frame = ttk.Frame(config_details_frame)
            param_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
            param_frame.columnconfigure(1, weight=1)
            param_frame.columnconfigure(3, weight=1)
            param_frame.columnconfigure(5, weight=1)
            
            # 超时设置
            ttk.Label(param_frame, text="超时(秒):", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            
            timeout_entry = ttk.Entry(param_frame, width=15, font=('Microsoft YaHei', 9))
            timeout_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
            timeout_entry.insert(0, str(config_info["default_timeout"]))
            
            # 最大Token数
            ttk.Label(param_frame, text="最大Token:", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
            
            tokens_entry = ttk.Entry(param_frame, width=15, font=('Microsoft YaHei', 9))
            tokens_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
            tokens_entry.insert(0, str(config_info["default_max_tokens"]))
            
            # 温度参数
            ttk.Label(param_frame, text="温度参数:", 
                     font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
            
            temp_entry = ttk.Entry(param_frame, width=15, font=('Microsoft YaHei', 9))
            temp_entry.grid(row=0, column=5, sticky=tk.W)
            temp_entry.insert(0, str(config_info["default_temperature"]))
            
            # 保存输入框引用
            config_entries[platform] = {
                'api_key': key_entry,
                'base_url': url_entry,
                'model': model_entry,
                'timeout': timeout_entry,
                'max_tokens': tokens_entry,
                'temperature': temp_entry
            }
            
            # 加载现有配置
            self._load_platform_config(platform, config_entries[platform])
        
        # 初始化显示
        update_config_display()
        
        # 保存配置按钮
        save_frame = ttk.Frame(config_container)
        save_frame.pack(fill=tk.X)
        
        def save_config():
            """保存当前平台的配置"""
            platform = config_platform_var.get()
            if platform in config_entries:
                try:
                    # 读取所有平台的配置
                    all_configs = self._load_all_configs()
                    
                    # 更新当前平台配置
                    entries = config_entries[platform]
                    all_configs[platform] = {
                        "api_key": entries['api_key'].get(),
                        "base_url": entries['base_url'].get(),
                        "model": entries['model'].get(),
                        "timeout": int(entries['timeout'].get() or 30),
                        "max_tokens": int(entries['max_tokens'].get() or 200),
                        "temperature": float(entries['temperature'].get() or 0.1)
                    }
                    
                    # 保存到文件
                    with open("ai_config.json", 'w', encoding='utf-8') as f:
                        json.dump(all_configs, f, ensure_ascii=False, indent=2)
                    
                    config_info = self._get_platform_config_info(platform)
                    messagebox.showinfo("成功", f"{config_info['display_name']} 配置已保存")
                    # 重新加载任务精简器配置
                    self.task_simplifier.load_config()
                except Exception as e:
                    error_msg = self._parse_config_error(str(e))
                    messagebox.showerror("保存失败", error_msg)
        
        ttk.Button(save_frame, text="💾 保存配置", command=save_config).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(save_frame, text="❌ 关闭", command=dialog.destroy).pack(side=tk.RIGHT)
        

    
    def _get_platform_config_info(self, platform):
        """获取平台配置信息"""
        platform_configs = {
            "deepseek": {
                "display_name": "DeepSeek",
                "url": "https://platform.deepseek.com/api_keys",
                "default_base_url": "https://api.deepseek.com",
                "default_model": "deepseek-chat",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "doubao": {
                "display_name": "豆包",
                "url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
                "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "default_model": "ep-20241219143532-qz8wg",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "yuanbao": {
                "display_name": "腾讯元宝",
                "url": "https://cloud.tencent.com/product/hunyuan",
                "default_base_url": "https://api.hunyuan.cloud.tencent.com/v1",
                "default_model": "hunyuan-turbos-latest",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "openai": {
                "display_name": "OpenAI",
                "url": "https://platform.openai.com/api-keys",
                "default_base_url": "https://api.openai.com/v1",
                "default_model": "gpt-3.5-turbo",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "gemini": {
                "display_name": "Google Gemini",
                "url": "https://aistudio.google.com/app/apikey",
                "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
                "default_model": "gemini-1.5-flash",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "claude": {
                "display_name": "Anthropic Claude",
                "url": "https://console.anthropic.com/",
                "default_base_url": "https://api.anthropic.com/v1",
                "default_model": "claude-3-haiku-20240307",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "glm": {
                "display_name": "智谱GLM",
                "url": "https://open.bigmodel.cn/usercenter/apikey",
                "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
                "default_model": "glm-4-flash",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "wenxin": {
                "display_name": "百度文心千帆",
                "url": "https://console.bce.baidu.com/ai/#/ai/ernie/overview/index",
                "default_base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-lite-8k",
                "default_model": "ernie-lite-8k",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            },
            "tongyi": {
                "display_name": "阿里通义千问",
                "url": "https://dashscope.console.aliyun.com/api-key",
                "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "default_model": "qwen-plus",
                "default_timeout": 30,
                "default_max_tokens": 200,
                "default_temperature": 0.1
            }
        }
        return platform_configs.get(platform, platform_configs["deepseek"])
    
    def _load_all_configs(self):
        """加载所有平台配置"""
        try:
            if os.path.exists("ai_config.json"):
                with open("ai_config.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
        return {}
    
    def _load_platform_config(self, platform, entries):
        """加载指定平台的配置"""
        try:
            configs = self._load_all_configs()
            if platform in configs:
                config = configs[platform]
                config_info = self._get_platform_config_info(platform)
                
                entries['api_key'].delete(0, tk.END)
                entries['api_key'].insert(0, config.get("api_key", ""))
                
                entries['base_url'].delete(0, tk.END)
                entries['base_url'].insert(0, config.get("base_url", config_info["default_base_url"]))
                
                entries['model'].delete(0, tk.END)
                entries['model'].insert(0, config.get("model", config_info["default_model"]))
                
                entries['timeout'].delete(0, tk.END)
                entries['timeout'].insert(0, str(config.get("timeout", config_info["default_timeout"])))
                
                entries['max_tokens'].delete(0, tk.END)
                entries['max_tokens'].insert(0, str(config.get("max_tokens", config_info["default_max_tokens"])))
                
                entries['temperature'].delete(0, tk.END)
                entries['temperature'].insert(0, str(config.get("temperature", config_info["default_temperature"])))
            else:
                # 加载默认配置
                config_info = self._get_platform_config_info(platform)
                entries['base_url'].insert(0, config_info["default_base_url"])
                entries['model'].insert(0, config_info["default_model"])
                entries['timeout'].insert(0, str(config_info["default_timeout"]))
                entries['max_tokens'].insert(0, str(config_info["default_max_tokens"]))
                entries['temperature'].insert(0, str(config_info["default_temperature"]))
        except Exception as e:
            print(f"加载平台配置失败: {e}")
    
    def _toggle_visibility(self, entry):
        """切换输入框显示/隐藏"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def _load_api_configs(self, api_entries):
        """加载现有的API配置（保留兼容性）"""
        try:
            if os.path.exists("ai_config.json"):
                with open("ai_config.json", 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                for key, entry in api_entries.items():
                    if key in config_data and config_data[key].get("api_key"):
                        entry.delete(0, tk.END)
                        entry.insert(0, config_data[key]["api_key"])
        except Exception as e:
            print(f"加载API配置失败: {e}")
    
    def _open_url(self, url):
        """打开URL链接"""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接: {str(e)}")
    
    def set_ios_device_ip(self):
        """设置iOS设备IP地址"""
        # 防止重复打开窗口的机制
        if hasattr(self, '_ios_ip_dialog_open') and self._ios_ip_dialog_open:
            return
        self._ios_ip_dialog_open = True
        
        # 使用优化的居中窗口创建方法
        dialog = self.create_centered_toplevel(self.root, "🍎 iOS设备IP设置", 520, 360)
        dialog.transient(self.root)  # 设置为父窗口的子窗口
        dialog.grab_set()  # 模态对话框
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="🍎 设置iOS设备IP地址", 
                               font=('Microsoft YaHei', 11, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # IP地址输入框架
        config_frame = ttk.LabelFrame(main_frame, text="🌐 设备配置", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # IP地址输入
        ttk.Label(config_frame, text="设备IP地址:", font=('Microsoft YaHei', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ip_var = tk.StringVar(value=self.ios_device_ip.get())
        ip_entry = ttk.Entry(config_frame, textvariable=ip_var, width=20, font=('Microsoft YaHei', 10))
        ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        # 说明文字
        info_frame = ttk.LabelFrame(main_frame, text="📋 连接说明", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        info_text = "• 默认地址: localhost (USB连接)\n• 本地连接: 127.0.0.1 (本地测试)\n• 无线连接: 192.168.x.x (WiFi连接)\n• 确保WebDriverAgent运行在8100端口"
        info_label = ttk.Label(info_frame, text=info_text, font=('Microsoft YaHei', 9), foreground='gray', justify=tk.LEFT)
        info_label.pack(anchor=tk.W, fill=tk.BOTH, expand=True)
        
        # 按钮框架 - 使用更好的布局
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))  # 添加上边距
        
        def save_ip():
            ip_address = ip_var.get().strip()
            if ip_address:
                self.ios_device_ip.set(ip_address)
                self._append_output(f"🍎 iOS设备IP已设置为: {ip_address}\n")
                
                # 更新设备状态显示
                if hasattr(self, 'device_status_label'):
                    self.device_status_label.config(text=f"iOS设备IP: {ip_address}")
                
                # 自动保存配置
                self.on_config_change()
                
                # 重置标志并关闭对话框
                self._ios_ip_dialog_open = False
                dialog.destroy()
                messagebox.showinfo("成功", f"✅ iOS设备IP已设置为: {ip_address}")
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址")
        
        # 按钮 - 确保正确显示
        save_button = ttk.Button(button_frame, text="💾 保存", command=save_ip)
        save_button.pack(side=tk.LEFT, padx=8, ipadx=10, ipady=5)  # 增加内边距
        
        cancel_button = ttk.Button(button_frame, text="❌ 取消", command=dialog.destroy)
        cancel_button.pack(side=tk.LEFT, padx=8, ipadx=10, ipady=5)  # 增加内边距
        
        # 设置焦点到IP地址输入框
        ip_entry.focus()
        
        # 绑定窗口关闭事件
        def on_dialog_close():
            self._ios_ip_dialog_open = False
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        # 如果是取消按钮，也需要重置标志
        def on_cancel():
            self._ios_ip_dialog_open = False
            dialog.destroy()
        cancel_button.config(command=on_cancel)
        
        ip_entry.select_range(0, tk.END)

    def on_device_type_change(self):
        """设备类型变化时更新相关设置"""
        # 防重复机制：如果设备类型没有实际变化，则跳过扫描
        current_device_type = self.device_type.get()
        if hasattr(self, '_last_device_type') and self._last_device_type == current_device_type:
            # 设备类型没有变化，只保存配置
            self.on_config_change()
            return
        
        self._last_device_type = current_device_type
        
        # 将中文选项转换为英文值用于内部处理
        if current_device_type == "安卓":
            device_type_en = "adb"
        elif current_device_type == "鸿蒙":
            device_type_en = "hdc"
        elif current_device_type == "iOS":
            device_type_en = "ios"
        else:
            device_type_en = "adb"  # 默认
        
        # 清空设备列表
        self.connected_devices = []
        self.selected_device_id.set("")
        
        # 更新设备管理区域的标题和按钮
        if hasattr(self, 'adb_frame'):
            if hasattr(self, 'adb_control_frame'):
                # 获取所有按钮，保存它们的属性
                buttons_info = []
                for widget in self.adb_control_frame.winfo_children():
                    if isinstance(widget, ttk.Button):
                        text = widget.cget('text')
                        is_visible = widget.winfo_viewable()
                        buttons_info.append((widget, text, is_visible))
                
                # 处理每个按钮
                for widget, text, is_visible in buttons_info:
                    if device_type_en == "hdc":
                        self.adb_frame.config(text="📱 HDC设备管理")
                        # HDC模式：修改连接按钮，隐藏ADB键盘按钮和远程桌面按钮
                        if "连接ADB" in text:
                            widget.config(text="🔗 连接HDC")
                        elif ("安装ADB键盘" in text or "远程桌面" in text) and is_visible:
                            widget.pack_forget()
                    elif device_type_en == "ios":
                        self.adb_frame.config(text="🍎 iOS设备管理")
                        # iOS模式：修改连接按钮为设置IP，隐藏ADB相关按钮
                        if "连接ADB" in text or "连接HDC" in text:
                            widget.config(text="🌐 设置设备IP")
                            # 延迟绑定命令，避免在选择设备类型时自动触发
                            def safe_bind_command():
                                try:
                                    # 确保按钮仍然存在且可见
                                    if widget.winfo_exists():
                                        widget.config(command=self.set_ios_device_ip)
                                except Exception as e:
                                    print(f"绑定iOS IP设置命令失败: {e}")
                            self.root.after(100, safe_bind_command)
                        elif ("安装ADB键盘" in text or "远程桌面" in text) and is_visible:
                            widget.pack_forget()
                    else:
                        self.adb_frame.config(text="📱 ADB设备管理")
                        # ADB模式：修改连接按钮，显示ADB键盘按钮和远程桌面按钮
                        if "连接HDC" in text:
                            widget.config(text="🔗 连接ADB", command=self.connect_adb_device)
                        elif "设置设备IP" in text:
                            widget.config(text="🔗 连接ADB", command=self.connect_adb_device)
                        elif "安装ADB键盘" in text and not is_visible:
                            widget.pack(side=tk.LEFT, padx=(0, 8))
                        elif "远程桌面" in text and not is_visible:
                            widget.pack(side=tk.LEFT, padx=(0, 8))
                
                # 确保关注公众号按钮始终在最后
                for widget, text, is_visible in buttons_info:
                    if "关注公众号" in text:
                        # 重新打包到最后
                        widget.pack_forget()
                        widget.pack(side=tk.LEFT, padx=(0, 8))
                        break
        
        # 更新设备扫描命令和标签
        if hasattr(self, 'device_status_label'):
            if device_type_en == "hdc":
                device_type_text = "HDC设备"
            elif device_type_en == "ios":
                device_type_text = "iOS设备"
                # 如果已经设置了IP，显示当前IP
                current_ip = self.ios_device_ip.get()
                if current_ip and current_ip != "localhost":
                    self.device_status_label.config(text=f"iOS设备IP: {current_ip}")
                else:
                    self.device_status_label.config(text="iOS设备未配置IP")
            else:
                device_type_text = "ADB设备"
                self.device_status_label.config(text=f"未连接{device_type_text}")
        
        # 只对非iOS设备进行设备扫描
        if device_type_en != "ios":
            self.refresh_devices()
        
        # 控制自动唤醒按钮的显示/隐藏（仅在安卓设备时显示）
        if hasattr(self, 'pwd_button'):
            if device_type_en == "adb":
                # 安卓设备：显示自动唤醒按钮
                self.pwd_button.grid()
            else:
                # 鸿蒙和iOS设备：隐藏自动唤醒按钮
                self.pwd_button.grid_remove()
        
        # 自动保存配置
        self.on_config_change()
    

    
    def _auto_save_config(self):
        """自动保存配置（静默保存，不显示提示）"""
        try:
            config = {
                'base_url': self.base_url.get(),
                'model': self.model.get(),
                'apikey': self.apikey.get(),
                'task': self.task_text.get("1.0", tk.END).strip(),
                'max_steps': int(self.max_steps.get() or 200),
                'temperature': float(self.temperature.get() or 0.0),
                'device_type': (lambda: {
                    "安卓": "adb", 
                    "iOS": "ios", 
                    "鸿蒙": "hdc"
                }.get(self.device_type.get(), "adb"))(),
                'selected_device': self.selected_device_id.get(),  # 保存用户选择的设备ID（不是环境变量）
                'remote_connection': getattr(self, 'last_remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'wireless_pair': getattr(self, 'last_wireless_pair', {
                    'pair_address': '10.10.10.100:41717',
                    'connect_address': '10.10.10.100:5555'
                }),
                'legacy_wireless': getattr(self, 'last_legacy_wireless', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'ios_device_ip': getattr(self, 'ios_device_ip', None).get() if hasattr(self, 'ios_device_ip') else "localhost"
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 静默更新状态，不显示弹窗
            if hasattr(self, 'status_var'):
                self.root.after(0, lambda: self.status_var.set("✅ 配置已自动保存"))
                # 3秒后恢复状态
                self.root.after(3000, lambda: self.status_var.set("✅ 就绪"))
                
        except Exception:
            pass  # 静默忽略错误，不影响用户体验
    
    def _parse_simplify_error(self, error_str):
        """解析润色任务的错误信息，提供友好的中文提示"""
        error_lower = error_str.lower()
        
        # 参数格式错误（新增）
        if "格式错误" in error_str or "format" in error_lower:
            if "api" in error_lower and ("key" in error_lower or "密钥" in error_str):
                return "🔑 API密钥格式错误\n\n请检查：\n• API密钥格式是否正确（如：sk-xxxxx）\n• 是否复制完整\n• 是否包含多余空格或字符\n\n💡 提示：从API服务商平台重新复制密钥"
            
            if "url" in error_lower or "接口地址" in error_str:
                return "🌐 接口地址格式错误\n\n请检查：\n• 地址必须以http://或https://开头\n• 域名是否正确（如api.deepseek.com）\n• 是否有拼写错误\n\n💡 示例：https://api.deepseek.com"
            
            if "模型" in error_str or "model" in error_lower:
                return "🤖 模型名称格式错误\n\n请检查：\n• 模型名称是否正确\n• 是否拼写完整\n• 是否区分大小写\n\n💡 常用模型：\n• DeepSeek: deepseek-chat\n• OpenAI: gpt-3.5-turbo"
        
        # 参数范围错误（新增）
        if "设置不合理" in error_str or "range" in error_lower:
            if "超时" in error_str or "timeout" in error_lower:
                return "⏰ 超时设置不合理\n\n建议设置：\n• 最小值：1秒\n• 最大值：300秒\n• 推荐值：30秒\n\n💡 网络较慢时可适当增加"
            
            if "token" in error_lower:
                return "📊 Token数设置不合理\n\n建议设置：\n• 最小值：1\n• 最大值：8000\n• 推荐值：200-500\n\n💡 任务简单时可设置小一些"
            
            if "温度" in error_str or "temperature" in error_lower:
                return "🌡️ 温度参数不合理\n\n建议设置：\n• 最小值：0（最准确）\n• 最大值：2（最创意）\n• 推荐值：0.1-0.3\n\n💡 任务精简建议使用低温度值"
        
        # 网络相关错误
        if "timeout" in error_lower or "timed out" in error_lower:
            return "🌐 网络连接超时\n\n请检查：\n• 网络连接是否正常\n• API服务是否可用\n• 请求是否超时（可尝试增加timeout设置）\n\n💡 建议将超时设置为60秒"
        
        if "connection" in error_lower and "refused" in error_lower:
            return "🔌 连接被拒绝\n\n请检查：\n• API地址是否正确\n• 防火墙是否阻止连接\n• API服务是否正常运行\n\n💡 尝试在浏览器中访问API地址"
        
        if "dns" in error_lower or "name" in error_lower and "resolve" in error_lower:
            return "🌍 DNS解析失败\n\n请检查：\n• 网络连接是否正常\n• API地址是否正确\n• DNS服务器是否可用\n\n💡 尝试切换网络或DNS"
        
        # API密钥相关错误
        if "api" in error_lower and ("key" in error_lower or "token" in error_lower or "密钥" in error_str):
            if "invalid" in error_lower or "unauthorized" in error_lower or "无效" in error_str:
                return "🔑 API密钥无效\n\n请检查：\n• API密钥是否正确\n• 密钥是否已过期\n• 账户是否有足够权限\n• 是否选择了正确的AI平台\n\n💡 重新从API服务商获取密钥"
            if "missing" in error_lower or "required" in error_lower or "为空" in error_str:
                return "🔑 缺少API密钥\n\n请先在配置页面设置正确的API密钥\n\n💡 点击API配置页面 → 选择平台 → 输入密钥"
            if "长度不足" in error_str or "length" in error_lower:
                return "🔑 API密钥长度不足\n\n请检查：\n• 是否复制完整\n• 是否被截断\n• 是否包含完整字符\n\n💡 重新复制完整的API密钥"
        
        # 配置相关错误
        if "config" in error_lower and ("not" in error_lower or "missing" in error_lower):
            return "⚙️ 配置错误\n\n请检查：\n• 是否已完成API配置\n• 配置文件是否存在\n• 配置格式是否正确\n\n💡 在API配置页面重新设置"
        
        # 模型相关错误
        if "model" in error_lower or "模型" in error_str:
            if "not" in error_lower and ("found" in error_lower or "exist" in error_lower):
                return "🤖 模型不存在\n\n请检查：\n• 模型名称是否正确\n• 是否选择了支持的模型\n• API服务商是否提供该模型\n\n💡 查看API文档确认可用模型"
            if "not" in error_lower and ("available" in error_lower or "accessible" in error_lower):
                return "🤖 模型不可用\n\n请检查：\n• 账户是否有该模型权限\n• 模型是否在当前地区可用\n• API配额是否充足\n\n💡 尝试其他可用模型"
            if "名称不正确" in error_str:
                return "🤖 模型名称不正确\n\n请检查模型名称拼写和格式\n\n💡 参考正确格式：\n• DeepSeek: deepseek-chat\n• OpenAI: gpt-3.5-turbo\n• 豆包: ep-xxxxx"
        
        # 接口地址相关错误
        if "base_url" in error_lower or "接口地址" in error_str:
            if "不正确" in error_str or "incorrect" in error_lower:
                return "🌐 接口地址不正确\n\n请检查：\n• 地址拼写是否正确\n• 是否包含正确的域名\n• 域名后缀是否正确\n\n💡 对照官方文档核对地址"
        
        # 请求相关错误
        if "request" in error_lower and ("failed" in error_lower or "error" in error_lower):
            if "400" in error_str or "bad" in error_lower and "request" in error_lower:
                return "📤 请求参数错误\n\n请检查：\n• 请求格式是否正确\n• 参数是否符合API要求\n• 任务描述是否过长或包含特殊字符\n\n💡 尝试简化任务描述"
            if "401" in error_str or "unauthorized" in error_lower:
                return "🔐 认证失败\n\n请检查：\n• API密钥是否正确\n• 认证方式是否符合要求\n\n💡 重新设置API密钥"
            if "403" in error_str or "forbidden" in error_lower:
                return "🚫 访问被禁止\n\n请检查：\n• 账户权限是否足够\n• API配额是否充足\n• 是否有访问该功能的权限\n\n💡 检查账户余额和权限"
            if "429" in error_str or "rate" in error_lower and ("limit" in error_lower or "exceed" in error_lower):
                return "⏰ 请求频率超限\n\n请稍后再试，或检查：\n• API配额是否充足\n• 请求频率是否过高\n\n💡 等待几分钟后重试"
            if "500" in error_str or "internal" in error_lower and "error" in error_lower:
                return "🏢 服务器内部错误\n\n这通常是API服务商的问题，请：\n• 稍后重试\n• 联系API服务商\n• 尝试切换其他AI平台"
        
        # 任务相关错误
        if "task" in error_lower:
            return "📝 任务处理错误\n\n请检查：\n• 任务描述是否清晰合理\n• 任务长度是否适中\n• 是否包含敏感或违规内容\n\n💡 尝试简化或改写任务描述"
        
        # 通用错误处理
        if "file" in error_lower and ("not" in error_lower or "missing" in error_lower):
            return "📁 文件错误\n\n请检查：\n• 配置文件是否存在\n• 文件权限是否正确\n• 文件路径是否有效\n\n💡 重新启动程序"
        
        if "json" in error_lower and ("decode" in error_lower or "parse" in error_lower):
            return "📋 数据解析错误\n\n请检查：\n• API返回数据格式是否正确\n• 配置文件格式是否有效\n\n💡 重新设置配置"
        
        # 默认错误信息（包含原始错误但更友好）
        return f"❌ 未知错误\n\n原始错误信息：{error_str}\n\n建议：\n• 检查网络连接\n• 验证API配置\n• 重启程序后重试\n• 如问题持续，请联系技术支持\n\n💡 常见问题：\n• API密钥格式错误\n• 接口地址拼写错误\n• 模型名称不正确\n• 参数范围设置不合理"
    
    def _get_field_specific_guide(self, field: str, provider: str) -> str:
        """根据错误字段提供具体的修复指导"""
        
        guides = {
            "api_key": {
                "deepseek": "🔑 DeepSeek API密钥设置指导：\n\n1. 访问 https://platform.deepseek.com/api_keys\n2. 创建或复制API密钥\n3. 确保密钥格式为：sk-xxxxxxxxxx\n4. 检查密钥是否完整复制\n5. 验证密钥是否已激活",
                
                "openai": "🔑 OpenAI API密钥设置指导：\n\n1. 访问 https://platform.openai.com/api-keys\n2. 创建新的API密钥\n3. 确保密钥格式为：sk-xxxxxxxxxx\n4. 检查账户余额是否充足\n5. 验证API权限设置",
                
                "doubao": "🔑 豆包API密钥设置指导：\n\n1. 访问 https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey\n2. 创建或复制API密钥\n3. 确保密钥长度充足\n4. 检查账户状态和配额\n5. 验证项目权限设置",
                
                "wenxin": "🔑 文心千帆API密钥设置指导：\n\n1. 访问 https://console.bce.baidu.com/ai/#/ai/ernie/overview/index\n2. 创建应用获取API Key和Secret Key\n3. 使用API Key和Secret Key获取access_token\n4. 检查账户状态和配额\n5. 验证应用权限设置",
                
                "tongyi": "🔑 通义千问API密钥设置指导：\n\n1. 访问 https://dashscope.console.aliyun.com/api-key\n2. 创建新的API密钥\n3. 确保密钥格式为sk-xxxxxxxxxx\n4. 检查账户余额和配额\n5. 验证服务权限和开通状态",
                
                "default": "🔑 API密钥设置指导：\n\n1. 登录对应AI服务商平台\n2. 进入API密钥管理页面\n3. 创建或获取新的API密钥\n4. 确保密钥格式正确\n5. 检查密钥权限和状态"
            },
            
            "base_url": {
                "deepseek": "🌐 DeepSeek接口地址设置：\n\n正确格式：https://api.deepseek.com\n\n常见错误：\n• 缺少https://前缀\n• 拼写错误（如deekseek）\n• 多余的路径或参数",
                
                "openai": "🌐 OpenAI接口地址设置：\n\n正确格式：https://api.openai.com/v1\n\n常见错误：\n• 缺少https://前缀\n• 拼写错误\n• 缺少/v1路径",
                
                "doubao": "🌐 豆包接口地址设置：\n\n正确格式：https://ark.cn-beijing.volces.com/api/v3\n\n常见错误：\n• 地区设置错误\n• API版本不正确\n• 域名拼写错误",
                
                "wenxin": "🌐 文心千帆接口地址设置：\n\n正确格式：https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-lite-8k\n\n常见错误：\n• 模型名称错误\n• 缺少access_token\n• 接口版本不正确",
                
                "tongyi": "🌐 通义千问接口地址设置：\n\n正确格式：https://dashscope.aliyuncs.com/compatible-mode/v1\n\n常见错误：\n• 使用了非兼容模式地址\n• 地区设置错误\n• API版本不正确",
                
                "default": "🌐 接口地址设置指导：\n\n1. 确保以http://或https://开头\n2. 检查域名拼写是否正确\n3. 验证路径和版本\n4. 参考官方文档确认"
            },
            
            "model": {
                "deepseek": "🤖 DeepSeek模型名称：\n\n常用模型：\n• deepseek-chat（对话模型）\n• deepseek-coder（代码模型）\n\n注意事项：\n• 模型名称区分大小写\n• 确保账户有该模型权限",
                
                "openai": "🤖 OpenAI模型名称：\n\n常用模型：\n• gpt-3.5-turbo（推荐）\n• gpt-4\n• gpt-4-turbo\n• gpt-4o\n\n注意事项：\n• 确保模型可用性\n• 检查账户权限",
                
                "doubao": "🤖 豆包模型名称：\n\n常用格式：\n• ep-xxxxxxxxxx（端点ID）\n• doubao-pro-4k\n• doubao-pro-32k\n\n注意事项：\n• 需要先创建推理端点\n• 确保端点状态正常",
                
                "wenxin": "🤖 文心千帆模型名称：\n\n常用模型：\n• ernie-lite-8k（轻量级）\n• ernie-tiny-8k（超轻量）\n• ernie-speed-8k（速度版）\n• ernie-4.0-8k（最新版）\n\n注意事项：\n• 不同模型性能和价格不同\n• 确保账户有该模型权限",
                
                "tongyi": "🤖 通义千问模型名称：\n\n常用模型：\n• qwen-plus（推荐）\n• qwen-turbo（快速版）\n• qwen-max（最强版）\n• qwen-long（长文本）\n\n注意事项：\n• 模型名称区分大小写\n• 确保账户有该模型权限",
                
                "default": "🤖 模型名称设置：\n\n1. 查看API文档确认可用模型\n2. 检查模型名称拼写\n3. 验证大小写格式\n4. 确保账户有使用权限"
            },
            
            "timeout": "⏰ 超时设置指导：\n\n建议范围：1-300秒\n• 网络良好：30秒\n• 网络较慢：60秒\n• 复杂任务：90-120秒\n\n注意：超时时间过长可能影响体验",
            
            "max_tokens": "📊 最大Token数设置：\n\n建议范围：1-8000\n• 简单任务：200-500\n• 复杂任务：500-2000\n• 长文本处理：2000-4000\n\n注意：Token数影响输出长度",
            
            "temperature": "🌡️ 温度参数设置：\n\n建议范围：0.0-2.0\n• 精准任务：0.1-0.3\n• 平衡任务：0.5-0.7\n• 创意任务：1.0-1.5\n\n注意：任务精简建议使用低温度值",
            
            "default": "⚙️ 参数设置指导：\n\n1. 参考官方文档\n2. 使用推荐值\n3. 根据实际需求调整\n4. 验证参数有效性"
        }
        
        # 获取平台特定的指导
        if field in guides:
            platform_guide = guides[field].get(provider, guides[field].get("default", ""))
            return platform_guide
        else:
            return guides.get("default", "")
    
    def _parse_config_error(self, error_str):
        """解析配置保存的错误信息，提供友好的中文提示"""
        error_lower = error_str.lower()
        
        if "permission" in error_lower and "denied" in error_lower:
            return "🔒 权限不足\n\n请检查：\n• 程序是否有写入权限\n• 是否被安全软件阻止\n• 尝试以管理员身份运行"
        
        if "disk" in error_lower and ("full" in error_lower or "space" in error_lower):
            return "💾 磁盘空间不足\n\n请清理磁盘空间后重试"
        
        if "file" in error_lower and ("not" in error_lower or "missing" in error_lower):
            return "📁 文件路径错误\n\n请检查：\n• 程序目录是否存在\n• 文件路径是否有效"
        
        if "json" in error_lower and ("encode" in error_lower or "decode" in error_lower):
            return "📋 配置格式错误\n\n配置数据格式异常，请重置配置"
        
        return f"❌ 配置保存失败\n\n原始错误：{error_str}\n\n建议：\n• 检查磁盘空间\n• 验证写入权限\n• 重启程序后重试"

    def on_closing(self):
        """程序关闭时的处理，自动保存配置"""
        try:
            # 立即保存当前配置
            config = {
                'base_url': self.base_url.get(),
                'model': self.model.get(),
                'apikey': self.apikey.get(),
                'task': self.task_text.get("1.0", tk.END).strip(),
                'max_steps': int(self.max_steps.get() or 200),
                'temperature': float(self.temperature.get() or 0.0),
                'device_type': (lambda: {
                    "安卓": "adb", 
                    "iOS": "ios", 
                    "鸿蒙": "hdc"
                }.get(self.device_type.get(), "adb"))(),
                'selected_device': self.selected_device_id.get(),  # 保存用户选择的设备ID（不是环境变量）
                'remote_connection': getattr(self, 'last_remote_connection', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'wireless_pair': getattr(self, 'last_wireless_pair', {
                    'pair_address': '10.10.10.100:41717',
                    'connect_address': '10.10.10.100:5555'
                }),
                'legacy_wireless': getattr(self, 'last_legacy_wireless', {
                    'ip': '192.168.1.100',
                    'port': '5555'
                }),
                'ios_device_ip': getattr(self, 'ios_device_ip', None).get() if hasattr(self, 'ios_device_ip') else "localhost"
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 保存任务历史记录
            self.save_task_history()
                
        except Exception:
            pass  # 静默忽略错误，确保程序能正常关闭
        
        # 如果有正在运行的任务，停止它
        if self.running:
            self.running = False
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
        
        # 销毁窗口，退出程序
        self.root.destroy()
    
    def _load_last_selected_platform(self):
        """加载上次选择的AI平台"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'gui_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('last_selected_ai_platform', 'deepseek')
        except Exception as e:
            print(f"加载上次选择的AI平台失败: {e}")
        return 'deepseek'
    
    def _save_last_selected_platform(self, platform):
        """保存用户选择的AI平台"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'gui_config.json')
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            config['last_selected_ai_platform'] = platform
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存上次选择的AI平台失败: {e}")


    def load_task_history(self):
        """加载任务历史记录"""
        try:
            if os.path.exists(self.task_history_file):
                with open(self.task_history_file, 'r', encoding='utf-8') as f:
                    self.task_history = json.load(f)
        except Exception as e:
            print(f"加载任务历史失败: {e}")
            self.task_history = []
    
    def save_task_history(self):
        """保存任务历史记录"""
        try:
            with open(self.task_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.task_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务历史失败: {e}")
    
    def add_task_to_history(self, task):
        """添加任务到历史记录"""
        try:
            # 规范化任务文本，去除多余空白
            normalized = ' '.join(task.split()) if isinstance(task, str) else str(task)
            if not normalized:
                return

            # 如果历史不为空，检查最近一条是否与当前相同（避免重复添加）
            if self.task_history:
                try:
                    last_task = self.task_history[0].get('task', '')
                    last_norm = ' '.join(last_task.split()) if isinstance(last_task, str) else str(last_task)
                    if last_norm == normalized:
                        return
                except Exception:
                    pass

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task_record = {
                'task': normalized,
                'timestamp': current_time,
                'id': len(self.task_history) + 1
            }

            # 添加到历史记录开头
            self.task_history.insert(0, task_record)
            
            # 保持历史记录不超过50条
            if len(self.task_history) > 50:
                self.task_history = self.task_history[:50]
            
            self.save_task_history()
            
        except Exception as e:
            print(f"添加任务历史失败: {e}")
    
    def show_task_history(self):
        """显示任务历史窗口"""
        # 使用优化的居中窗口创建方法
        history_window = self.create_centered_toplevel(self.root, "📚 任务历史记录", 900, 550)
        history_window.transient(self.root)
        history_window.grab_set()
        
        # 居中显示窗口
        self.center_window(history_window)
        
 # 主框架
        main_frame = ttk.Frame(history_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="📚 任务历史记录", 
                 font=('Microsoft YaHei', 14, 'bold')).pack(side=tk.LEFT)
        
        # 创建表格框架来包含tree和滚动条
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview显示历史记录，启用多选
        columns = ('时间', '任务')
        tree = ttk.Treeview(table_frame, columns=columns, show='tree headings', height=12, selectmode='extended')
        
        # 设置列标题和宽度
        tree.heading('#0', text='')
        tree.heading('时间', text='执行时间')
        tree.heading('任务', text='任务内容')
        
        tree.column('#0', width=0, stretch='NO')  # 隐藏树形列
        tree.column('时间', width=150, anchor='center')
        tree.column('任务', width=650, anchor='w')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 填充数据
        for record in self.task_history:
            # 显示完整的任务内容，仅在表格中适当截断用于显示
            task_content = record.get('task', '')
            display_task = task_content
            if len(display_task) > 100:
                display_task = display_task[:97] + "..."
            
            tree.insert('', 'end', values=(
                record.get('timestamp', ''),
                display_task
            ))
        
        # 绑定双击事件
        tree.bind('<Double-1>', lambda e: self.use_task_from_history(history_window, tree))
        
        # 绑定ESC键关闭窗口
        history_window.bind('<Escape>', lambda e: history_window.destroy())
        
        # 说明文字和按钮框架
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 说明文字
        ttk.Label(bottom_frame, text="提示：Ctrl+点击可多选 | 双击可快速使用 | ESC关闭窗口", 
                 font=('Microsoft YaHei', 8), foreground='gray').pack(pady=(0, 10))
        
        # 操作按钮放在底部中间
        buttons_container = ttk.Frame(bottom_frame)
        buttons_container.pack()
        
        # 使用选中任务按钮
        ttk.Button(buttons_container, text="📝 使用选中任务", 
                  command=lambda: self.use_task_from_history(history_window, tree)).pack(side=tk.LEFT, padx=10)
        
        # 删除选中按钮
        ttk.Button(buttons_container, text="🗑️ 删除选中", 
                  command=lambda: self.delete_selected_tasks(history_window, tree)).pack(side=tk.LEFT, padx=10)
        
        # 清空全部按钮
        ttk.Button(buttons_container, text="🆕 清空全部", 
                  command=lambda: self.clear_all_tasks(history_window, tree)).pack(side=tk.LEFT, padx=10)
        
        # 删除重复项按钮（保留第一次出现的记录）
        ttk.Button(buttons_container, text="⚡ 删除重复项", 
              command=lambda: self.remove_duplicate_tasks(history_window, tree)).pack(side=tk.LEFT, padx=10)
    
    def use_task_from_history(self, history_window, tree):
        """从历史记录中使用任务"""
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("提示", "请先选择一个任务记录")
            return
        
        item = selected_item[0]
        values = tree.item(item, 'values')
        
        # 根据时间和任务内容查找对应的完整任务记录
        timestamp = values[0]
        task_display = values[1]
        for record in self.task_history:
            if record.get('timestamp') == timestamp and record.get('task', '').startswith(task_display.replace('...', '')):
                # 将完整的任务内容填充到任务输入框
                full_task = record.get('task', '')
                self.task_text.delete("1.0", tk.END)
                self.task_text.insert("1.0", full_task)
                self.task.set(full_task)
                
                # 关闭历史记录窗口
                history_window.destroy()
                
                self.status_var.set("✅ 已加载历史任务")
                break
    
    def delete_selected_tasks(self, history_window, tree):
        """删除选中的任务历史记录（支持单条和多条）"""
        selected_items = tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要删除的记录")
            return
        
        count = len(selected_items)
        if count == 1:
            message = "确定要删除选中的1条任务记录吗？"
        else:
            message = f"确定要删除选中的 {count} 条任务记录吗？"
        
        if messagebox.askyesno("确认", message):
            # 获取要删除的任务
            tasks_to_delete = []
            for item in selected_items:
                values = tree.item(item, 'values')
                timestamp = values[0]
                task_display = values[1]
                tasks_to_delete.append((timestamp, task_display))
            
            # 从历史记录中删除
            for timestamp, task_display in tasks_to_delete:
                self.task_history = [r for r in self.task_history 
                                   if not (r.get('timestamp') == timestamp and 
                                          r.get('task', '').startswith(task_display.replace('...', '')))]
            self.save_task_history()
            
            # 刷新树形视图
            for item in selected_items:
                tree.delete(item)
            
            self.status_var.set(f"✅ 已删除 {count} 条任务记录")

    def remove_duplicate_tasks(self, history_window, tree):
        """移除任务历史中的重复项，保留每个任务的第一条记录。"""
        if not self.task_history:
            messagebox.showinfo("提示", "历史记录为空，无重复项可删")
            return

        # 使用规范化文本作为判重依据
        seen = set()
        new_history = []
        removed = 0
        for record in self.task_history:
            task_text = record.get('task', '')
            norm = ' '.join(task_text.split()) if isinstance(task_text, str) else str(task_text)
            if norm in seen:
                removed += 1
                continue
            seen.add(norm)
            # 先加入保留列表
            new_history.append(record)

        if removed == 0:
            messagebox.showinfo("提示", "未发现重复记录")
            return

        # 重新分配ID并保存
        for idx, rec in enumerate(new_history, start=1):
            rec['id'] = idx

        self.task_history = new_history
        self.save_task_history()

        # 刷新树视图
        for item in tree.get_children():
            tree.delete(item)
        for record in self.task_history:
            task_content = record.get('task', '')
            display_task = task_content if len(task_content) <= 100 else task_content[:97] + '...'
            tree.insert('', 'end', values=(record.get('timestamp', ''), display_task))

        self.status_var.set(f"✅ 已删除 {removed} 条重复记录")
    

    def clear_all_tasks(self, history_window, tree):
        """清空所有任务历史记录"""
        if not self.task_history:
            messagebox.showinfo("提示", "历史记录已经是空的")
            return
        
        if messagebox.askyesno("确认", f"确定要清空所有 {len(self.task_history)} 条任务历史记录吗？此操作不可恢复！"):
            self.task_history = []
            self.save_task_history()
            
            # 清空树形视图
            for item in tree.get_children():
                tree.delete(item)
            
            self.status_var.set("✅ 已清空所有历史记录")
    
    def _handle_scrcpy_exit(self, returncode):
        """处理 scrcpy 退出的情况"""
        if returncode != 0:
            self._append_output(f"❌ scrcpy启动失败，退出代码: {returncode}\n")
            self._append_output("💡 请检查:\n")
            self._append_output("   1. scrcpy是否已安装并加入PATH\n")
            self._append_output("   2. 设备是否已授权\n")
            self._append_output("   3. 设备屏幕是否已解锁\n")
            self.status_var.set("❌ 远程桌面启动失败")
        else:
            self._append_output("✅ scrcpy已正常退出\n")
            self.status_var.set("✅ 远程控制已结束")
            
        # 远程桌面正常退出，不做任何额外操作，主程序继续运行
        self._append_output("✅ 远程桌面已正常关闭，主程序继续运行\n")
    
    def _exit_application(self):
        """安全退出应用程序"""
        try:
            # 停止所有正在运行的进程
            if hasattr(self, 'process') and self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
            
            # 清理资源
            self._append_output("🧹 正在清理资源...\n")
            self.root.update()
            
            # 退出应用程序
            self._append_output("👋 程序已退出\n")
            self.root.quit()
            self.root.destroy()
            
            # 强制退出进程
            import sys
            import os
            os._exit(0)
            
        except Exception as e:
            # 如果正常退出失败，强制退出
            import os
            os._exit(0)
    
    def open_remote_desktop(self):
        """打开远程桌面控制对话框"""
        # 检查是否有设备连接
        if not self.connected_devices:
            messagebox.showwarning("设备检查", "未检测到连接的设备，请先连接设备")
            return
        
        # 获取当前设备类型
        device_type = self.device_type.get()
        device_type_en = "hdc" if device_type == "鸿蒙" else "adb"
        device_display = "HDC" if device_type_en == "hdc" else "ADB"
        
        # 检查是否有可用设备
        available_devices = [d for d in self.connected_devices if d['status'] == 'device']
        if not available_devices:
            messagebox.showwarning("设备检查", f"没有可用的{device_display}设备")
            return
        
        # 使用优化的居中窗口创建方法
        dialog = self.create_centered_toplevel(self.root, f"🖥️ {device_display}远程桌面控制", 550, 450)
        
        # 保存对话框引用
        self.remote_desktop_window = dialog
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1)  # 让控制区域可扩展
        
        # 标题
        title_label = ttk.Label(main_frame, text=f"🖥️ {device_display}远程桌面控制", 
                               font=('Microsoft YaHei', 12, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 15), sticky=tk.W+tk.E)
        
        # 设备选择区域
        device_frame = ttk.LabelFrame(main_frame, text="📱 选择设备", padding="10")
        device_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        device_frame.columnconfigure(0, weight=1)
        
        # 填充设备列表，独立选择，默认选择第一个设备
        device_options = []
        device_ids = []
        
        for device in available_devices:
            if device['status'] == 'device':
                display_name = device['id']
                device_ids.append(device['id'])
                if device['info'] and 'model' in device['info']:
                    display_name += f" ({device['info']['model']})"
                device_options.append(display_name)
        
        # 设备选择下拉框 - 完全模仿主界面的方式
        device_var = tk.StringVar()
        device_combo = ttk.Combobox(device_frame, textvariable=device_var, 
                                   state="readonly", font=('Microsoft YaHei', 10))
        device_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        device_combo.columnconfigure(0, weight=1)
        
        # 设置设备选项
        device_combo['values'] = device_options
        
        # 设置默认选择第一个设备
        if device_options:
            device_var.set(device_options[0])  # 设置变量为显示名称
            device_combo.current(0)  # 设置选中索引
        
        # 控制按钮区域
        control_frame = ttk.LabelFrame(main_frame, text="🎮 远程控制", padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        control_frame.columnconfigure(0, weight=1)
        
        # 说明文字
        info_label = ttk.Label(control_frame, 
                              text="通过scrcpy工具实现设备桌面镜像和控制\n" + 
                                   "• 实时查看设备桌面\n" +
                                   "• 鼠标控制设备操作\n" +
                                   "• 键盘输入文字\n" +
                                   "• 文件拖拽传输（部分设备支持）\n" +
                                   "• 关闭远程桌面不会影响主程序运行",
                              font=('Microsoft YaHei', 9), foreground='#666666')
        info_label.grid(row=0, column=0, columnspan=3, pady=(0, 15), sticky=tk.W)
        
        # 控制选项
        options_frame = ttk.Frame(control_frame)
        options_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 分辨率选项
        ttk.Label(options_frame, text="分辨率限制:", font=('Microsoft YaHei', 9)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        resolution_var = tk.StringVar(value="1024")
        resolution_combo = ttk.Combobox(options_frame, textvariable=resolution_var, 
                                      width=10, state="readonly", font=('Microsoft YaHei', 9))
        resolution_combo['values'] = ('720', '1024', '1280', '1920', '无限制')
        resolution_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # 位深选项
        ttk.Label(options_frame, text="位深:", font=('Microsoft YaHei', 9)).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        bit_depth_var = tk.StringVar(value="32")
        bit_depth_combo = ttk.Combobox(options_frame, textvariable=bit_depth_var, 
                                      width=8, state="readonly", font=('Microsoft YaHei', 9))
        bit_depth_combo['values'] = ('8', '16', '32')
        bit_depth_combo.grid(row=0, column=3, sticky=tk.W)
        
        # 控制按钮
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        def start_remote_control():
            """启动远程控制"""
            selected_index = device_combo.current()
            if selected_index < 0:
                messagebox.showwarning("设备选择", "请先选择一个设备")
                return
            
            # 使用过滤后的设备ID列表，确保索引匹配
            device_id = device_ids[selected_index]
            
            # 构建scrcpy命令
            scrcpy_cmd = ['scrcpy']
            
            # 添加设备ID
            if ':' in device_id:  # 远程设备
                scrcpy_cmd.extend(['-s', device_id])
            else:  # USB设备，对于多个设备需要指定ID
                if len(available_devices) > 1:
                    scrcpy_cmd.extend(['-s', device_id])
            
            # 添加分辨率限制
            resolution = resolution_var.get()
            if resolution != '无限制':
                scrcpy_cmd.extend(['-m', resolution])
            
            # 添加位深
            bit_depth = bit_depth_var.get()
            scrcpy_cmd.extend(['-b', bit_depth + 'M'])
            
            # 添加其他有用选项
            scrcpy_cmd.extend([
                '--no-audio',        # 禁用音频转发
                '--stay-awake',      # 保持设备唤醒                
                '--window-title', f'{device_display}远程控制 - {device_id}'  # 设置窗口标题
            ])
            
            self._append_output(f"🖥️ 正在启动{device_display}远程控制...\n")
            self._append_output(f"📱 目标设备: {device_id}\n")
            self._append_output(f"🔧 执行命令: {' '.join(scrcpy_cmd)}\n")
            
            try:
                # 在新进程中启动scrcpy（隐藏CMD窗口）
                import subprocess
                import os
                import threading
                import time
                
                # 在Windows上隐藏控制台窗口
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                else:
                    creationflags = 0
                
                process = subprocess.Popen(scrcpy_cmd, creationflags=creationflags)
                
                # 给scrcpy一些时间启动，然后监控其状态
                def monitor_scrcpy():
                    import time
                    time.sleep(3)  # 等待3秒让scrcpy完全启动
                    
                    # 持续监控 scrcpy 进程状态
                    while True:
                        if process.poll() is not None:
                            # scrcpy已经退出
                            returncode = process.returncode
                            
                            # 在主线程中更新UI，不再需要传递自动退出选项
                            self.root.after(0, lambda rc=returncode: self._handle_scrcpy_exit(rc))
                            break
                        
                        time.sleep(1)  # 每秒检查一次进程状态
                
                threading.Thread(target=monitor_scrcpy, daemon=True).start()
                
                self._append_output("✅ scrcpy远程控制已启动\n")
                self._append_output("💡 关闭远程桌面窗口不会影响主程序运行\n")
                self.status_var.set(f"🖥️ {device_display}远程控制运行中")
                
                # 关闭对话框
                dialog.destroy()
                
            except FileNotFoundError:
                messagebox.showerror("错误", 
                                   "未找到scrcpy程序！\n\n" +
                                   "请按以下步骤安装scrcpy：\n" +
                                   "1. 访问 https://github.com/Genymobile/scrcpy\n" +
                                   "2. 下载对应平台的scrcpy程序\n" +
                                   "3. 将scrcpy.exe (Windows) 或 scrcpy (Linux/Mac) 加入系统PATH\n" +
                                   "4. 或将scrcpy程序复制到本程序目录")
            except Exception as e:
                messagebox.showerror("错误", f"启动远程控制失败: {str(e)}")
                self._append_output(f"❌ 启动远程控制失败: {str(e)}\n")
        
        def install_scrcpy():
            """显示scrcpy安装说明"""
            # 使用优化的居中窗口创建方法
            install_window = self.create_centered_toplevel(dialog, "📦 scrcpy安装说明", 500, 400)
            
            main_frame = ttk.Frame(install_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            title_label = ttk.Label(main_frame, text="📦 scrcpy安装说明", 
                                   font=('Microsoft YaHei', 12, 'bold'))
            title_label.pack(pady=(0, 15))
            
            # 创建滚动文本框
            from tkinter import scrolledtext
            install_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, 
                                                   font=('Microsoft YaHei', 9), 
                                                   bg='#f8f8f8')
            install_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            
            install_info = """
scrcpy (Screen Copy) 是一款开源的Android设备屏幕镜像工具

🌟 主要功能：
• 实时显示Android设备屏幕
• 鼠标控制设备操作
• 键盘输入文字和快捷键
• 文件拖拽传输
• 录屏功能
• 多设备支持

📥 安装方法：

方法一：下载预编译版本（推荐）
1. 访问官方发布页面：https://github.com/Genymobile/scrcpy/releases
2. 下载最新版本的 scrcpy-win64.zip (Windows)
3. 解压到任意目录
4. 将 scrcpy.exe 所在目录添加到系统PATH环境变量

方法二：包管理器安装
Windows (使用 Scoop):
    scoop install scrcpy

Linux (Ubuntu/Debian):
    sudo apt install scrcpy

macOS (使用 Homebrew):
    brew install scrcpy

方法三：源码编译
1. 安装依赖：
   Windows: 需要MSYS2环境
   Linux: sudo apt install build-essential pkg-config meson ninja-build
   macOS: brew install meson ninja

2. 克隆源码：
   git clone https://github.com/Genymobile/scrcpy
   cd scrcpy

3. 编译安装：
   meson build
   cd build
   ninja
   ninja install

🔧 验证安装：
打开命令行，输入：scrcpy --version
如果显示版本信息，说明安装成功

📱 使用要求：
• Android 5.0+ (API 21+)
• 开启USB调试
• 设备已授权连接

💡 使用提示：
• 首次连接需要在设备上授权
• 部分手机需要在开发者选项中开启"USB安装"
• 如遇性能问题，可降低分辨率或位深
            """
            
            install_text.insert("1.0", install_info)
            install_text.config(state=tk.DISABLED)
            
            # 关闭按钮
            ttk.Button(main_frame, text="关闭", command=install_window.destroy).pack()
        
        def refresh_device_list():
            """刷新设备列表并重新选择主界面设备"""
            self.refresh_devices()
            
            # 重新获取可用设备
            new_available_devices = [d for d in self.connected_devices if d['status'] == 'device']
            
            # 重新填充设备列表
            new_device_options = []
            new_selected_device_id = self.selected_device_id.get()
            new_default_index = 0
            new_main_device_id = extract_device_id(new_selected_device_id)
            
            new_found_main_device = False
            for i, device in enumerate(new_available_devices):
                display_name = device['id']
                if device['info'] and 'model' in device['info']:
                    display_name += f" ({device['info']['model']})"
                new_device_options.append(display_name)
                
                if new_main_device_id and device['id'] == new_main_device_id:
                    new_default_index = i
                    new_found_main_device = True
                elif not new_found_main_device and new_main_device_id and device['id'].startswith(new_main_device_id):
                    new_default_index = i
                elif not new_found_main_device and i == 0:
                    new_default_index = 0
            
            # 更新下拉框
            device_combo['values'] = new_device_options
            if new_device_options:
                device_combo.current(new_default_index)
                if new_found_main_device:
                    self._append_output("🔄 已刷新并同步主界面设备\n")
                else:
                    self._append_output("🔄 设备列表已刷新\n")
            else:
                self._append_output("⚠️ 未找到可用设备\n")

        # 按钮布局
        ttk.Button(buttons_frame, text="🚀 启动远程控制", 
                  command=start_remote_control, 
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        
        ttk.Button(buttons_frame, text="🔄 刷新设备", 
                  command=refresh_device_list).grid(row=0, column=1, padx=5)
        
        ttk.Button(buttons_frame, text="📦 安装说明", 
                  command=install_scrcpy).grid(row=0, column=2, padx=5)
        
        ttk.Button(buttons_frame, text="❌ 关闭", 
                  command=dialog.destroy, 
                  style='Danger.TButton').grid(row=0, column=3, padx=5)
        

        
        # 绑定窗口关闭事件，清除引用
        def on_dialog_close():
            self.remote_desktop_window = None
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)


def main():
    root = tk.Tk()
    app = PhoneAgentGUI(root)
    
    # 设置窗口关闭事件处理
    def on_closing():
        """窗口关闭时的处理"""
        if app.running:
            # 如果正在运行任务，询问用户
            import tkinter.messagebox as msgbox
            result = msgbox.askyesno("确认退出", 
                                   "程序正在运行任务，确定要退出吗？\n\n" +
                                   "建议先停止当前任务再退出程序。")
            if result:
                # 用户确认退出，强制停止任务并退出
                app.stop_agent()
                app._exit_application()
        else:
            # 直接退出
            app._exit_application()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()