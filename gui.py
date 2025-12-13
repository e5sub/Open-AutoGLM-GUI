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
import json
from datetime import datetime
import re


class PhoneAgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("鸡哥手机助手 V0.2 - AI手机自动化工具")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)
        
        # 设置样式
        self.setup_styles()
        
        # 变量存储
        self.base_url = tk.StringVar(value="https://open.bigmodel.cn/api/paas/v4")
        self.model = tk.StringVar(value="autoglm-phone")
        self.apikey = tk.StringVar(value="your-bigmodel-api-key")
        self.task = tk.StringVar(value="输入你想要执行的任务，例如：打开美团搜索附近的火锅店")
        
        self.process = None
        self.running = False
        self.config_file = "gui_config.json"
        
        # ADB相关变量
        self.connected_devices = []
        self.selected_device_id = tk.StringVar(value="")

        # 先创建界面组件，再加载配置（避免在组件未创建时访问属性）
        self.create_widgets()
        
        # 加载配置
        self.load_config()
        
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        
        # 设置主题
        style.theme_use('clam')
        
        # 配置颜色
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'), foreground='#2E86AB')
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#333333')
        style.configure('Success.TButton', font=('Arial', 10, 'bold'))
        style.configure('Danger.TButton', font=('Arial', 10, 'bold'))
        
        # 配置框架
        style.configure('Card.TFrame', relief='raised', borderwidth=1)
        style.configure('Output.TFrame', relief='sunken', borderwidth=2)
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=3, pady=(0, 25))
        
        title_label = ttk.Label(title_frame, text="🤖 鸡哥手机助手", style='Title.TLabel')
        title_label.pack()
        
        subtitle_label = ttk.Label(title_frame, text="AI驱动的手机自动化工具", font=('Microsoft YaHei', 10))
        subtitle_label.pack()
        
        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ 配置参数", style='Card.TFrame', padding="8")
        config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))
        config_frame.columnconfigure(1, weight=1)
        
        # Base URL
        ttk.Label(config_frame, text="🌐 Base URL:", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=3)
        url_entry = ttk.Entry(config_frame, textvariable=self.base_url, width=50, font=('Arial', 9))
        url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
        
        # Model
        ttk.Label(config_frame, text="🧠 Model:", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=3)
        model_entry = ttk.Entry(config_frame, textvariable=self.model, width=50, font=('Arial', 9))
        model_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
        
        # API Key
        ttk.Label(config_frame, text="🔑 API Key:", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=3)
        apikey_frame = ttk.Frame(config_frame)
        apikey_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
        apikey_frame.columnconfigure(0, weight=1)
        
        self.apikey_entry = ttk.Entry(apikey_frame, textvariable=self.apikey, width=40, show="*", font=('Arial', 9))
        self.apikey_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.show_apikey_btn = ttk.Button(apikey_frame, text="👁️", width=2, command=self.toggle_apikey_visibility)
        self.show_apikey_btn.grid(row=0, column=1, padx=(3, 0))
        
        # Task
        ttk.Label(config_frame, text="📝 Task:", font=('Arial', 9, 'bold')).grid(row=3, column=0, sticky=(tk.NW, tk.W), pady=3)
        self.task_text = tk.Text(config_frame, width=50, height=2, font=('Arial', 9), wrap=tk.WORD)
        self.task_text.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=3)
        
        # 设置初始任务文本
        self.task_text.insert("1.0", self.task.get())
        self.task_text.bind("<KeyRelease>", lambda e: self.task.set(self.task_text.get("1.0", tk.END).strip()))
        
        # ADB设备区域
        adb_frame = ttk.LabelFrame(main_frame, text="📱 ADB设备管理", style='Card.TFrame', padding="8")
        adb_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(8, 8))
        adb_frame.columnconfigure(1, weight=1)
        
        # ADB控制按钮
        adb_control_frame = ttk.Frame(adb_frame)
        adb_control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(adb_control_frame, text="🔄 刷新设备", command=self.refresh_devices).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(adb_control_frame, text="🔗 连接ADB", command=self.connect_adb_device).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(adb_control_frame, text="📋 设备详情", command=self.show_device_details).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(adb_control_frame, text="📲 安装ADB键盘", command=self.install_adb_keyboard).pack(side=tk.LEFT, padx=(0, 8))
        
        # 设备选择
        ttk.Label(adb_frame, text="📱 选择设备:", font=('Microsoft YaHei', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        device_select_frame = ttk.Frame(adb_frame)
        device_select_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(15, 0))
        device_select_frame.columnconfigure(0, weight=1)
        
        self.device_combo = ttk.Combobox(device_select_frame, textvariable=self.selected_device_id, 
                                      state="readonly", font=('Microsoft YaHei', 9))
        self.device_combo.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.device_status_label = ttk.Label(device_select_frame, text="未检测到设备", 
                                        font=('Microsoft YaHei', 9), foreground='red')
        self.device_status_label.grid(row=0, column=1, padx=(10, 0))
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=5)
        
        # 主要操作按钮
        main_buttons = ttk.Frame(button_frame)
        main_buttons.pack(side=tk.LEFT, padx=(0, 20))
        
        self.run_button = ttk.Button(main_buttons, text="🚀 运行", command=self.run_agent, style='Success.TButton')
        self.run_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(main_buttons, text="⏹️ 停止", command=self.stop_agent, state=tk.DISABLED, style='Danger.TButton')
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # 辅助功能按钮
        aux_buttons = ttk.Frame(button_frame)
        aux_buttons.pack(side=tk.LEFT)
        
        ttk.Button(aux_buttons, text="🗑️ 清空", command=self.clear_output).grid(row=0, column=0, padx=5)
        ttk.Button(aux_buttons, text="💾 保存配置", command=self.save_config).grid(row=0, column=1, padx=5)
        ttk.Button(aux_buttons, text="📁 加载配置", command=self.load_config_dialog).grid(row=0, column=2, padx=5)
        
        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text="📋 输出控制台", style='Output.TFrame', padding="5")
        output_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # 创建带行号的文本框
        text_frame = ttk.Frame(output_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(1, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # 行号显示
        self.line_numbers = tk.Text(text_frame, width=4, padx=3, takefocus=0, 
                                   border=0, state='disabled', wrap='none',
                                   background='#f0f0f0', foreground='#666666')
        self.line_numbers.grid(row=0, column=0, sticky=(tk.N, tk.S))
        
        # 主输出文本框
        self.output_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=80, height=20,
                                                   font=('Consolas', 9), bg='#1e1e1e', fg='#ffffff',
                                                   insertbackground='#ffffff')
        self.output_text.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        status_frame.columnconfigure(1, weight=1)
        
        self.status_var = tk.StringVar(value="✅ 就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # 时间显示
        self.time_var = tk.StringVar(value="")
        time_label = ttk.Label(status_frame, textvariable=self.time_var, relief=tk.SUNKEN, anchor=tk.E, width=20)
        time_label.grid(row=0, column=1, sticky=(tk.E))
        
        # 更新时间
        self.update_time()
        
        # 初始刷新设备列表（在所有组件创建完成后）
        self.refresh_devices()
        
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%H:%M:%S")
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
            
        # 提前获取选中的设备（避免在打包环境中使用未定义的变量）
        selected_device = self.selected_device_id.get()

        # 无论在开发环境还是打包环境中，都使用直接运行方式
        self._run_agent_direct(base_url, model, apikey, task, selected_device)
        
    def _run_adb_silent(self, cmd, timeout=10):
        """静默执行ADB命令，避免弹窗"""
        import os
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=creation_flags)

    def _run_agent_direct(self, base_url, model, apikey, task, selected_device):
        """直接运行代理（打包环境）"""
        try:
            # 导入必要模块
            from phone_agent.agent import PhoneAgent, AgentConfig
            from phone_agent.model import ModelConfig
            from phone_agent.adb import ADBConnection, list_devices
            
            # 解析设备ID
            device_id = None
            if selected_device:
                device_id = selected_device.split(' ')[0]
            
            # 使用线程安全的输出函数
            def safe_output(text):
                # 为每行添加时间戳和格式化
                if '\n' in text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip():
                            self.root.after(0, self._append_output, line + '\n')
                else:
                    if text.strip():
                        self.root.after(0, self._append_output, text)
            
            # 在打包环境中设置subprocess创建标志，避免弹窗
            import subprocess
            import os
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
                api_key=apikey
            )
            
            # 获取打包环境中的ADB路径
            import sys
            if getattr(sys, 'frozen', False):
                # 在打包环境中，ADB文件在exe所在目录
                import os
                exe_dir = os.path.dirname(sys.executable)
                adb_path = os.path.join(exe_dir, 'adb.exe')
                if not os.path.exists(adb_path):
                    # 尝试在当前目录查找
                    import tempfile
                    adb_path = 'adb.exe'
            else:
                adb_path = 'adb.exe'
            
            # 创建代理配置
            agent_config = AgentConfig(
                device_id=device_id,
                verbose=True,
                max_steps=50  # 限制步数，避免无限循环
            )
            
            # 创建并运行PhoneAgent
            safe_output("🚀 开始执行任务...\n")
            agent = PhoneAgent(
                model_config=model_config,
                agent_config=agent_config
            )
            
            # 设置ADB路径（如果需要）
            safe_output(f"🔧 ADB路径: {adb_path}\n")
            
            # 在单独线程中执行任务，避免阻塞GUI
            def execute_task():
                try:
                    safe_output(f"📋 开始执行: {task}\n")
                    
                    # 重定向print输出到GUI
                    import sys
                    original_stdout = sys.stdout
                    
                    class GUIOutput:
                        def __init__(self, output_func, stop_check_func):
                            self.output_func = output_func
                            self.stop_check_func = stop_check_func
                            self.buffer = ""  # 添加缓冲区
                            self.in_progress = False  # 标记是否正在处理同一行
                            
                        def write(self, text):
                            # 检查是否需要停止
                            if not self.stop_check_func():
                                return
                            
                            # 直接累积到缓冲区
                            self.buffer += text
                            
                            # 只有当遇到换行符或缓冲区很大时才处理
                            if '\n' in self.buffer or len(self.buffer) > 200:
                                # 处理缓冲区中的完整行
                                while '\n' in self.buffer:
                                    line_end = self.buffer.find('\n')
                                    line = self.buffer[:line_end]
                                    self.buffer = self.buffer[line_end + 1:]  # 跳过换行符
                                    
                                    # 如果行不为空，输出
                                    if line.strip():
                                        self.output_func(line)
                                        
                        def flush(self):
                            # 输出剩余的缓冲内容
                            if self.buffer.strip():
                                self.output_func(self.buffer)
                                self.buffer = ""
                    
                    # 检查是否继续运行
                    def is_running():
                        return self.running
                    
                    # 设置输出重定向
                    sys.stdout = GUIOutput(safe_output, is_running)
                    
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
        
        # 避免对已经是完整行的文本重复处理
        # 如果文本已经包含时间戳格式，直接插入
        if text.startswith('[') and '] ' in text and (':' in text.split('] ')[0].split('[')[1] if ']' in text else False):
            formatted_text = text
        else:
            # 添加时间戳
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 分割文本为行，处理多行文本
            lines = text.split('\n')
            formatted_lines = []
            
            for line in lines:
                if not line:  # 空行
                    formatted_lines.append("")
                    continue
                    
                # 处理不同类型的输出
                if any(keyword in line.lower() for keyword in ['error', 'failed', '错误', '失败']):
                    formatted_line = f"[{timestamp}] ❌ {line}"
                elif any(keyword in line.lower() for keyword in ['warning', 'warn', '警告']):
                    formatted_line = f"[{timestamp}] ⚠️ {line}"
                elif any(keyword in line.lower() for keyword in ['success', 'ok', '成功', '完成']):
                    formatted_line = f"[{timestamp}] ✅ {line}"
                elif any(keyword in line.lower() for keyword in ['checking', '检查']):
                    formatted_line = f"[{timestamp}] 🔍 {line}"
                else:
                    formatted_line = f"[{timestamp}] {line}"
                    
                formatted_lines.append(formatted_line)
            
            # 重新组合文本
            formatted_text = '\n'.join(formatted_lines)
            
            # 如果原始文本以换行符结尾，确保格式化文本也如此
            if text.endswith('\n') and not formatted_text.endswith('\n'):
                formatted_text += '\n'
        
        # 插入文本
        self.output_text.insert(tk.END, formatted_text)
        self.output_text.see(tk.END)
        
        # 更新行号
        self.update_line_numbers()
        
    def _insert_direct_text(self, text):
        """直接插入文本，不添加时间戳（用于已经格式化的输出）"""
        if text.strip():  # 只插入非空内容
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
            self.update_line_numbers()
        
    def update_line_numbers(self):
        """更新行号显示"""
        lines = self.output_text.get("1.0", tk.END).count('\n')
        line_numbers = "\n".join(str(i) for i in range(1, lines + 1))
        self.line_numbers.config(state='normal')
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", line_numbers)
        self.line_numbers.config(state='disabled')
        
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
            config = {
                'base_url': self.base_url.get(),
                'model': self.model.get(),
                'apikey': self.apikey.get(),
                'task': self.task_text.get("1.0", tk.END).strip(),
                'selected_device': self.selected_device_id.get()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("成功", "配置已保存到 gui_config.json")
            self.status_var.set("✅ 配置已保存")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
            self.status_var.set("❌ 保存配置失败")
            
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
                
                # 恢复选中的设备
                selected_device = config.get('selected_device', '')
                if selected_device and hasattr(self, 'selected_device_id'):
                    self.selected_device_id.set(selected_device)
                
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
                
                # 恢复选中的设备
                selected_device = config.get('selected_device', '')
                if selected_device:
                    self.selected_device_id.set(selected_device)
                
                messagebox.showinfo("成功", "配置已成功加载")
                self.status_var.set("✅ 从文件加载配置")
                
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {str(e)}")
            self.status_var.set("❌ 加载配置失败")
        
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
        self.output_text.delete("1.0", tk.END)
        self.update_line_numbers()
        self.status_var.set("✅ 输出已清空")
        
    # ADB相关方法
    def refresh_devices(self):
        """刷新ADB设备列表"""
        try:
            self._append_output("🔍 正在扫描ADB设备...\n")
            
            # 获取设备列表
            result = self._run_adb_silent(['adb', 'devices'])
            
            if result.returncode == 0:
                self.connected_devices = self._parse_device_list(result.stdout)
                self._update_device_display()
            else:
                self._append_output("❌ ADB命令执行失败\n")
                self.device_status_label.config(text="ADB错误", foreground='red')
                
        except subprocess.TimeoutExpired:
            self._append_output("❌ ADB命令超时\n")
            self.device_status_label.config(text="ADB超时", foreground='red')
        except FileNotFoundError:
            self._append_output("❌ 未找到ADB，请检查Android SDK是否安装\n")
            self.device_status_label.config(text="ADB未安装", foreground='red')
        except Exception as e:
            self._append_output(f"❌ 扫描设备失败: {str(e)}\n")
            self.device_status_label.config(text="扫描失败", foreground='red')
            
    def _parse_device_list(self, adb_output):
        """解析ADB设备列表输出"""
        devices = []
        lines = adb_output.strip().split('\n')
        
        for line in lines[1:]:  # 跳过标题行
            if line.strip() and '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0].strip()
                    status = parts[1].strip()
                    devices.append({
                        'id': device_id,
                        'status': status,
                        'info': self._get_device_info(device_id) if status == 'device' else None
                    })
                    
        return devices
        
    def _get_device_info(self, device_id):
        """获取设备详细信息"""
        try:
            info = {}
            
            # 获取设备型号
            model_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'], timeout=5)
            if model_result.returncode == 0:
                info['model'] = model_result.stdout.strip()
                
            # 获取Android版本
            version_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'], timeout=5)
            if version_result.returncode == 0:
                info['android_version'] = version_result.stdout.strip()
                
            # 获取设备制造商
            manufacturer_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.manufacturer'], timeout=5)
            if manufacturer_result.returncode == 0:
                info['manufacturer'] = manufacturer_result.stdout.strip()
                
            # 获取IP地址
            ip_result = self._run_adb_silent(['adb', '-s', device_id, 'shell', 'ip', 'addr', 'show', 'wlan0'], timeout=5)
            if ip_result.returncode == 0:
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
            for device in self.connected_devices:
                if device['status'] == 'device':
                    display_name = device['id']
                    if device['info'] and 'model' in device['info']:
                        display_name += f" ({device['info']['model']})"
                    device_options.append(display_name)
                    
            self.device_combo['values'] = device_options
            
            if device_options:
                self.device_combo.current(0)
                self.device_status_label.config(text=f"已连接 {len(device_options)} 台设备", foreground='green')
            else:
                self.device_status_label.config(text="无可用设备", foreground='orange')
        else:
            self.device_combo['values'] = []
            self.device_combo.set("")
            self.device_status_label.config(text="未检测到设备", foreground='red')
            
        self._append_output(f"📱 扫描完成，发现 {len(self.connected_devices)} 台设备\n")

    def connect_adb_device(self):
        """智能ADB设备连接功能"""
        self._append_output("🔍 正在检查设备连接状态...\n")
        
        try:
            # 刷新设备列表
            self.refresh_devices()
            
            # 分析设备状态
            usb_devices = [d for d in self.connected_devices if d['status'] == 'device' and ':' not in d['id']]
            remote_devices = [d for d in self.connected_devices if d['status'] == 'device' and ':' in d['id']]
            offline_devices = [d for d in self.connected_devices if d['status'] == 'offline']
            
            # 创建智能连接对话框
            dialog = tk.Toplevel(self.root)
            dialog.title("智能ADB连接")
            dialog.geometry("500x400")
            dialog.resizable(False, False)
            
            # 设置对话框始终在最前
            dialog.lift()
            dialog.attributes('-topmost', True)
            dialog.after(1000, lambda: dialog.attributes('-topmost', False))
            
            # 主框架
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 标题
            title_label = ttk.Label(main_frame, text="📱 ADB设备连接状态", 
                                   font=('Arial', 12, 'bold'))
            title_label.pack(pady=(0, 15))
            
            # 设备状态显示区域
            status_frame = ttk.LabelFrame(main_frame, text="当前设备状态", padding="10")
            status_frame.pack(fill=tk.X, pady=(0, 15))
            
            # USB设备状态
            if usb_devices:
                usb_text = f"✅ USB设备: {len(usb_devices)} 台\n"
                for device in usb_devices:
                    usb_text += f"   • {device['id']}\n"
            else:
                usb_text = "❌ 未检测到USB设备"
            
            usb_label = ttk.Label(status_frame, text=usb_text, font=('Consolas', 9))
            usb_label.pack(anchor=tk.W, pady=2)
            
            # 远程设备状态
            if remote_devices:
                remote_text = f"✅ 远程设备: {len(remote_devices)} 台\n"
                for device in remote_devices:
                    remote_text += f"   • {device['id']}\n"
            else:
                remote_text = "⚪ 未连接远程设备"
                
            remote_label = ttk.Label(status_frame, text=remote_text, font=('Consolas', 9))
            remote_label.pack(anchor=tk.W, pady=2)
            
            # 离线设备状态
            if offline_devices:
                offline_text = f"⚠️ 离线设备: {len(offline_devices)} 台\n"
                for device in offline_devices:
                    offline_text += f"   • {device['id']}\n"
                    
                offline_label = ttk.Label(status_frame, text=offline_text, 
                                         font=('Consolas', 9), foreground='orange')
                offline_label.pack(anchor=tk.W, pady=2)
            
            # 操作按钮区域
            button_frame = ttk.LabelFrame(main_frame, text="连接选项", padding="10")
            button_frame.pack(fill=tk.X, pady=(0, 15))
            
            def do_connect_usb():
                """USB连接引导"""
                if usb_devices:
                    self._append_output("💡 USB连接提示：\n")
                    self._append_output("   1. 确保USB调试已开启\n")
                    self._append_output("   2. 检查USB连接线\n")
                    self._append_output("   3. 重新授权设备\n")
                else:
                    self._append_output("📱 请使用USB线连接Android设备并开启USB调试\n")
                dialog.destroy()
                
            def do_connect_remote():
                """远程连接"""
                dialog.destroy()
                self.connect_remote_device()
                
            def do_refresh_devices():
                """刷新设备"""
                self._append_output("🔄 正在重新扫描设备...\n")
                self.refresh_devices()
                dialog.after(1000, lambda: self.connect_adb_device())
                dialog.destroy()
            
            def do_restart_adb():
                """重启ADB服务"""
                try:
                    self._append_output("🔄 正在重启ADB服务...\n")
                    subprocess.run(['adb', 'kill-server'], capture_output=True, timeout=5)
                    subprocess.run(['adb', 'start-server'], capture_output=True, timeout=5)
                    self._append_output("✅ ADB服务已重启\n")
                    self.refresh_devices()
                    dialog.after(1000, lambda: self.connect_adb_device())
                    dialog.destroy()
                except Exception as e:
                    self._append_output(f"❌ 重启ADB失败: {str(e)}\n")
            
            # 提供智能按钮建议
            buttons_row1 = ttk.Frame(button_frame)
            buttons_row1.pack(fill=tk.X, pady=5)
            
            if not usb_devices:
                ttk.Button(buttons_row1, text="📱 USB连接帮助", 
                          command=do_connect_usb).pack(side=tk.LEFT, padx=(0, 8))
            else:
                ttk.Button(buttons_row1, text="🔄 检查USB连接", 
                          command=do_connect_usb).pack(side=tk.LEFT, padx=(0, 8))
                          
            ttk.Button(buttons_row1, text="📡 添加远程设备", 
                      command=do_connect_remote).pack(side=tk.LEFT, padx=(0, 8))
            
            buttons_row2 = ttk.Frame(button_frame)
            buttons_row2.pack(fill=tk.X, pady=5)
            
            ttk.Button(buttons_row2, text="🔄 重新扫描", 
                      command=do_refresh_devices).pack(side=tk.LEFT, padx=(0, 8))
            
            if offline_devices or len(self.connected_devices) == 0:
                ttk.Button(buttons_row2, text="🔧 重启ADB服务", 
                          command=do_restart_adb).pack(side=tk.LEFT, padx=(0, 8))
            
            # 关闭按钮
            ttk.Button(main_frame, text="关闭", 
                      command=dialog.destroy).pack(pady=(10, 0))
            
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
            
        # 创建详情窗口
        details_window = tk.Toplevel(self.root)
        details_window.title("设备详细信息")
        details_window.geometry("600x400")
        details_window.resizable(True, True)
        
        # 创建文本框显示详细信息
        details_text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, 
                                           font=('Consolas', 9), bg='#f8f8f8')
        details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取每个设备的详细信息
        details_info = "=" * 50 + "\n"
        details_info += f"ADB设备详细信息 (共 {len(self.connected_devices)} 台)\n"
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
        
    def connect_device(self):
        """连接到指定IP的设备"""
        dialog = tk.Toplevel(self.root)
        dialog.title("连接设备")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        
        # IP地址输入
        ttk.Label(dialog, text="请输入设备IP地址:").pack(pady=(20, 5))
        ip_var = tk.StringVar(value="192.168.1.100:5555")
        ip_entry = ttk.Entry(dialog, textvariable=ip_var, width=30, font=('Consolas', 10))
        ip_entry.pack(pady=5)
        ip_entry.select_range(0, len(ip_var.get()))
        ip_entry.focus()
        
        def do_connect():
            ip_address = ip_var.get().strip()
            if ip_address:
                self._append_output(f"🔗 正在连接到 {ip_address}...\n")
                try:
                    result = subprocess.run(['adb', 'connect', ip_address],
                                        capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        self._append_output(f"✅ 连接成功: {result.stdout.strip()}\n")
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        self._append_output(f"❌ 连接失败: {result.stderr.strip()}\n")
                        messagebox.showerror("连接失败", result.stderr.strip())
                except Exception as e:
                    self._append_output(f"❌ 连接异常: {str(e)}\n")
                    messagebox.showerror("连接异常", str(e))
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址")
                
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="连接", command=do_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def connect_remote_device(self):
        """远程连接ADB设备"""
        dialog = tk.Toplevel(self.root)
        dialog.title("远程ADB连接")
        dialog.geometry("500x200")
        dialog.resizable(False, False)
        
        # IP地址和端口输入
        ttk.Label(dialog, text="请输入设备IP地址:").pack(pady=(15, 5))
        ip_var = tk.StringVar(value="192.168.1.100")
        ip_entry = ttk.Entry(dialog, textvariable=ip_var, width=30, font=('Consolas', 10))
        ip_entry.pack(pady=5)
        
        ttk.Label(dialog, text="请输入端口号:").pack(pady=(5, 5))
        port_var = tk.StringVar(value="5555")
        port_entry = ttk.Entry(dialog, textvariable=port_var, width=15, font=('Consolas', 10))
        port_entry.pack(pady=5)
        
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
                    
                    # 连接ADB
                    result = subprocess.run(['adb', 'connect', remote_address],
                                        capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        self._append_output(f"✅ 远程连接成功: {result.stdout.strip()}\n")
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        self._append_output(f"❌ 远程连接失败: {result.stderr.strip()}\n")
                        messagebox.showerror("连接失败", result.stderr.strip())
                except subprocess.TimeoutExpired:
                    self._append_output(f"❌ 连接超时: {remote_address}\n")
                    messagebox.showerror("连接超时", f"连接 {remote_address} 超时")
                except Exception as e:
                    self._append_output(f"❌ 连接异常: {str(e)}\n")
                    messagebox.showerror("连接异常", str(e))
            else:
                messagebox.showwarning("输入错误", "请输入有效的IP地址和端口号")
                
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        
        ttk.Button(button_frame, text="远程连接", command=do_remote_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def install_adb_keyboard(self):
        """安装ADB键盘应用"""
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
                                          capture_output=True, text=True, timeout=60)
            
            if install_result.returncode == 0:
                self._append_output(f"✅ ADB键盘安装成功: {install_result.stdout.strip()}\n")
                
                # 设置为默认输入法
                self._append_output("🔧 正在设置ADB键盘为默认输入法...\n")
                settings_result = subprocess.run(['adb', '-s', device_id, 'shell', 
                                               'ime enable com.android.adbkeyboard/.AdbIME'],
                                              capture_output=True, text=True, timeout=10)
                
                if settings_result.returncode == 0:
                    self._append_output("✅ ADB键盘已启用\n")
                    
                    # 切换到ADB键盘
                    switch_result = subprocess.run(['adb', '-s', device_id, 'shell', 
                                                  'ime set com.android.adbkeyboard/.AdbIME'],
                                                 capture_output=True, text=True, timeout=10)
                    
                    if switch_result.returncode == 0:
                        self._append_output("✅ ADB键盘已设置为默认输入法\n")
                        messagebox.showinfo("安装成功", "ADB键盘安装并设置成功！")
                    else:
                        self._append_output(f"⚠️ 设置默认输入法失败: {switch_result.stderr.strip()}\n")
                        messagebox.showwarning("部分成功", "键盘安装成功，但设置为默认输入法失败，请手动设置。")
                else:
                    self._append_output(f"⚠️ 启用ADB键盘失败: {settings_result.stderr.strip()}\n")
                    messagebox.showwarning("部分成功", "键盘安装成功，但启用失败，请手动启用。")
            else:
                self._append_output(f"❌ ADB键盘安装失败: {install_result.stderr.strip()}\n")
                messagebox.showerror("安装失败", install_result.stderr.strip())
                
        except subprocess.TimeoutExpired:
            self._append_output("❌ 安装超时，请检查设备连接\n")
            messagebox.showerror("安装超时", "安装过程超时，请检查设备连接状态")
        except Exception as e:
            self._append_output(f"❌ 安装异常: {str(e)}\n")
            messagebox.showerror("安装异常", str(e))


def main():
    root = tk.Tk()
    app = PhoneAgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()