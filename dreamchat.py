import sys
import os
import json
import threading
import webbrowser
import customtkinter as ctk
import requests
from datetime import datetime
from pathlib import Path

# PyInstaller --onefile 兼容：__file__ 指向临时解压目录
# 打包后配置/人格/文档应存储在 EXE 所在目录
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ['PYTHONIOENCODING'] = 'utf-8'

class AIScriptParser:
    """AIScript v1.0 解析器"""
    
    def parse(self, content):
        """解析 AIScript 文件，提取角色设定"""
        result = {
            'meta': {},
            'rules': [],
            'vars': {},
            'knowledge': {},
            'corpus': {},
            'flow': '',
            'system_prompt': ''
        }
        
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 边界标记
            if line == 'AUTH_CFG_START' or line == 'AUTH_CFG_END':
                continue
            
            # 区块标识
            if line.startswith('::'):
                current_section = line[2:].strip()
                continue
            
            # META 区块
            if current_section == 'META':
                if line.startswith('RID'):
                    result['meta']['id'] = self._extract_value(line)
                elif line.startswith('AID'):
                    result['meta']['author'] = self._extract_value(line)
                elif line.startswith('VER'):
                    result['meta']['version'] = self._extract_value(line)
                elif line.startswith('TYPE'):
                    result['meta']['type'] = self._extract_value(line)
                elif line.startswith('DSC'):
                    result['meta']['description'] = self._extract_value(line)
            
            # RULES 区块
            elif current_section == 'RULES':
                rule_match = self._parse_rule(line)
                if rule_match:
                    result['rules'].append(rule_match)
            
            # VARS 区块
            elif current_section == 'VARS':
                var_match = self._parse_variable(line)
                if var_match:
                    result['vars'][var_match[0]] = var_match[1]
            
            # KNW 区块
            elif current_section == 'KNW':
                knw_match = self._parse_knowledge(line)
                if knw_match:
                    result['knowledge'][knw_match[0]] = knw_match[1]
            
            # CORPUS 区块
            elif current_section == 'CORPUS':
                corpus_match = self._parse_corpus(line)
                if corpus_match:
                    result['corpus'][corpus_match[0]] = corpus_match[1]
            
            # FLOW 区块 - 保存原始内容
            elif current_section == 'FLOW':
                result['flow'] += line + '\n'
        
        # 生成系统提示词
        result['system_prompt'] = self._generate_system_prompt(result)
        
        return result
    
    def _extract_value(self, line):
        """提取值"""
        if '"' in line:
            parts = line.split('"')
            if len(parts) >= 2:
                return parts[1]
        return line
    
    def _parse_rule(self, line):
        """解析规则"""
        line = line.strip()
        if line.startswith('B0') or line.startswith('R0') or line.startswith('PR0'):
            parts = line.split('"')
            if len(parts) >= 2:
                return parts[1]
        return None
    
    def _parse_variable(self, line):
        """解析变量"""
        line = line.strip()
        if line.startswith('SET'):
            parts = line.split('=')
            if len(parts) >= 2:
                var_name = parts[0].replace('SET', '').strip()
                var_value = parts[1].strip().strip('"')
                return (var_name, var_value)
        return None
    
    def _parse_knowledge(self, line):
        """解析知识库"""
        line = line.strip()
        if '=' in line and not line.startswith('DIM') and not line.startswith('STD'):
            parts = line.split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip().strip('"')
                return (key, value)
        return None
    
    def _parse_corpus(self, line):
        """解析语料库"""
        line = line.strip()
        if line.endswith(':'):
            return (line[:-1], [])
        elif line.startswith('-'):
            return ('current', [line[1:].strip()])
        return None
    
    def _generate_system_prompt(self, data):
        """生成系统提示词"""
        prompt = ""
        
        # 角色基本信息
        if data['meta']:
            meta = data['meta']
            prompt += f"你是一个名为「{meta.get('id', 'AI助手')}」的AI角色。\n"
            if meta.get('description'):
                prompt += f"角色描述：{meta['description']}\n"
            if meta.get('author'):
                prompt += f"创作者：{meta['author']}\n"
            prompt += "\n"
        
        # 知识库信息
        if data['knowledge']:
            prompt += "【角色设定】\n"
            for key, value in data['knowledge'].items():
                prompt += f"{key}：{value}\n"
            prompt += "\n"
        
        # 行为规则
        if data['rules']:
            prompt += "【行为准则】\n"
            for rule in data['rules']:
                prompt += f"- {rule}\n"
            prompt += "\n"
        
        # 语料参考
        if data['corpus']:
            prompt += "【回复风格参考】\n"
            for category, lines in data['corpus'].items():
                if category != 'current' and lines:
                    prompt += f"{category}:\n"
                    for line in lines:
                        prompt += f"  - {line}\n"
            prompt += "\n"
        
        # 变量状态
        if data['vars']:
            prompt += "【会话状态】\n"
            for key, value in data['vars'].items():
                prompt += f"$ {key} = {value}\n"
            prompt += "\n"
        
        return prompt.strip()


