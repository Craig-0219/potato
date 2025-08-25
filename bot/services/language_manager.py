# bot/services/language_manager.py - 多語言支援管理服務
"""
多語言支援管理服務
提供國際化 (i18n) 功能、語言偵測、翻譯等服務
"""

import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from shared.logger import logger

class LanguageManager:
    """多語言支援管理器"""
    
    def __init__(self):
        self.supported_languages = {
            'zh-TW': '繁體中文',
            'zh-CN': '简体中文', 
            'en': 'English',
            'ja': '日本語',
            'ko': '한국어'
        }
        
        self.default_language = 'zh-TW'
        self.fallback_language = 'en'
        
        # 語言包緩存
        self.language_packs = {}
        
        # 語言偵測規則
        self.detection_rules = self._load_detection_rules()
        
        # 初始化語言包
        self._load_all_language_packs()
    
    # ========== 語言包管理 ==========
    
    def _load_all_language_packs(self):
        """載入所有語言包"""
        try:
            language_dir = os.path.join(os.path.dirname(__file__), '..', 'locales')
            
            # 如果目錄不存在，創建預設語言包
            if not os.path.exists(language_dir):
                os.makedirs(language_dir, exist_ok=True)
                self._create_default_language_packs(language_dir)
            
            # 載入所有語言包
            for lang_code in self.supported_languages.keys():
                self._load_language_pack(lang_code, language_dir)
                
            logger.info(f"✅ 已載入 {len(self.language_packs)} 個語言包")
            
        except Exception as e:
            logger.error(f"載入語言包錯誤: {e}")
            # 創建基本的中文語言包作為後備
            self._create_fallback_language_pack()
    
    def _load_language_pack(self, lang_code: str, language_dir: str):
        """載入指定語言包"""
        try:
            file_path = os.path.join(language_dir, f"{lang_code}.json")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.language_packs[lang_code] = json.load(f)

    def _create_default_language_packs(self, language_dir: str):
        """創建預設語言包"""
        # 繁體中文語言包
        zh_tw_pack = self._get_zh_tw_pack()
        
        # 英文語言包
        en_pack = self._get_en_pack()
        
        # 簡體中文語言包
        zh_cn_pack = self._get_zh_cn_pack()
        
        # 日文語言包
        ja_pack = self._get_ja_pack()
        
        # 韓文語言包
        ko_pack = self._get_ko_pack()
        
        language_packs = {
            'zh-TW': zh_tw_pack,
            'en': en_pack,
            'zh-CN': zh_cn_pack,
            'ja': ja_pack,
            'ko': ko_pack
        }
        
        for lang_code, pack in language_packs.items():
            try:
                file_path = os.path.join(language_dir, f"{lang_code}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(pack, f, ensure_ascii=False, indent=2)
                logger.info(f"創建語言包文件: {file_path}")
            except Exception as e:
                logger.error(f"創建語言包 {lang_code} 錯誤: {e}")
    
    def _create_fallback_language_pack(self):
        """創建後備語言包"""
        self.language_packs['zh-TW'] = self._get_zh_tw_pack()
        logger.info("創建後備中文語言包")
    
    # ========== 語言偵測 ==========
    
    def detect_language(self, text: str, user_locale: str = None) -> str:
        """偵測文本語言"""
        try:
            # 1. 優先使用用戶設定的語言
            if user_locale and user_locale in self.supported_languages:
                return user_locale
            
            # 2. 基於文本內容偵測
            detected_lang = self._detect_by_content(text)
            if detected_lang:
                return detected_lang
            
            # 3. 返回預設語言
            return self.default_language
            
        except Exception as e:
            logger.error(f"語言偵測錯誤: {e}")
            return self.default_language
    
    def _detect_by_content(self, text: str) -> Optional[str]:
        """基於內容偵測語言"""
        if not text or len(text.strip()) < 5:
            return None
        
        text = text.lower().strip()
        
        # 中文偵測（繁體/簡體）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if chinese_chars > 0:
            # 繁簡體偵測
            traditional_indicators = ['請', '時', '會', '說', '門', '車', '電', '話', '問', '題']
            simplified_indicators = ['请', '时', '会', '说', '门', '车', '电', '话', '问', '题']
            
            traditional_score = sum(1 for char in traditional_indicators if char in text)
            simplified_score = sum(1 for char in simplified_indicators if char in text)
            
            if traditional_score > simplified_score:
                return 'zh-TW'
            elif simplified_score > traditional_score:
                return 'zh-CN'
            else:
                return 'zh-TW'  # 預設繁體
        
        # 日文偵測
        hiragana = len(re.findall(r'[\u3040-\u309f]', text))
        katakana = len(re.findall(r'[\u30a0-\u30ff]', text))
        if hiragana > 0 or katakana > 0:
            return 'ja'
        
        # 韓文偵測
        korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))
        if korean_chars > 0:
            return 'ko'
        
        # 英文偵測（基於常見英文詞彙）
        english_words = ['the', 'and', 'you', 'that', 'was', 'for', 'are', 'with', 'his', 'they']
        english_score = sum(1 for word in english_words if f' {word} ' in f' {text} ')
        if english_score >= 2:
            return 'en'
        
        return None
    
    def _load_detection_rules(self) -> Dict[str, Any]:
        """載入語言偵測規則"""
        return {
            'zh-TW': {
                'chars': r'[\u4e00-\u9fff]',
                'indicators': ['請', '時', '會', '說', '門', '車', '電', '話'],
                'weight': 1.0
            },
            'zh-CN': {
                'chars': r'[\u4e00-\u9fff]',
                'indicators': ['请', '时', '会', '说', '门', '车', '电', '话'],
                'weight': 1.0
            },
            'ja': {
                'chars': r'[\u3040-\u309f\u30a0-\u30ff]',
                'indicators': ['です', 'ます', 'した', 'して'],
                'weight': 1.2
            },
            'ko': {
                'chars': r'[\uac00-\ud7af]',
                'indicators': ['입니다', '합니다', '했습니다'],
                'weight': 1.2
            },
            'en': {
                'chars': r'[a-zA-Z]',
                'indicators': ['the', 'and', 'you', 'that', 'was'],
                'weight': 0.8
            }
        }
    
    # ========== 本地化字串獲取 ==========
    
    def get_string(self, key: str, lang_code: str = None, **kwargs) -> str:
        """獲取本地化字串"""
        try:
            # 決定使用的語言
            if not lang_code:
                lang_code = self.default_language
            
            # 嘗試獲取指定語言的字串
            if lang_code in self.language_packs:
                text = self._get_nested_string(self.language_packs[lang_code], key)
                if text:
                    return self._format_string(text, **kwargs)
            
            # 後備語言
            if self.fallback_language in self.language_packs:
                text = self._get_nested_string(self.language_packs[self.fallback_language], key)
                if text:
                    return self._format_string(text, **kwargs)
            
            # 預設語言
            if self.default_language in self.language_packs:
                text = self._get_nested_string(self.language_packs[self.default_language], key)
                if text:
                    return self._format_string(text, **kwargs)
            
            # 如果都找不到，返回 key 本身
            logger.warning(f"找不到本地化字串: {key} ({lang_code})")
            return key
            
        except Exception as e:
            logger.error(f"獲取本地化字串錯誤: {e}")
            return key
    
    def _get_nested_string(self, language_pack: Dict[str, Any], key: str) -> Optional[str]:
        """獲取嵌套的字串"""
        try:
            keys = key.split('.')
            current = language_pack
            
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return None
            
            return current if isinstance(current, str) else None
            
        except Exception:
            return None
    
    def _format_string(self, text: str, **kwargs) -> str:
        """格式化字串"""
        try:
            if kwargs:
                return text.format(**kwargs)
            return text
        except Exception as e:
            logger.error(f"字串格式化錯誤: {e}")
            return text
    
    # ========== 語言設定管理 ==========
    
    async def set_user_language(self, user_id: int, guild_id: int, lang_code: str) -> bool:
        """設定用戶語言"""
        try:
            if lang_code not in self.supported_languages:
                return False
            
            # 這裡可以將用戶語言設定存儲到資料庫
            # 暫時先記錄日誌
            logger.info(f"用戶 {user_id} 在伺服器 {guild_id} 設定語言為: {lang_code}")
            return True
            
        except Exception as e:
            logger.error(f"設定用戶語言錯誤: {e}")
            return False
    
    async def get_user_language(self, user_id: int, guild_id: int) -> str:
        """獲取用戶語言設定"""
        try:
            # 這裡可以從資料庫獲取用戶語言設定
            # 暫時返回預設語言
            return self.default_language
            
        except Exception as e:
            logger.error(f"獲取用戶語言錯誤: {e}")
            return self.default_language
    
    async def set_guild_language(self, guild_id: int, lang_code: str) -> bool:
        """設定伺服器預設語言"""
        try:
            if lang_code not in self.supported_languages:
                return False
            
            # 這裡可以將伺服器語言設定存儲到資料庫
            logger.info(f"伺服器 {guild_id} 設定語言為: {lang_code}")
            return True
            
        except Exception as e:
            logger.error(f"設定伺服器語言錯誤: {e}")
            return False
    
    async def get_guild_language(self, guild_id: int) -> str:
        """獲取伺服器語言設定"""
        try:
            # 這裡可以從資料庫獲取伺服器語言設定
            return self.default_language
            
        except Exception as e:
            logger.error(f"獲取伺服器語言錯誤: {e}")
            return self.default_language
    
    # ========== 語言包定義 ==========
    
    def _get_zh_tw_pack(self) -> Dict[str, Any]:
        """繁體中文語言包"""
        return {
            "common": {
                "yes": "是",
                "no": "否",
                "cancel": "取消",
                "confirm": "確認",
                "success": "成功",
                "error": "錯誤",
                "warning": "警告",
                "info": "資訊",
                "loading": "載入中...",
                "processing": "處理中...",
                "completed": "已完成",
                "failed": "失敗",
                "language_set_success": "您的語言已設定為 **{language}**",
                "operation_failed": "操作執行失敗，請稍後再試",
                "set_at": "設定時間"
            },
            "language": {
                "your_setting": "您的語言設定",
                "current_language": "目前語言",
                "detection_type": "偵測方式", 
                "auto_detected": "自動偵測",
                "manually_set": "手動設定",
                "confidence": "置信度",
                "change_hint": "使用 /set_language 來變更語言",
                "no_setting": "未設定語言偏好",
                "using_default": "目前使用預設語言：**{default}**",
                "set_language_hint": "使用 /set_language 來設定您的語言偏好",
                "reset_success": "語言設定已重置，現在將使用預設語言",
                "now_using": "目前使用語言"
            },
            "commands": {
                "permission_denied": "❌ 您沒有權限使用此指令",
                "guild_only": "❌ 此指令只能在伺服器中使用",
                "invalid_arguments": "❌ 指令參數無效",
                "command_failed": "❌ 指令執行失敗：{error}",
                "command_success": "✅ 指令執行成功"
            },
            "ticket": {
                "created": "✅ 票券已建立",
                "closed": "✅ 票券已關閉",
                "not_found": "❌ 找不到票券",
                "permission_denied": "❌ 您沒有權限操作此票券",
                "already_exists": "❌ 您已經有開啟的票券了",
                "priority_updated": "✅ 優先級已更新為 {priority}",
                "assigned": "✅ 票券已指派給 {staff}",
                "tag_added": "✅ 已添加標籤：{tag}",
                "tag_removed": "✅ 已移除標籤：{tag}"
            },
            "welcome": {
                "title": "🎉 歡迎加入！",
                "message": "歡迎 {user} 加入 **{server}**！\\n\\n你是我們的第 **{count}** 位成員！",
                "dm_title": "👋 歡迎！",
                "dm_message": "歡迎加入 **{server}**！\\n\\n如有任何問題，請隨時建立票券。",
                "leave_message": "👋 **{user}** 離開了 **{server}**",
                "setup_complete": "✅ 歡迎系統設定完成",
                "system_enabled": "✅ 歡迎系統已啟用",
                "system_disabled": "❌ 歡迎系統已停用"
            },
            "vote": {
                "created": "✅ 投票已建立",
                "ended": "✅ 投票已結束",
                "not_found": "❌ 找不到投票",
                "already_voted": "❌ 您已經投過票了",
                "vote_recorded": "✅ 您的投票已記錄",
                "permission_denied": "❌ 您沒有權限參與此投票",
                "invalid_option": "❌ 無效的投票選項"
            },
            "ai": {
                "suggestion_generated": "✅ AI 建議已生成",
                "no_suggestions": "❌ 無法為此內容生成建議",
                "analysis_complete": "📊 內容分析完成",
                "confidence": "置信度：{confidence}",
                "suggestion_applied": "✅ 已應用 AI 建議",
                "feedback_recorded": "✅ 您的回饋已記錄",
                "priority_assessed": "🎯 優先級評估：{priority}",
                "tags_suggested": "🏷️ 建議標籤：{tags}"
            },
            "system": {
                "maintenance": "🔧 系統維護中，請稍後再試",
                "database_error": "❌ 資料庫錯誤，請聯繫管理員",
                "unexpected_error": "❌ 發生未預期的錯誤",
                "feature_disabled": "❌ 此功能目前已停用",
                "rate_limited": "❌ 操作過於頻繁，請稍後再試",
                "timeout": "⏰ 操作超時，請重試"
            }
        }
    
    def _get_en_pack(self) -> Dict[str, Any]:
        """英文語言包"""
        return {
            "common": {
                "yes": "Yes",
                "no": "No",
                "cancel": "Cancel",
                "confirm": "Confirm",
                "success": "Success",
                "error": "Error",
                "warning": "Warning",
                "info": "Information",
                "loading": "Loading...",
                "processing": "Processing...",
                "completed": "Completed",
                "failed": "Failed",
                "language_set_success": "Your language has been set to **{language}**",
                "operation_failed": "Operation failed, please try again later",
                "set_at": "Set at"
            },
            "language": {
                "your_setting": "Your Language Setting",
                "current_language": "Current Language",
                "detection_type": "Detection Type", 
                "auto_detected": "Auto-detected",
                "manually_set": "Manually set",
                "confidence": "Confidence",
                "change_hint": "Use /set_language to change your language",
                "no_setting": "No language preference set",
                "using_default": "Currently using default language: **{default}**",
                "set_language_hint": "Use /set_language to set your language preference",
                "reset_success": "Language setting has been reset, now using default language",
                "now_using": "Now using language"
            },
            "commands": {
                "permission_denied": "❌ You don't have permission to use this command",
                "guild_only": "❌ This command can only be used in a server",
                "invalid_arguments": "❌ Invalid command arguments",
                "command_failed": "❌ Command execution failed: {error}",
                "command_success": "✅ Command executed successfully"
            },
            "ticket": {
                "created": "✅ Ticket created",
                "closed": "✅ Ticket closed",
                "not_found": "❌ Ticket not found",
                "permission_denied": "❌ You don't have permission to operate this ticket",
                "already_exists": "❌ You already have an open ticket",
                "priority_updated": "✅ Priority updated to {priority}",
                "assigned": "✅ Ticket assigned to {staff}",
                "tag_added": "✅ Tag added: {tag}",
                "tag_removed": "✅ Tag removed: {tag}"
            },
            "welcome": {
                "title": "🎉 Welcome!",
                "message": "Welcome {user} to **{server}**!\\n\\nYou are our **{count}** member!",
                "dm_title": "👋 Welcome!",
                "dm_message": "Welcome to **{server}**!\\n\\nIf you have any questions, please feel free to create a ticket.",
                "leave_message": "👋 **{user}** left **{server}**",
                "setup_complete": "✅ Welcome system setup complete",
                "system_enabled": "✅ Welcome system enabled",
                "system_disabled": "❌ Welcome system disabled"
            },
            "vote": {
                "created": "✅ Vote created",
                "ended": "✅ Vote ended",
                "not_found": "❌ Vote not found",
                "already_voted": "❌ You have already voted",
                "vote_recorded": "✅ Your vote has been recorded",
                "permission_denied": "❌ You don't have permission to participate in this vote",
                "invalid_option": "❌ Invalid vote option"
            },
            "ai": {
                "suggestion_generated": "✅ AI suggestion generated",
                "no_suggestions": "❌ Unable to generate suggestions for this content",
                "analysis_complete": "📊 Content analysis complete",
                "confidence": "Confidence: {confidence}",
                "suggestion_applied": "✅ AI suggestion applied",
                "feedback_recorded": "✅ Your feedback has been recorded",
                "priority_assessed": "🎯 Priority assessment: {priority}",
                "tags_suggested": "🏷️ Suggested tags: {tags}"
            },
            "system": {
                "maintenance": "🔧 System under maintenance, please try again later",
                "database_error": "❌ Database error, please contact administrator",
                "unexpected_error": "❌ An unexpected error occurred",
                "feature_disabled": "❌ This feature is currently disabled",
                "rate_limited": "❌ Too many operations, please try again later",
                "timeout": "⏰ Operation timeout, please retry"
            }
        }
    
    def _get_zh_cn_pack(self) -> Dict[str, Any]:
        """简体中文语言包"""
        return {
            "common": {
                "yes": "是",
                "no": "否",
                "cancel": "取消",
                "confirm": "确认",
                "success": "成功",
                "error": "错误",
                "warning": "警告",
                "info": "信息",
                "loading": "加载中...",
                "processing": "处理中...",
                "completed": "已完成",
                "failed": "失败"
            },
            "commands": {
                "permission_denied": "❌ 您没有权限使用此命令",
                "guild_only": "❌ 此命令只能在服务器中使用",
                "invalid_arguments": "❌ 命令参数无效",
                "command_failed": "❌ 命令执行失败：{error}",
                "command_success": "✅ 命令执行成功"
            },
            "ticket": {
                "created": "✅ 工单已创建",
                "closed": "✅ 工单已关闭",
                "not_found": "❌ 找不到工单",
                "permission_denied": "❌ 您没有权限操作此工单",
                "already_exists": "❌ 您已经有开启的工单了",
                "priority_updated": "✅ 优先级已更新为 {priority}",
                "assigned": "✅ 工单已分配给 {staff}",
                "tag_added": "✅ 已添加标签：{tag}",
                "tag_removed": "✅ 已移除标签：{tag}"
            },
            "welcome": {
                "title": "🎉 欢迎加入！",
                "message": "欢迎 {user} 加入 **{server}**！\\n\\n你是我们的第 **{count}** 位成员！",
                "dm_title": "👋 欢迎！",
                "dm_message": "欢迎加入 **{server}**！\\n\\n如有任何问题，请随时创建工单。",
                "leave_message": "👋 **{user}** 离开了 **{server}**",
                "setup_complete": "✅ 欢迎系统设置完成",
                "system_enabled": "✅ 欢迎系统已启用",
                "system_disabled": "❌ 欢迎系统已停用"
            },
            "vote": {
                "created": "✅ 投票已创建",
                "ended": "✅ 投票已结束",
                "not_found": "❌ 找不到投票",
                "already_voted": "❌ 您已经投过票了",
                "vote_recorded": "✅ 您的投票已记录",
                "permission_denied": "❌ 您没有权限参与此投票",
                "invalid_option": "❌ 无效的投票选项"
            },
            "ai": {
                "suggestion_generated": "✅ AI 建议已生成",
                "no_suggestions": "❌ 无法为此内容生成建议",
                "analysis_complete": "📊 内容分析完成",
                "confidence": "置信度：{confidence}",
                "suggestion_applied": "✅ 已应用 AI 建议",
                "feedback_recorded": "✅ 您的反馈已记录",
                "priority_assessed": "🎯 优先级评估：{priority}",
                "tags_suggested": "🏷️ 建议标签：{tags}"
            },
            "system": {
                "maintenance": "🔧 系统维护中，请稍后再试",
                "database_error": "❌ 数据库错误，请联系管理员",
                "unexpected_error": "❌ 发生未预期的错误",
                "feature_disabled": "❌ 此功能目前已停用",
                "rate_limited": "❌ 操作过于频繁，请稍后再试",
                "timeout": "⏰ 操作超时，请重试"
            }
        }
    
    def _get_ja_pack(self) -> Dict[str, Any]:
        """日语语言包"""
        return {
            "common": {
                "yes": "はい",
                "no": "いいえ",
                "cancel": "キャンセル",
                "confirm": "確認",
                "success": "成功",
                "error": "エラー",
                "warning": "警告",
                "info": "情報",
                "loading": "読み込み中...",
                "processing": "処理中...",
                "completed": "完了",
                "failed": "失敗"
            },
            "commands": {
                "permission_denied": "❌ このコマンドを使用する権限がありません",
                "guild_only": "❌ このコマンドはサーバー内でのみ使用できます",
                "invalid_arguments": "❌ コマンドの引数が無効です",
                "command_failed": "❌ コマンド実行に失敗しました：{error}",
                "command_success": "✅ コマンドが正常に実行されました"
            },
            "ticket": {
                "created": "✅ チケットが作成されました",
                "closed": "✅ チケットが閉じられました",
                "not_found": "❌ チケットが見つかりません",
                "permission_denied": "❌ このチケットを操作する権限がありません",
                "already_exists": "❌ 既に開いているチケットがあります",
                "priority_updated": "✅ 優先度が{priority}に更新されました",
                "assigned": "✅ チケットが{staff}に割り当てられました",
                "tag_added": "✅ タグを追加しました：{tag}",
                "tag_removed": "✅ タグを削除しました：{tag}"
            },
            "welcome": {
                "title": "🎉 ようこそ！",
                "message": "{user}さん、**{server}**へようこそ！\\n\\nあなたは**{count}**番目のメンバーです！",
                "dm_title": "👋 ようこそ！",
                "dm_message": "**{server}**へようこそ！\\n\\nご質問がございましたら、お気軽にチケットを作成してください。",
                "leave_message": "👋 **{user}**さんが**{server}**を退出しました",
                "setup_complete": "✅ ウェルカムシステムの設定が完了しました",
                "system_enabled": "✅ ウェルカムシステムが有効になりました",
                "system_disabled": "❌ ウェルカムシステムが無効になりました"
            },
            "vote": {
                "created": "✅ 投票が作成されました",
                "ended": "✅ 投票が終了しました",
                "not_found": "❌ 投票が見つかりません",
                "already_voted": "❌ 既に投票済みです",
                "vote_recorded": "✅ あなたの投票が記録されました",
                "permission_denied": "❌ この投票に参加する権限がありません",
                "invalid_option": "❌ 無効な投票選択肢です"
            },
            "ai": {
                "suggestion_generated": "✅ AI提案が生成されました",
                "no_suggestions": "❌ このコンテンツの提案を生成できません",
                "analysis_complete": "📊 コンテンツ分析完了",
                "confidence": "信頼度：{confidence}",
                "suggestion_applied": "✅ AI提案が適用されました",
                "feedback_recorded": "✅ フィードバックが記録されました",
                "priority_assessed": "🎯 優先度評価：{priority}",
                "tags_suggested": "🏷️ 提案タグ：{tags}"
            },
            "system": {
                "maintenance": "🔧 システムメンテナンス中です。後でもう一度お試しください",
                "database_error": "❌ データベースエラーが発生しました。管理者にお問い合わせください",
                "unexpected_error": "❌ 予期しないエラーが発生しました",
                "feature_disabled": "❌ この機能は現在無効になっています",
                "rate_limited": "❌ 操作が頻繁すぎます。後でもう一度お試しください",
                "timeout": "⏰ 操作がタイムアウトしました。再試行してください"
            }
        }
    
    def _get_ko_pack(self) -> Dict[str, Any]:
        """韩语语言包"""
        return {
            "common": {
                "yes": "예",
                "no": "아니오",
                "cancel": "취소",
                "confirm": "확인",
                "success": "성공",
                "error": "오류",
                "warning": "경고",
                "info": "정보",
                "loading": "로딩 중...",
                "processing": "처리 중...",
                "completed": "완료",
                "failed": "실패"
            },
            "commands": {
                "permission_denied": "❌ 이 명령어를 사용할 권한이 없습니다",
                "guild_only": "❌ 이 명령어는 서버에서만 사용할 수 있습니다",
                "invalid_arguments": "❌ 명령어 인수가 잘못되었습니다",
                "command_failed": "❌ 명령어 실행에 실패했습니다: {error}",
                "command_success": "✅ 명령어가 성공적으로 실행되었습니다"
            },
            "ticket": {
                "created": "✅ 티켓이 생성되었습니다",
                "closed": "✅ 티켓이 닫혔습니다",
                "not_found": "❌ 티켓을 찾을 수 없습니다",
                "permission_denied": "❌ 이 티켓을 조작할 권한이 없습니다",
                "already_exists": "❌ 이미 열린 티켓이 있습니다",
                "priority_updated": "✅ 우선순위가 {priority}로 업데이트되었습니다",
                "assigned": "✅ 티켓이 {staff}에게 할당되었습니다",
                "tag_added": "✅ 태그를 추가했습니다: {tag}",
                "tag_removed": "✅ 태그를 제거했습니다: {tag}"
            },
            "welcome": {
                "title": "🎉 환영합니다!",
                "message": "{user}님, **{server}**에 오신 것을 환영합니다!\\n\\n당신은 우리의 **{count}**번째 멤버입니다!",
                "dm_title": "👋 환영합니다!",
                "dm_message": "**{server}**에 오신 것을 환영합니다!\\n\\n궁금한 점이 있으시면 언제든지 티켓을 생성해 주세요.",
                "leave_message": "👋 **{user}**님이 **{server}**를 떠났습니다",
                "setup_complete": "✅ 환영 시스템 설정이 완료되었습니다",
                "system_enabled": "✅ 환영 시스템이 활성화되었습니다",
                "system_disabled": "❌ 환영 시스템이 비활성화되었습니다"
            },
            "vote": {
                "created": "✅ 투표가 생성되었습니다",
                "ended": "✅ 투표가 종료되었습니다",
                "not_found": "❌ 투표를 찾을 수 없습니다",
                "already_voted": "❌ 이미 투표하셨습니다",
                "vote_recorded": "✅ 투표가 기록되었습니다",
                "permission_denied": "❌ 이 투표에 참여할 권한이 없습니다",
                "invalid_option": "❌ 잘못된 투표 선택지입니다"
            },
            "ai": {
                "suggestion_generated": "✅ AI 제안이 생성되었습니다",
                "no_suggestions": "❌ 이 콘텐츠에 대한 제안을 생성할 수 없습니다",
                "analysis_complete": "📊 콘텐츠 분석 완료",
                "confidence": "신뢰도: {confidence}",
                "suggestion_applied": "✅ AI 제안이 적용되었습니다",
                "feedback_recorded": "✅ 피드백이 기록되었습니다",
                "priority_assessed": "🎯 우선순위 평가: {priority}",
                "tags_suggested": "🏷️ 제안 태그: {tags}"
            },
            "system": {
                "maintenance": "🔧 시스템 점검 중입니다. 나중에 다시 시도해 주세요",
                "database_error": "❌ 데이터베이스 오류가 발생했습니다. 관리자에게 문의하세요",
                "unexpected_error": "❌ 예상치 못한 오류가 발생했습니다",
                "feature_disabled": "❌ 이 기능은 현재 비활성화되어 있습니다",
                "rate_limited": "❌ 너무 많은 작업을 수행했습니다. 나중에 다시 시도해 주세요",
                "timeout": "⏰ 작업 시간이 초과되었습니다. 다시 시도해 주세요"
            }
        }
    
    # ========== 實用方法 ==========
    
    def get_supported_languages(self) -> Dict[str, str]:
        """獲取支援的語言列表"""
        return self.supported_languages.copy()
    
    def is_supported_language(self, lang_code: str) -> bool:
        """檢查是否支援指定語言"""
        return lang_code in self.supported_languages
    
    def get_language_name(self, lang_code: str) -> str:
        """獲取語言名稱"""
        return self.supported_languages.get(lang_code, lang_code)
    
    def format_message(self, template_key: str, lang_code: str = None, **kwargs) -> str:
        """格式化訊息"""
        return self.get_string(template_key, lang_code, **kwargs)