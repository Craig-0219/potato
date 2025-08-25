# bot/services/webhook_manager.py - Webhook整合系統 v1.7.0
"""
Webhook整合系統
提供自定義Webhook、事件通知、第三方服務整合等功能
"""

import asyncio
import json
import hmac
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

from bot.db.webhook_dao import WebhookDAO
from shared.logger import logger

class WebhookType(Enum):
    """Webhook類型"""
    INCOMING = "incoming"      # 接收Webhook
    OUTGOING = "outgoing"      # 發送Webhook
    BIDIRECTIONAL = "both"     # 雙向Webhook

class WebhookEvent(Enum):
    """Webhook事件類型"""
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_CLOSED = "ticket_closed"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    VOTE_CREATED = "vote_created"
    VOTE_COMPLETED = "vote_completed"
    SYSTEM_ALERT = "system_alert"
    CUSTOM_EVENT = "custom_event"

class WebhookStatus(Enum):
    """Webhook狀態"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class WebhookConfig:
    """Webhook配置"""
    id: str
    name: str
    url: str
    type: WebhookType
    events: List[WebhookEvent]
    secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3
    retry_interval: int = 5
    status: WebhookStatus = WebhookStatus.ACTIVE
    guild_id: int = 0
    created_by: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_triggered: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0

@dataclass
class WebhookPayload:
    """Webhook負載"""
    event: WebhookEvent
    timestamp: datetime
    guild_id: int
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WebhookResponse:
    """Webhook回應"""
    success: bool
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0

class WebhookManager:
    """Webhook整合管理器"""
    
    def __init__(self):
        self.webhook_dao = WebhookDAO()
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_handlers: Dict[WebhookEvent, List[str]] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 執行統計
        self.execution_stats = {
            'total_sent': 0,
            'total_received': 0,
            'success_count': 0,
            'failure_count': 0,
            'last_reset': datetime.now(timezone.utc)
        }
        
        logger.info("✅ Webhook管理器已初始化")
    
    async def initialize(self):
        """初始化Webhook系統"""
        try:
            # 創建HTTP會話
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                connector=aiohttp.TCPConnector(limit=100)
            )
            
            # 從資料庫載入Webhook配置
            await self._load_webhooks_from_database()
            
            logger.info("✅ Webhook系統初始化完成")
            
        except Exception as e:
            logger.error(f"❌ Webhook系統初始化失敗: {e}")
            raise
    
    async def shutdown(self):
        """關閉Webhook系統"""
        try:
            if self.session:
                await self.session.close()
            logger.info("✅ Webhook系統已關閉")
        except Exception as e:
            logger.error(f"❌ Webhook系統關閉失敗: {e}")
    
    # ========== Webhook配置管理 ==========
    
    async def create_webhook(self, config_data: Dict[str, Any]) -> str:
        """創建Webhook"""
        try:
            # 生成Webhook ID和密鑰
            webhook_id = secrets.token_urlsafe(16)
            secret = secrets.token_urlsafe(32) if config_data.get('use_secret', True) else None
            
            # 創建配置
            config = WebhookConfig(
                id=webhook_id,
                name=config_data['name'],
                url=config_data['url'],
                type=WebhookType(config_data.get('type', 'outgoing')),
                events=[WebhookEvent(event) for event in config_data.get('events', [])],
                secret=secret,
                headers=config_data.get('headers', {}),
                timeout=config_data.get('timeout', 30),
                retry_count=config_data.get('retry_count', 3),
                retry_interval=config_data.get('retry_interval', 5),
                guild_id=config_data.get('guild_id', 0),
                created_by=config_data.get('created_by', 0)
            )
            
            # 保存到記憶體和資料庫
            self.webhooks[webhook_id] = config
            await self.webhook_dao.create_webhook(config)
            
            # 註冊事件處理器
            self._register_webhook_events(config)
            
            logger.info(f"✅ Webhook已創建: {config.name} (ID: {webhook_id})")
            return webhook_id
            
        except Exception as e:
            logger.error(f"❌ 創建Webhook失敗: {e}")
            raise
    
    async def update_webhook(self, webhook_id: str, updates: Dict[str, Any]) -> bool:
        """更新Webhook配置"""
        try:
            if webhook_id not in self.webhooks:
                raise ValueError(f"Webhook不存在: {webhook_id}")
            
            config = self.webhooks[webhook_id]
            
            # 取消註冊舊事件
            self._unregister_webhook_events(webhook_id)
            
            # 更新配置
            if 'name' in updates:
                config.name = updates['name']
            if 'url' in updates:
                config.url = updates['url']
            if 'events' in updates:
                config.events = [WebhookEvent(event) for event in updates['events']]
            if 'headers' in updates:
                config.headers = updates['headers']
            if 'timeout' in updates:
                config.timeout = updates['timeout']
            if 'status' in updates:
                config.status = WebhookStatus(updates['status'])
            
            # 保存到資料庫
            await self.webhook_dao.update_webhook(webhook_id, updates)
            
            # 重新註冊事件
            self._register_webhook_events(config)
            
            logger.info(f"✅ Webhook已更新: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新Webhook失敗: {e}")
            return False
    
    async def delete_webhook(self, webhook_id: str) -> bool:
        """刪除Webhook"""
        try:
            if webhook_id not in self.webhooks:
                return False
            
            config = self.webhooks[webhook_id]
            
            # 取消註冊事件
            self._unregister_webhook_events(webhook_id)
            
            # 從記憶體和資料庫中刪除
            del self.webhooks[webhook_id]
            await self.webhook_dao.delete_webhook(webhook_id)
            
            logger.info(f"✅ Webhook已刪除: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 刪除Webhook失敗: {e}")
            return False
    
    # ========== 事件觸發 ==========
    
    async def trigger_webhook_event(self, event: WebhookEvent, guild_id: int, data: Dict[str, Any]):
        """觸發Webhook事件"""
        try:
            # 找到匹配的Webhook
            matching_webhooks = []
            
            for webhook_id, config in self.webhooks.items():
                if (config.guild_id == guild_id and 
                    event in config.events and 
                    config.status == WebhookStatus.ACTIVE and
                    config.type in [WebhookType.OUTGOING, WebhookType.BIDIRECTIONAL]):
                    matching_webhooks.append(config)
            
            if not matching_webhooks:

            error_msg = str(e)
            logger.error(f"❌ Webhook發送失敗 ({config.name}): {error_msg}")
            
            return WebhookResponse(
                success=False,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    # ========== 接收Webhook ==========
    
    async def process_incoming_webhook(self, webhook_id: str, payload: Dict[str, Any], 
                                     signature: Optional[str] = None) -> Dict[str, Any]:
        """處理接收的Webhook"""
        try:
            if webhook_id not in self.webhooks:
                raise ValueError(f"Webhook不存在: {webhook_id}")
            
            config = self.webhooks[webhook_id]
            
            # 檢查Webhook類型
            if config.type not in [WebhookType.INCOMING, WebhookType.BIDIRECTIONAL]:
                raise ValueError("此Webhook不接受入站請求")
            
            # 檢查狀態
            if config.status != WebhookStatus.ACTIVE:
                raise ValueError("Webhook已停用")
            
            # 驗證簽名
            if config.secret and signature:
                expected_signature = self._generate_signature(json.dumps(payload), config.secret)
                if not hmac.compare_digest(signature.replace('sha256=', ''), expected_signature):
                    raise ValueError("簽名驗證失敗")
            
            # 處理事件
            event_type = payload.get('event')
            if event_type:
                try:
                    event = WebhookEvent(event_type)
                    await self._process_webhook_event(config, event, payload)
                except ValueError:
                    logger.warning(f"⚠️ 未知的Webhook事件類型: {event_type}")
            
            # 更新統計
            config.last_triggered = datetime.now(timezone.utc)
            config.success_count += 1
            self.execution_stats['total_received'] += 1
            self.execution_stats['success_count'] += 1
            
            return {'status': 'success', 'message': 'Webhook processed successfully'}
            
        except Exception as e:
            logger.error(f"❌ 處理接收Webhook失敗: {e}")
            self.execution_stats['total_received'] += 1
            self.execution_stats['failure_count'] += 1
            
            return {'status': 'error', 'message': str(e)}
    
    async def _process_webhook_event(self, config: WebhookConfig, event: WebhookEvent, payload: Dict[str, Any]):
        """處理Webhook事件"""
        try:
            # 這裡可以根據不同的事件類型執行不同的處理邏輯
            logger.info(f"🔗 處理Webhook事件: {event.value} from {config.name}")
            
            # 觸發相應的系統事件
            if event == WebhookEvent.TICKET_CREATED:
                # 可以觸發工作流程或其他系統功能
                pass
            elif event == WebhookEvent.SYSTEM_ALERT:
                # 可以發送通知或執行緊急處理
                pass
            # 可以添加更多事件處理邏輯
            
        except Exception as e:
            logger.error(f"❌ 處理Webhook事件失敗: {e}")
    
    # ========== 輔助方法 ==========
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """生成Webhook簽名"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _register_webhook_events(self, config: WebhookConfig):
        """註冊Webhook事件處理器"""
        for event in config.events:
            if event not in self.event_handlers:
                self.event_handlers[event] = []
            
            if config.id not in self.event_handlers[event]:
                self.event_handlers[event].append(config.id)
    
    def _unregister_webhook_events(self, webhook_id: str):
        """取消註冊Webhook事件處理器"""
        for event, webhook_ids in self.event_handlers.items():
            if webhook_id in webhook_ids:
                webhook_ids.remove(webhook_id)
    
    async def _load_webhooks_from_database(self):
        """從資料庫載入Webhook配置"""
        try:
            webhooks = await self.webhook_dao.get_all_webhooks()
            
            for webhook_data in webhooks:
                config = WebhookConfig(
                    id=webhook_data['id'],
                    name=webhook_data['name'],
                    url=webhook_data['url'],
                    type=WebhookType(webhook_data['type']),
                    events=[WebhookEvent(event) for event in webhook_data['events']],
                    secret=webhook_data.get('secret'),
                    headers=webhook_data.get('headers', {}),
                    timeout=webhook_data.get('timeout', 30),
                    retry_count=webhook_data.get('retry_count', 3),
                    retry_interval=webhook_data.get('retry_interval', 5),
                    status=WebhookStatus(webhook_data.get('status', 'active')),
                    guild_id=webhook_data.get('guild_id', 0),
                    created_by=webhook_data.get('created_by', 0),
                    success_count=webhook_data.get('success_count', 0),
                    failure_count=webhook_data.get('failure_count', 0)
                )
                
                self.webhooks[config.id] = config
                self._register_webhook_events(config)
            
            logger.info(f"✅ 已載入 {len(webhooks)} 個Webhook配置")
            
        except Exception as e:
            logger.error(f"❌ 載入Webhook配置失敗: {e}")
    
    # ========== 統計和查詢 ==========
    
    def get_webhooks(self, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """獲取Webhook列表"""
        webhooks = []
        
        for config in self.webhooks.values():
            if guild_id is None or config.guild_id == guild_id:
                webhooks.append({
                    'id': config.id,
                    'name': config.name,
                    'url': config.url,
                    'type': config.type.value,
                    'events': [event.value for event in config.events],
                    'status': config.status.value,
                    'success_count': config.success_count,
                    'failure_count': config.failure_count,
                    'last_triggered': config.last_triggered.isoformat() if config.last_triggered else None,
                    'created_at': config.created_at.isoformat()
                })
        
        return webhooks
    
    def get_webhook_statistics(self) -> Dict[str, Any]:
        """獲取Webhook統計信息"""
        active_webhooks = sum(1 for config in self.webhooks.values() if config.status == WebhookStatus.ACTIVE)
        
        return {
            'total_webhooks': len(self.webhooks),
            'active_webhooks': active_webhooks,
            'total_sent': self.execution_stats['total_sent'],
            'total_received': self.execution_stats['total_received'],
            'success_count': self.execution_stats['success_count'],
            'failure_count': self.execution_stats['failure_count'],
            'success_rate': (self.execution_stats['success_count'] / 
                           max(self.execution_stats['total_sent'] + self.execution_stats['total_received'], 1)) * 100,
            'event_distribution': self._get_event_distribution()
        }
    
    def _get_event_distribution(self) -> Dict[str, int]:
        """獲取事件分佈統計"""
        event_count = {}
        
        for config in self.webhooks.values():
            for event in config.events:
                event_count[event.value] = event_count.get(event.value, 0) + 1
        
        return event_count

# 全域Webhook管理器實例
webhook_manager = WebhookManager()