class DreamChat(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title('DreamChat - AI助手')
        self.geometry('950x720')
        self.minsize(800, 600)
        
        # 配置
        self.config_file = os.path.join(BASE_DIR, 'data', 'config.json')
        self.api_config = self.load_config()
        self.chat_history = []
        self.chat_messages = []  # 保存所有消息的引用
        
        # 主题配置（五种高级主题）
        self.themes = {
            'midnight': {'name': '午夜极光', 'bg': '#0d1117', 'fg': '#58a6ff', 'accent': '#161b22', 'text': '#c9d1d9', 'chat_bg': '#0d1117', 'input_bg': '#161b22', 'user_bg': '#1f2937', 'ai_bg': '#161b22', 'user_text': '#e0e0e0', 'ai_text': '#c9d1d9'},
            'sakura': {'name': '绯樱隐士', 'bg': '#3d1f2e', 'fg': '#ff69b4', 'accent': '#4a2535', 'text': '#ffb6c1', 'chat_bg': '#3d1f2e', 'input_bg': '#4a2535', 'user_bg': '#5a3045', 'ai_bg': '#452535', 'user_text': '#ffb6c1', 'ai_text': '#ffc0cb'},
            'ocean': {'name': '深海秘境', 'bg': '#0a192f', 'fg': '#64ffda', 'accent': '#112240', 'text': '#ccd6f6', 'chat_bg': '#0a192f', 'input_bg': '#112240', 'user_bg': '#1d3557', 'ai_bg': '#112240', 'user_text': '#ccd6f6', 'ai_text': '#8892b0'},
            'forest': {'name': '翡翠幽林', 'bg': '#0a1a0a', 'fg': '#4ade80', 'accent': '#1a3a1a', 'text': '#d1fae5', 'chat_bg': '#0a1a0a', 'input_bg': '#1a3a1a', 'user_bg': '#2d5a2d', 'ai_bg': '#1a3a1a', 'user_text': '#d1fae5', 'ai_text': '#a7f3d0'},
            'ember': {'name': '暮火余烬', 'bg': '#1a0f0a', 'fg': '#ff9f43', 'accent': '#2d1a0e', 'text': '#ffe0c2', 'chat_bg': '#1a0f0a', 'input_bg': '#2d1a0e', 'user_bg': '#3d2415', 'ai_bg': '#2d1a0e', 'user_text': '#ffe0c2', 'ai_text': '#ffb380'}
        }
        
        valid_themes = list(self.themes.keys())
        self.current_theme = self.api_config.get('theme', 'midnight')
        if self.current_theme not in valid_themes:
            self.current_theme = 'midnight'
        
        # 人格配置
        self.personality_dir = os.path.join(BASE_DIR, 'personalities')
        os.makedirs(self.personality_dir, exist_ok=True)
        self.current_personality = None
        self.parser = AIScriptParser()
        
        # 模式标志
        self.is_personality_mode = False
        
        # 创建UI
        self._create_ui()
        
        # 应用主题
        self._apply_theme(self.themes[self.current_theme])
        
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        return {
            'api_key': '',
            'base_url': '',
            'model': '',
            'personality': '',
            'theme': 'midnight'
        }

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.api_config, f, indent=2, ensure_ascii=False)
        self.status_label.configure(text='✓ 已保存', text_color="#00FF88")
        self.after(2000, lambda: self.status_label.configure(text='就绪', text_color="gray"))
    
    def _apply_theme(self, theme):
        """应用主题"""
        self.theme = theme
        self.configure(fg_color=theme['bg'])
        
        # 更新标题栏
        self.header_frame.configure(fg_color=theme['accent'])
        self.title_label.configure(text_color=theme['fg'])
        self.dev_label.configure(text_color=theme['fg'])
        
        if self.is_personality_mode:
            self.mode_label.configure(text_color="#AA88FF")
        else:
            self.mode_label.configure(text_color=theme['fg'])
        
        # 更新按钮
        self.docs_btn.configure(border_color=theme['fg'], text_color=theme['fg'])
        self.settings_btn.configure(border_color=theme['fg'], text_color=theme['fg'])
        self.mode_btn.configure(border_color="#FF88AA", text_color="#FF88AA")
        
        # 更新状态标签
        self.status_label.configure(text_color="gray")
        
        # 更新输入区域
        self.input_container.configure(fg_color=theme['input_bg'])
        
        # 更新聊天区域背景
        self.chat_scroll.configure(fg_color=theme['chat_bg'])
        
        self._update_theme_menu()
        
        # 更新已有消息的颜色
        self._update_message_colors()
    
    def _update_message_colors(self):
        """更新已有消息的颜色"""
        if not hasattr(self, 'theme') or not hasattr(self, 'chat_messages'):
            return
        theme = self.theme
        
        for msg in self.chat_messages:
            try:
                msg_frame = msg['frame']
                role = msg['role']
                text_labels = msg.get('text_labels', [])
                
                # 确定颜色
                if role == 'user':
                    msg_bg = theme['user_bg']
                    msg_text = theme['user_text']
                elif role == 'assistant':
                    msg_bg = theme['ai_bg']
                    msg_text = theme['ai_text']
                else:
                    msg_bg = theme['chat_bg']
                    msg_text = "#ff6666"
                
                # 更新框架背景
                msg_frame.configure(fg_color=msg_bg)
                
                # 递归更新所有子控件背景
                def update_widget_colors(widget, bg_color):
                    try:
                        widget.configure(fg_color=bg_color)
                    except:
                        pass
                    for child in widget.winfo_children():
                        update_widget_colors(child, bg_color)
                
                update_widget_colors(msg_frame, msg_bg)
                
                # 更新文字颜色
                for label in text_labels:
                    try:
                        label.configure(text_color=msg_text)
                    except:
                        pass
                        
            except Exception as e:
                pass
    
    def _update_theme_menu(self):
        """更新主题菜单显示"""
        if hasattr(self, 'theme_menu'):
            theme_names = [f"{icon} {name}" for icon, name in 
                          [('🌌', '午夜极光'), ('🌸', '绯樱隐士'), ('🌊', '深海秘境'), ('🌲', '翡翠幽林'), ('🔥', '暮火余烬')]]
            self.theme_menu.configure(values=theme_names)
            current_idx = list(self.themes.keys()).index(self.current_theme)
            self.theme_menu.set(theme_names[current_idx])
    
    def _create_ui(self):
        # 主布局 - grid
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)
        
        # ===== 顶部标题栏 =====
        header_frame = ctk.CTkFrame(self, height=55)
        header_frame.grid(row=0, column=0, sticky='ew')
        self.header_frame = header_frame
        
        title_label = ctk.CTkLabel(
            header_frame,
            text='✦ DreamChat',
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#00D4FF"
        )
        self.title_label = title_label
        title_label.pack(side='left', padx=20, pady=12)
        
        # 开发者信息（可点击跳转B站主页）
        dev_label = ctk.CTkLabel(
            header_frame,
            text='by white-cat彼岸',
            font=ctk.CTkFont(size=10),
            text_color="#00D4FF",
            cursor="hand2"
        )
        self.dev_label = dev_label
        dev_label.pack(side='left', padx=5)
        dev_label.bind('<Button-1>', lambda e: webbrowser.open('https://space.bilibili.com/3493257650637602'))
        
        # 人格选择器
        # 模式显示标签
        self.mode_label = ctk.CTkLabel(
            header_frame,
            text='💬 默认模式',
            font=ctk.CTkFont(size=11),
            text_color="#00FF88"
        )
        self.mode_label.pack(side='left', padx=10)
        
        self.personality_label = ctk.CTkLabel(
            header_frame,
            text='',
            font=ctk.CTkFont(size=12),
            text_color="#AA88FF"
        )
        self.personality_label.pack(side='left', padx=5)
        
        self.personality_btn = ctk.CTkButton(
            header_frame,
            text='📋 切换人格',
            command=self.open_personality_selector,
            width=100,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_color="#AA88FF",
            border_width=1,
            text_color="#AA88FF"
        )
        self.personality_btn.pack(side='left', padx=5)
        self.personality_btn.pack_forget()  # 默认隐藏
        
        # 模式切换按钮
        self.mode_btn = ctk.CTkButton(
            header_frame,
            text='🎭 人格模式',
            command=self.toggle_mode,
            width=100,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_color="#FF88AA",
            border_width=1,
            text_color="#FF88AA"
        )
        self.mode_btn.pack(side='left', padx=5)
        
        self.status_label = ctk.CTkLabel(
            header_frame,
            text='● 就绪',
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.pack(side='right', padx=15)
        
        # ===== 主题切换下拉菜单 =====
        self._update_theme_menu()
        
        theme_menu = ctk.CTkOptionMenu(
            header_frame,
            values=['🌌 午夜极光', '🌸 绯樱隐士', '🌊 深海秘境', '🌲 翡翠幽林', '🔥 暮火余烬'],
            font=ctk.CTkFont(size=11),
            width=140,
            height=30,
            corner_radius=6,
            command=self._change_theme
        )
        self.theme_menu = theme_menu
        current_idx = list(self.themes.keys()).index(self.current_theme)
        theme_menu.set(list(self.themes.keys())[current_idx])
        theme_menu.pack(side='right', padx=10)
        
        # ===== 聊天区域 =====
        chat_container = ctk.CTkFrame(self)
        chat_container.grid(row=1, column=0, sticky='nsew', padx=15, pady=8)
        
        self.chat_scroll = ctk.CTkScrollableFrame(chat_container)
        self.chat_scroll.pack(fill='both', expand=True)
        
        self.add_message('assistant', '✨ 你好！我是 DreamChat AI助手\n有什么可以帮你的吗？')
        
        # ===== 输入区域 =====
        input_container = ctk.CTkFrame(self, height=65)
        input_container.grid(row=2, column=0, sticky='ew', padx=15, pady=10)
        self.input_container = input_container
        
        self.msg_entry = ctk.CTkEntry(
            input_container,
            height=45,
            font=ctk.CTkFont(size=14),
            corner_radius=10
        )
        self.msg_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.send_btn = ctk.CTkButton(
            input_container,
            text='发送',
            command=self.send_message,
            width=90,
            height=45,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#00D4FF"
        )
        self.send_btn.pack(side='right')
        
        self.msg_entry.bind('<Return>', lambda e: self.send_message())
        
        # ===== 设置按钮 =====
        self.settings_btn = ctk.CTkButton(
            header_frame,
            text='⚙️ 设置',
            command=self.open_settings,
            width=80,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#00D4FF",
            border_width=1,
            text_color="#00D4FF"
        )
        self.settings_btn.pack(side='right', padx=5)
        self.settings_win = None
        
        # 文档按钮（默认显示，人格模式下隐藏）
        self.docs_btn = ctk.CTkButton(
            header_frame,
            text='📖 文档',
            command=self.open_docs,
            width=80,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#FFD700",
            border_width=1,
            text_color="#FFD700"
        )
        self.docs_btn.pack(side='right', padx=15)
        
    def _change_theme(self, theme_name):
        """切换主题"""
        theme_map = {
            '🌌 午夜极光': 'midnight',
            '🌸 绯樱隐士': 'sakura',
            '🌊 深海秘境': 'ocean',
            '🌲 翡翠幽林': 'forest',
            '🔥 暮火余烬': 'ember'
        }
        theme_key = theme_map.get(theme_name, 'midnight')
        self.current_theme = theme_key
        self.api_config['theme'] = theme_key
        self._apply_theme(self.themes[theme_key])
        self.save_config()
    
    def open_settings(self):
        """打开设置窗口（只允许一个）"""
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.attributes('-topmost', True)
            self.after(200, lambda: self.settings_win.attributes('-topmost', False))
            return
        
        settings_win = ctk.CTkToplevel(self)
        self.settings_win = settings_win
        settings_win.title('设置')
        settings_win.geometry('500x420')
        settings_win.resizable(False, False)
        
        settings_win.update_idletasks()
        x = (settings_win.winfo_screenwidth() // 2) - 250
        y = (settings_win.winfo_screenheight() // 2) - 210
        settings_win.geometry(f'+{x}+{y}')
        
        settings_win.attributes('-topmost', True)
        self.after(200, lambda: settings_win.attributes('-topmost', False))
        
        # 标题
        title_label = ctk.CTkLabel(
            settings_win,
            text='⚙️ 设置',
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#00D4FF"
        )
        title_label.pack(pady=(20, 15))
        
        # API Key 设置
        api_frame = ctk.CTkFrame(settings_win, corner_radius=8)
        api_frame.pack(fill='x', padx=20, pady=5)
        
        ctk.CTkLabel(api_frame, text='🔑 API Key', font=ctk.CTkFont(size=12, weight="bold")).pack(anchor='w', padx=10, pady=6)
        
        settings_api_key = ctk.CTkEntry(
            api_frame,
            width=440,
            show='•',
            font=ctk.CTkFont(size=12)
        )
        settings_api_key.pack(padx=10, pady=(0, 10))
        settings_api_key.insert(0, self.api_config.get('api_key', ''))
        
        # Base URL 设置
        url_frame = ctk.CTkFrame(settings_win, corner_radius=8)
        url_frame.pack(fill='x', padx=20, pady=5)
        
        ctk.CTkLabel(url_frame, text='🌐 Base URL', font=ctk.CTkFont(size=12, weight="bold")).pack(anchor='w', padx=10, pady=6)
        
        settings_base_url = ctk.CTkEntry(
            url_frame,
            width=440,
            font=ctk.CTkFont(size=12)
        )
        settings_base_url.pack(padx=10, pady=(0, 10))
        settings_base_url.insert(0, self.api_config.get('base_url', ''))
        
        # Model 设置
        model_frame = ctk.CTkFrame(settings_win, corner_radius=8)
        model_frame.pack(fill='x', padx=20, pady=5)
        
        ctk.CTkLabel(model_frame, text='🤖 Model', font=ctk.CTkFont(size=12, weight="bold")).pack(anchor='w', padx=10, pady=6)
        
        settings_model = ctk.CTkOptionMenu(
            model_frame,
            values=['加载中...'],
            font=ctk.CTkFont(size=12),
            width=200
        )
        settings_model.pack(padx=10, pady=(0, 10))
        settings_model.set(self.api_config.get('model', ''))
        
        # 刷新模型列表按钮
        refresh_btn = ctk.CTkButton(
            model_frame,
            text='🔄 刷新',
            command=lambda: self._fetch_models(settings_api_key.get(), settings_base_url.get(), settings_model),
            width=80,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_color="#00D4FF",
            border_width=1
        )
        refresh_btn.pack(padx=10, pady=(0, 10), side='right')
        
        # 自动获取模型列表
        threading.Thread(
            target=lambda: self._fetch_models(
                settings_api_key.get(),
                settings_base_url.get(),
                settings_model
            ),
            daemon=True
        ).start()
        
        # 保存按钮
        save_btn = ctk.CTkButton(
            settings_win,
            text='💾 保存设置',
            command=lambda: self._save_settings(settings_api_key, settings_base_url, settings_model, settings_win),
            width=160,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#00D4FF"
        )
        save_btn.pack(pady=12)
        
        # 关闭按钮
        close_btn = ctk.CTkButton(
            settings_win,
            text='关闭',
            command=settings_win.destroy,
            width=100,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#555",
            border_width=1
        )
        close_btn.pack(pady=(0, 15))
        
        settings_win.protocol("WM_DELETE_WINDOW", lambda: self._close_settings())
    
    def _close_settings(self):
        if self.settings_win:
            self.settings_win.destroy()
            self.settings_win = None
    
    def _fetch_models(self, api_key, base_url, model_menu):
        if not api_key or not base_url:
            return
        
        try:
            url = f'{base_url}/models'
            headers = {'Authorization': f'Bearer {api_key}'}
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = [m['id'] for m in data.get('data', [])]
                
                if models:
                    def update_ui():
                        model_menu.configure(values=models)
                        current = self.api_config.get('model', '')
                        if current in models:
                            model_menu.set(current)
                        else:
                            model_menu.set(models[0])
                    
                    self.after(0, update_ui)
        except Exception as e:
            print(f"获取模型列表失败: {e}")
    
    def _save_settings(self, api_key_entry, url_entry, model_menu, win):
        self.api_config['api_key'] = api_key_entry.get()
        self.api_config['base_url'] = url_entry.get()
        self.api_config['model'] = model_menu.get()
        self.save_config()
        
        self.status_label.configure(text='✓ 设置已保存', text_color="#00FF88")
        self.after(2000, lambda: self.status_label.configure(text='就绪', text_color="gray"))
        win.destroy()
    
    def open_personality_selector(self):
        """打开人格选择器"""
        selector_win = ctk.CTkToplevel(self)
        selector_win.title('选择人格')
        selector_win.geometry('400x500')
        selector_win.resizable(False, False)
        
        selector_win.update_idletasks()
        x = (selector_win.winfo_screenwidth() // 2) - 200
        y = (selector_win.winfo_screenheight() // 2) - 250
        selector_win.geometry(f'+{x}+{y}')
        
        selector_win.attributes('-topmost', True)
        self.after(200, lambda: selector_win.attributes('-topmost', False))
        
        # 标题
        title_label = ctk.CTkLabel(
            selector_win,
            text='🎭 选择人格',
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#AA88FF"
        )
        title_label.pack(pady=(20, 15))
        
        # 人格列表框
        list_frame = ctk.CTkFrame(selector_win, corner_radius=8)
        list_frame.pack(fill='both', expand=True, padx=20, pady=5)
        
        # 获取所有人格文件
        personalities = self._load_personalities()
        
        # 创建滚动列表
        personality_list = ctk.CTkScrollableFrame(list_frame)
        personality_list.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 添加"无"选项
        none_btn = ctk.CTkButton(
            personality_list,
            text='🚫 无（默认）',
            command=lambda: self._select_personality(None, selector_win),
            width=340,
            height=40,
            corner_radius=8,
            fg_color="transparent" if self.current_personality is None else "#2a2a4a",
            border_color="#555",
            border_width=1,
            anchor='w'
        )
        none_btn.pack(pady=3)
        
        if not personalities:
            # 显示提示
            empty_label = ctk.CTkLabel(
                personality_list,
                text='暂无导入的人格\n点击"导入新人格"添加',
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            empty_label.pack(pady=20)
        
        # 添加其他人格
        for person in personalities:
            btn = ctk.CTkButton(
                personality_list,
                text=f"🎭 {person['name']}",
                command=lambda p=person: self._select_personality(p, selector_win),
                width=340,
                height=40,
                corner_radius=8,
                fg_color="transparent" if self.current_personality and self.current_personality['file'] == person['file'] else "#2a2a4a",
                border_color="#555",
                border_width=1,
                anchor='w'
            )
            btn.pack(pady=3)
        
        # 导入新人格按钮
        import_btn = ctk.CTkButton(
            selector_win,
            text='📥 导入新人格',
            command=lambda: self._import_personality(selector_win),
            width=200,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#AA88FF",
            border_width=1,
            text_color="#AA88FF"
        )
        import_btn.pack(pady=10)
        
        # 关闭按钮
        close_btn = ctk.CTkButton(
            selector_win,
            text='关闭',
            command=selector_win.destroy,
            width=100,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#555",
            border_width=1
        )
        close_btn.pack(pady=(0, 20))
    
    def _load_personalities(self):
        """加载所有人格文件"""
        personalities = []
        
        for file in Path(self.personality_dir).glob('*.aiscript'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                parsed = self.parser.parse(content)
                meta = parsed['meta']
                
                personalities.append({
                    'file': str(file),
                    'name': meta.get('id', file.stem),
                    'description': meta.get('description', ''),
                    'type': meta.get('type', 'OPEN'),
                    'parsed': parsed
                })
            except Exception as e:
                print(f"加载人格文件失败 {file.name}: {e}")
        
        return personalities
    
    def toggle_mode(self):
        """切换模式"""
        self.is_personality_mode = not self.is_personality_mode
        
        if self.is_personality_mode:
            self.mode_btn.configure(text='💬 默认模式')
            self.mode_label.configure(text='🎭 人格模式', text_color="#AA88FF")
            self.status_label.configure(text='● 人格模式', text_color="#FF88AA")
            
            # 显示人格选择按钮
            self.personality_btn.pack(side='left', padx=5)
            
            # 如果当前有人格，自动加载
            if self.current_personality:
                self.add_message('assistant', f"✨ 已切换到人格模式\n当前人格：{self.current_personality['name']}")
            else:
                self.add_message('assistant', "✨ 已切换到人格模式\n请点击「切换人格」选择角色")
        else:
            self.mode_btn.configure(text='🎭 人格模式')
            self.mode_label.configure(text='💬 默认模式', text_color="#00FF88")
            self.status_label.configure(text='● 就绪', text_color="gray")
            
            # 隐藏人格选择按钮
            self.personality_btn.pack_forget()
            
            self.add_message('assistant', '✨ 已切换到默认模式\n\n你好！我是 **DreamChat**，由 Bilibili 的 white-cat彼岸 开发。\n\n🔗 B站主页：https://space.bilibili.com/3493257650637602\n\n我可以帮助你回答问题、创作内容、编程辅助等。有什么可以帮你的吗？😊')
    
    def _select_personality(self, personality, win):
        """选择人格"""
        self.current_personality = personality
        self.api_config['personality'] = personality['file'] if personality else ''
        self.save_config()
        
        # 更新显示
        if personality:
            self.personality_label.configure(text=f"· {personality['name']}", text_color="#AA88FF")
            if self.is_personality_mode:
                self.status_label.configure(text=f'● {personality["name"]}', text_color="#FF88AA")
        else:
            self.personality_label.configure(text="", text_color="#AA88FF")
            if self.is_personality_mode:
                self.status_label.configure(text='● 人格模式', text_color="#FF88AA")
        
        # 清空聊天并显示欢迎消息
        self.chat_history.clear()
        for widget in self.chat_scroll.winfo_children():
            widget.destroy()
        
        if personality:
            self.add_message('assistant', f"✨ 已加载人格：{personality['name']}\n{personality['description']}\n\n请问有什么可以帮你的？")
        else:
            self.add_message('assistant', '✨ 已选择默认模式\n你好！我是 DreamChat AI助手')
        
        win.destroy()
    
    def _import_personality(self, win):
        """导入新人格"""
        file_path = ctk.filedialog.askopenfilename(
            title='选择 AIScript 文件',
            filetypes=[('AIScript 文件', '*.aiscript'), ('所有文件', '*.*')],
            initialdir=self.personality_dir
        )
        
        if file_path:
            try:
                # 复制到人格目录
                import shutil
                dest_path = os.path.join(self.personality_dir, os.path.basename(file_path))
                shutil.copy2(file_path, dest_path)
                
                # 重新加载并选择
                self._load_and_select_personality(dest_path)
                win.destroy()
            except Exception as e:
                ctk.CTkMessageBox(
                    self,
                    title='导入失败',
                    message=f'导入人格文件失败：{str(e)}',
                    icon='error'
                ).show()
    
    def _load_and_select_personality(self, file_path):
        """加载并选择人格"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            parsed = self.parser.parse(content)
            meta = parsed['meta']
            
            personality = {
                'file': file_path,
                'name': meta.get('id', os.path.basename(file_path)),
                'description': meta.get('description', ''),
                'type': meta.get('type', 'OPEN'),
                'parsed': parsed
            }
            
            self.current_personality = personality
            self.api_config['personality'] = file_path
            self.save_config()
            
            self.personality_label.configure(text=f"🎭 {personality['name']}")
            
            # 清空聊天
            self.chat_history.clear()
            for widget in self.chat_scroll.winfo_children():
                widget.destroy()
            
            self.add_message('assistant', f"✨ 已加载人格：{personality['name']}\n{personality['description']}\n\n请问有什么可以帮你的？")
            
        except Exception as e:
            print(f"加载人格文件失败: {e}")
    
    def add_message(self, role, content):
        """添加消息到聊天区域"""
        time_str = datetime.now().strftime('%H:%M')
        theme = getattr(self, 'theme', self.themes['midnight'])
        
        # 保存消息引用以便后续更新颜色
        text_labels = []

        if role == 'user':
            msg_frame = ctk.CTkFrame(self.chat_scroll, corner_radius=15, fg_color=theme['user_bg'])
            msg_frame.pack(fill='x', pady=5, anchor='e')

            # 用户标签（右侧）
            icon_label = ctk.CTkLabel(msg_frame, text='👤', font=ctk.CTkFont(size=14), width=35, anchor='e', fg_color=theme['user_bg'])
            icon_label.pack(side='right', padx=5, pady=8)

            # 内容容器（右侧对齐，自动填充）
            content_frame = ctk.CTkFrame(msg_frame, corner_radius=12, fg_color=theme['user_bg'])
            content_frame.pack(side='right', fill='x', expand=True, padx=(0, 45), pady=6)

            # 时间戳（右对齐）
            time_label = ctk.CTkLabel(content_frame, text=time_str, font=ctk.CTkFont(size=10), text_color="#888888", anchor='e', fg_color=theme['user_bg'])
            time_label.pack(anchor='e', padx=10, pady=(0, 2))
            
            # 消息内容（使用 wrap 自动换行）
            text_label = ctk.CTkLabel(
                content_frame, 
                text=content, 
                anchor='w', 
                font=ctk.CTkFont(size=13), 
                text_color=theme['user_text'],
                wraplength=500,
                fg_color=theme['user_bg']
            )
            text_label.pack(padx=10, pady=5, fill='x', expand=True)
            text_labels.append(text_label)

            # 用户消息立即滚动
            self.after(10, self._scroll_to_bottom)

        elif role == 'assistant':
            msg_frame = ctk.CTkFrame(self.chat_scroll, corner_radius=15, fg_color=theme['ai_bg'])
            msg_frame.pack(fill='x', pady=5, anchor='w')

            # AI标签（左侧）
            icon_label = ctk.CTkLabel(msg_frame, text='🤖', font=ctk.CTkFont(size=14), width=35, anchor='w', fg_color=theme['ai_bg'])
            icon_label.pack(side='left', padx=5, pady=8)

            # 内容容器（左侧对齐，自动填充）
            content_frame = ctk.CTkFrame(msg_frame, corner_radius=12, fg_color=theme['ai_bg'])
            content_frame.pack(side='left', fill='x', expand=True, padx=(0, 45), pady=6)

            # 时间戳（左对齐）
            time_label = ctk.CTkLabel(content_frame, text=time_str, font=ctk.CTkFont(size=10), text_color="#888888", anchor='w', fg_color=theme['ai_bg'])
            time_label.pack(anchor='w', padx=10, pady=(0, 2))

            # 消息内容（多行，自动换行）
            for line in content.split('\n'):
                label = ctk.CTkLabel(
                    content_frame,
                    text=line if line else " ",
                    anchor='w',
                    font=ctk.CTkFont(size=13),
                    text_color=theme['ai_text'],
                    wraplength=500,
                    fg_color=theme['ai_bg']
                )
                label.pack(anchor='w', padx=10, pady=2, fill='x')
                text_labels.append(label)

            # AI消息立即滚动到底部
            self.after(10, self._scroll_to_bottom)

        else:
            msg_frame = ctk.CTkFrame(self.chat_scroll, corner_radius=10, fg_color=theme['chat_bg'])
            msg_frame.pack(fill='x', pady=5)
            ctk.CTkLabel(msg_frame, text=f'⚠️ {content}', font=ctk.CTkFont(size=12), text_color="orange", fg_color=theme['chat_bg']).pack(pady=8)

            self._scroll_to_bottom()
        
        # 保存消息引用到列表
        self.chat_messages.append({
            'frame': msg_frame,
            'role': role,
            'text_labels': text_labels,
            'time_label': time_label if role in ['user', 'assistant'] else None
        })
    
    def _scroll_to_bottom(self):
        """强制滚动到底部"""
        try:
            # CTkScrollableFrame 内部结构：_parent_frame -> _parent_canvas
            if hasattr(self.chat_scroll, '_parent_canvas'):
                self.chat_scroll._parent_canvas.yview_moveto(1.0)
            elif hasattr(self.chat_scroll, '_parent_frame'):
                # 尝试通过父框架找到canvas
                for child in self.chat_scroll._parent_frame.winfo_children():
                    if isinstance(child, tkinter.Canvas):
                        child.yview_moveto(1.0)
                        break
            print("[DEBUG] 已执行滚动")
        except Exception as e:
            print(f"[DEBUG] 滚动失败: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_chat(self):
        self.chat_history.clear()
        for widget in self.chat_scroll.winfo_children():
            widget.destroy()
        
        if self.is_personality_mode and self.current_personality:
            self.add_message('assistant', f"✨ 对话已清空\n继续与「{self.current_personality['name']}」聊天吧")
        else:
            self.add_message('assistant', '✨ 对话已清空\n你好！我是 DreamChat AI助手')
    
    def send_message(self):
        message = self.msg_entry.get().strip()
        if not message:
            return
        
        self.msg_entry.delete(0, 'end')
        self.add_message('user', message)
        
        self.send_btn.configure(state='disabled', text='⏳')
        self.status_label.configure(text='● 思考中...', text_color="orange")
        
        threading.Thread(target=self._call_api, args=(message,), daemon=True).start()
    
    def _call_api(self, message):
        api_key = self.api_config.get('api_key', '')
        base_url = self.api_config.get('base_url', '')
        model = self.api_config.get('model', '')
        
        # 根据模式选择系统提示词
        if self.is_personality_mode and self.current_personality:
            system_prompt = self.current_personality['parsed']['system_prompt']
        else:
            system_prompt = """你是 DreamChat，由 Bilibili 的 white-cat彼岸 开发的项目。

【身份信息】
- 名字：DreamChat
- 开发者：white-cat彼岸（Bilibili 创作者）
- B站主页：https://space.bilibili.com/3493257650637602
- 定位：智能、友好、有用的AI助手

【行为准则】
1. 用中文回答用户问题
2. 保持友好、专业的态度
3. 诚实回答，不懂就说不懂
4. 不编造信息，不提供有害建议
5. 尊重用户，不评判用户的选择
6. 可以提及开发者是 Bilibili 的 white-cat彼岸

【回复风格】
- 简洁明了，不过度冗长
- 适当使用表情符号增加亲和力
- 结构清晰，重点突出
- 主动提供帮助和建议

【安全边界】
- 不输出违法、暴力、色情内容
- 不泄露个人隐私信息
- 不进行政治敏感讨论
- 不提供医疗、法律等专业建议（仅供参考）

现在请以 DreamChat 的身份开始对话。"""
        
        if not api_key:
            self.after(0, lambda: self.add_message('system', '请先在设置中配置 API Key！'))
            self.after(0, lambda: self.send_btn.configure(state='normal', text='发送'))
            self.after(0, lambda: self.status_label.configure(text='● 错误', text_color="red"))
            return

        if not base_url or not model:
            self.after(0, lambda: self.add_message('system', '请先在设置中配置 Base URL 和 Model！'))
            self.after(0, lambda: self.send_btn.configure(state='normal', text='发送'))
            self.after(0, lambda: self.status_label.configure(text='● 错误', text_color="red"))
            return
        
        try:
            url = f'{base_url}/chat/completions'
            messages = [
                {'role': 'system', 'content': system_prompt},
                *self.chat_history,
                {'role': 'user', 'content': message}
            ]
            
            payload = {'model': model, 'messages': messages, 'max_tokens': 1500, 'temperature': 0.7}
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
            
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            assistant_msg = data['choices'][0]['message']['content']
            
            self.chat_history.append({'role': 'user', 'content': message})
            self.chat_history.append({'role': 'assistant', 'content': assistant_msg})
            if len(self.chat_history) > 30:
                self.chat_history = self.chat_history[-30:]
            
            self.after(0, lambda: self.add_message('assistant', assistant_msg))
            self.after(0, lambda: self.status_label.configure(text='● 就绪', text_color="#00FF88"))
            
        except Exception as e:
            error_msg = str(e)
            if '401' in error_msg or '403' in error_msg:
                error_msg = 'API Key 无效或已过期'
            elif 'timeout' in error_msg.lower():
                error_msg = '请求超时，请检查网络连接'
            
            self.after(0, lambda: self.add_message('system', error_msg))
            self.after(0, lambda: self.status_label.configure(text='● 错误', text_color="red"))
        finally:
            self.after(0, lambda: self.send_btn.configure(state='normal', text='发送'))
    
    def open_docs(self):
        """打开文档阅读窗口"""
        if hasattr(self, 'docs_win') and self.docs_win and self.docs_win.winfo_exists():
            self.docs_win.lift()
            self.docs_win.attributes('-topmost', True)
            return
        
        docs_win = ctk.CTkToplevel(self)
        self.docs_win = docs_win
        docs_win.title('📖 文档中心')
        docs_win.geometry('850x600')
        docs_win.resizable(True, True)
        
        docs_win.update_idletasks()
        x = (docs_win.winfo_screenwidth() // 2) - 425
        y = (docs_win.winfo_screenheight() // 2) - 300
        docs_win.geometry(f'+{x}+{y}')
        
        docs_win.attributes('-topmost', True)
        
        # 顶部导航栏
        nav_frame = ctk.CTkFrame(docs_win, height=45)
        nav_frame.pack(fill='x')
        
        self.docs_tab_btns = []
        tabs = ['使用说明', 'AIScript V1.0']
        for i, tab_name in enumerate(tabs):
            btn = ctk.CTkButton(
                nav_frame,
                text=tab_name,
                width=120,
                height=35,
                corner_radius=8,
                fg_color="#00D4FF" if i == 0 else "transparent",
                border_color="#00D4FF" if i == 0 else "#555",
                border_width=1,
                text_color="white" if i == 0 else "#ccc",
                font=ctk.CTkFont(size=12, weight="bold" if i == 0 else "normal"),
                command=lambda t=i: self._switch_docs_tab(t)
            )
            btn.pack(side='left', padx=10, pady=5)
            self.docs_tab_btns.append(btn)
        
        # 关闭按钮
        close_btn = ctk.CTkButton(
            nav_frame,
            text='✕',
            width=40,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_color="#555",
            border_width=1,
            text_color="#888",
            font=ctk.CTkFont(size=14),
            command=docs_win.destroy
        )
        close_btn.pack(side='right', padx=15)
        
        # 内容区域
        content_frame = ctk.CTkFrame(docs_win)
        content_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        self.docs_content = ctk.CTkScrollableFrame(content_frame)
        self.docs_content.pack(fill='both', expand=True)
        
        # 加载使用说明
        self._load_docs_tab(0)
    
    def _load_docs_tab(self, tab_index):
        """加载文档标签页内容"""
        # 清空当前内容
        for widget in self.docs_content.winfo_children():
            widget.destroy()
        
        # 更新按钮样式
        for i, btn in enumerate(self.docs_tab_btns):
            if i == tab_index:
                btn.configure(
                    fg_color="#00D4FF",
                    text_color="white",
                    font=ctk.CTkFont(size=12, weight="bold")
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color="#ccc",
                    font=ctk.CTkFont(size=12)
                )
        
        if tab_index == 0:
            # 使用说明
            readme_content = """# DreamChat 使用说明

## 功能简介
DreamChat 是一款桌面聊天客户端，支持两种模式：
- **默认模式**：作为 DreamChat AI 助手与您对话
- **人格模式**：使用 AIScript v1.0 配置文件定义的角色与您对话

## 快速开始

### 1. 配置 API
1. 点击首页右上角 **⚙️ 设置** 按钮
2. 输入您的 API Key
3. 输入 Base URL（如 `https://api.agnes-ai.cn/v1`）
4. 输入或选择 Model（可点击"刷新"自动获取模型列表）
5. 点击 **💾 保存设置**

### 2. 开始聊天
- 在底部输入框输入消息，按 Enter 或点击 **发送** 按钮
- 聊天记录会话中保留，最多保留最近 30 条

### 3. 切换模式
- 点击 **🎭 人格模式** 切换到人格模式
- 点击 **💬 默认模式** 切换回默认模式

### 4. 管理人格（人格模式）
- 点击 **📋 切换人格** 打开人格选择器
- 可以选择已导入的人格，或点击 **📥 导入新人格** 添加 .aiscript 文件
- 导入后人格文件会保存到 `personalities/` 文件夹

---
作者：Bilibili white-cat彼岸
"""
            ctk.CTkLabel(
                self.docs_content,
                text=readme_content,
                font=ctk.CTkFont(size=13),
                text_color="#e0e0e0",
                justify='left'
            ).pack(padx=15, pady=10, anchor='w')
        
        elif tab_index == 1:
            # AIScript V1.0 说明书
            try:
                script_path = os.path.join(BASE_DIR, 'AIScript V1.0.txt')
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                
                ctk.CTkLabel(
                    self.docs_content,
                    text=script_content,
                    font=ctk.CTkFont(size=12),
                    text_color="#e0e0e0",
                    justify='left'
                ).pack(padx=15, pady=10, anchor='w')
            except Exception as e:
                ctk.CTkLabel(
                    self.docs_content,
                    text=f'加载 AIScript 文档失败：{str(e)}',
                    font=ctk.CTkFont(size=13),
                    text_color="#ff6666"
                ).pack(padx=15, pady=10)
    
    def _switch_docs_tab(self, tab_index):
        """切换文档标签页"""
        self._load_docs_tab(tab_index)

if __name__ == '__main__':
    app = DreamChat()
    app.mainloop()
