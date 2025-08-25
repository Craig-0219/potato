# bot/services/security_audit_manager.py - 企業級安全審計管理器 v1.7.0
"""
企業級安全審計管理器
提供全面的安全監控、審計日誌、權限管理和合規報告功能
"""

import asyncio
import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import ipaddress
from cryptography.fernet import Fernet
import re

from shared.logger import logger

class SecurityEventType(Enum):
    """安全事件類型"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure" 
    PERMISSION_DENIED = "permission_denied"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_CONFIGURATION = "system_configuration"
    USER_MANAGEMENT = "user_management"
    ROLE_ASSIGNMENT = "role_assignment"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"
    COMMAND_EXECUTION = "command_execution"
    FILE_ACCESS = "file_access"
    DATABASE_QUERY = "database_query"
    API_CALL = "api_call"

class RiskLevel(Enum):
    """風險等級"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditAction(Enum):
    """審計動作類型"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ACCESS = "access"
    EXPORT = "export"
    IMPORT = "import"

class ComplianceStandard(Enum):
    """合規標準"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    ISO27001 = "iso27001"
    PCI_DSS = "pci_dss"

@dataclass
class SecurityEvent:
    """安全事件數據類"""
    id: str
    event_type: SecurityEventType
    timestamp: datetime
    user_id: int
    guild_id: Optional[int]
    risk_level: RiskLevel
    action: AuditAction
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None

@dataclass
class SecurityRule:
    """安全規則數據類"""
    id: str
    name: str
    description: str
    rule_type: str
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    enabled: bool
    severity: RiskLevel
    created_at: datetime
    created_by: int

@dataclass
class ComplianceReport:
    """合規報告數據類"""
    id: str
    standard: ComplianceStandard
    period_start: datetime
    period_end: datetime
    guild_id: int
    generated_by: int
    generated_at: datetime
    summary: Dict[str, Any]
    violations: List[Dict[str, Any]]
    recommendations: List[str]

class SecurityAuditManager:
    """企業級安全審計管理器"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.security_rules: Dict[str, SecurityRule] = {}
        self.event_buffer: List[SecurityEvent] = []
        self.encryption_key = self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        self.suspicious_activity_cache: Dict[str, List[datetime]] = {}
        self.rate_limits: Dict[str, Dict[str, datetime]] = {}
        
        # 預設安全規則
        self._initialize_default_rules()
        logger.info("✅ 企業級安全審計管理器已初始化")
    
    def _generate_encryption_key(self) -> bytes:
        """生成加密密鑰"""
        # 在生產環境中，這應該從安全的密鑰管理服務獲取
        return Fernet.generate_key()
    
    def _initialize_default_rules(self):
        """初始化預設安全規則"""
        default_rules = [
            {
                'id': 'failed_login_detection',
                'name': '登入失敗檢測',
                'description': '檢測連續登入失敗嘗試',
                'rule_type': 'threshold',
                'conditions': {
                    'event_type': 'login_failure',
                    'threshold': 5,
                    'time_window': 300,  # 5分鐘
                },
                'actions': [
                    {'type': 'alert', 'severity': 'high'},
                    {'type': 'temporary_ban', 'duration': 1800}  # 30分鐘
                ],
                'severity': RiskLevel.HIGH
            },
            {
                'id': 'privilege_escalation_detection',
                'name': '權限提升檢測',
                'description': '檢測異常權限變更',
                'rule_type': 'anomaly',
                'conditions': {
                    'event_type': 'role_assignment',
                    'check_elevation': True
                },
                'actions': [
                    {'type': 'alert', 'severity': 'critical'},
                    {'type': 'require_approval'}
                ],
                'severity': RiskLevel.CRITICAL
            },
            {
                'id': 'data_export_monitoring',
                'name': '資料匯出監控',
                'description': '監控大量資料匯出活動',
                'rule_type': 'volume',
                'conditions': {
                    'action': 'export',
                    'volume_threshold': 1000,
                    'time_window': 3600
                },
                'actions': [
                    {'type': 'alert', 'severity': 'medium'},
                    {'type': 'log_detail'}
                ],
                'severity': RiskLevel.MEDIUM
            }
        ]
        
        for rule_data in default_rules:
            rule = SecurityRule(
                id=rule_data['id'],
                name=rule_data['name'],
                description=rule_data['description'],
                rule_type=rule_data['rule_type'],
                conditions=rule_data['conditions'],
                actions=rule_data['actions'],
                enabled=True,
                severity=rule_data['severity'],
                created_at=datetime.now(timezone.utc),
                created_by=0
            )
            self.security_rules[rule.id] = rule
    
    # ========== 核心安全事件記錄 ==========
    
    async def log_security_event(
        self,
        event_type: SecurityEventType,
        user_id: int,
        action: AuditAction,
        resource: str,
        details: Dict[str, Any],
        guild_id: Optional[int] = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        """記錄安全事件"""
        try:
            event_id = str(uuid.uuid4())
            
            # 創建安全事件
            event = SecurityEvent(
                id=event_id,
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                guild_id=guild_id,
                risk_level=risk_level,
                action=action,
                resource=resource,
                details=self._sanitize_sensitive_data(details),
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=self._get_session_id(user_id),
                correlation_id=correlation_id
            )
            
            # 加密敏感數據
            if self._contains_sensitive_data(details):
                event.details = self._encrypt_data(event.details)
            
            # 添加到事件緩衝區
            self.event_buffer.append(event)
            
            # 檢查安全規則
            await self._evaluate_security_rules(event)
            
            # 檢測可疑活動
            await self._detect_suspicious_activity(event)
            
            # 定期持久化到資料庫
            if len(self.event_buffer) >= 100:
                await self._flush_event_buffer()
            
            logger.info(f"✅ 安全事件已記錄: {event_type.value} by {user_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"記錄安全事件失敗: {e}")
            return ""
    
    async def log_command_execution(
        self,
        user_id: int,
        guild_id: int,
        command_name: str,
        parameters: Dict[str, Any],
        success: bool,
        execution_time: float,
        ip_address: Optional[str] = None
    ):
        """記錄指令執行"""
        risk_level = RiskLevel.LOW
        event_type = SecurityEventType.COMMAND_EXECUTION
        
        # 評估指令風險等級
        if command_name in ['ban', 'kick', 'mute', 'delete_channel']:
            risk_level = RiskLevel.HIGH
        elif command_name in ['role_assign', 'permission_change']:
            risk_level = RiskLevel.CRITICAL
        
        details = {
            'command': command_name,
            'parameters': parameters,
            'success': success,
            'execution_time': execution_time,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        await self.log_security_event(
            event_type=event_type,
            user_id=user_id,
            guild_id=guild_id,
            action=AuditAction.EXECUTE,
            resource=f"command:{command_name}",
            details=details,
            risk_level=risk_level,
            ip_address=ip_address
        )
    
    async def log_data_access(
        self,
        user_id: int,
        guild_id: int,
        table_name: str,
        operation: str,
        record_count: int,
        filters: Dict[str, Any] = None
    ):
        """記錄資料存取"""
        risk_level = RiskLevel.LOW
        if record_count > 1000:
            risk_level = RiskLevel.MEDIUM
        elif operation in ['DELETE', 'UPDATE'] and record_count > 100:
            risk_level = RiskLevel.HIGH
        
        details = {
            'table': table_name,
            'operation': operation,
            'record_count': record_count,
            'filters': filters or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        await self.log_security_event(
            event_type=SecurityEventType.DATA_ACCESS,
            user_id=user_id,
            guild_id=guild_id,
            action=AuditAction(operation.lower()) if operation.lower() in [a.value for a in AuditAction] else AuditAction.ACCESS,
            resource=f"database:{table_name}",
            details=details,
            risk_level=risk_level
        )
    
    # ========== 可疑活動檢測 ==========
    
    async def _detect_suspicious_activity(self, event: SecurityEvent):
        """檢測可疑活動"""
        user_key = f"{event.user_id}_{event.guild_id or 0}"
        
        # 初始化用戶活動記錄
        if user_key not in self.suspicious_activity_cache:
            self.suspicious_activity_cache[user_key] = []
        
        # 添加當前事件時間
        self.suspicious_activity_cache[user_key].append(event.timestamp)
        
        # 保持最近1小時的記錄
        cutoff_time = event.timestamp - timedelta(hours=1)
        self.suspicious_activity_cache[user_key] = [
            t for t in self.suspicious_activity_cache[user_key] 
            if t > cutoff_time
        ]
        
        # 檢測異常頻率
        recent_events = len(self.suspicious_activity_cache[user_key])
        
        if recent_events > 50:  # 1小時內超過50個事件
            await self._handle_suspicious_activity(
                event.user_id,
                event.guild_id,
                "異常高頻操作",
                {"events_per_hour": recent_events}
            )
        
        # 檢測異常時間模式
        if self._is_unusual_time(event.timestamp):
            await self._handle_suspicious_activity(
                event.user_id,
                event.guild_id,
                "異常時間操作",
                {"timestamp": event.timestamp.isoformat()}
            )
        
        # 檢測IP地址異常
        if event.ip_address and await self._is_suspicious_ip(event.ip_address):
            await self._handle_suspicious_activity(
                event.user_id,
                event.guild_id,
                "可疑IP地址",
                {"ip_address": event.ip_address}
            )
    
    def _is_unusual_time(self, timestamp: datetime) -> bool:
        """檢查是否為異常時間（例如深夜）"""
        hour = timestamp.hour
        return hour < 6 or hour > 23  # 凌晨6點前或晚上11點後
    
    async def _is_suspicious_ip(self, ip_address: str) -> bool:
        """檢查IP地址是否可疑"""
        try:
            ip = ipaddress.ip_address(ip_address)
            
            # 檢查是否為已知的惡意IP範圍
            # 這裡可以整合第三方威脅情報服務
            
            # 檢查是否為Tor出口節點或VPN
            suspicious_ranges = [
                ipaddress.ip_network('10.0.0.0/8'),      # 私有網路
                ipaddress.ip_network('172.16.0.0/12'),   # 私有網路
                ipaddress.ip_network('192.168.0.0/16'),  # 私有網路
            ]
            
            # 如果是私有IP但來自外部，可能是偽造的
            for network in suspicious_ranges:
                if ip in network:
                    return True
            
            return False
            
        except ValueError:
            return True  # 無效IP地址本身就可疑
    
    async def _handle_suspicious_activity(
        self,
        user_id: int,
        guild_id: Optional[int],
        activity_type: str,
        details: Dict[str, Any]
    ):
        """處理可疑活動"""
        await self.log_security_event(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            user_id=user_id,
            guild_id=guild_id,
            action=AuditAction.ACCESS,
            resource="system",
            details={
                "activity_type": activity_type,
                "details": details,
                "detected_at": datetime.now(timezone.utc).isoformat()
            },
            risk_level=RiskLevel.HIGH
        )
        
        # 可以在這裡添加自動響應措施
        logger.warning(f"🚨 檢測到可疑活動: {activity_type} by user {user_id}")
    
    # ========== 安全規則評估 ==========
    
    async def _evaluate_security_rules(self, event: SecurityEvent):
        """評估安全規則"""
        for rule_id, rule in self.security_rules.items():
            if not rule.enabled:
                continue
            
            try:
                if await self._rule_matches_event(rule, event):
                    await self._execute_rule_actions(rule, event)
            except Exception as e:
                logger.error(f"評估安全規則失敗 {rule_id}: {e}")
    
    async def _rule_matches_event(self, rule: SecurityRule, event: SecurityEvent) -> bool:
        """檢查規則是否匹配事件"""
        conditions = rule.conditions
        
        # 檢查事件類型
        if 'event_type' in conditions:
            if event.event_type.value != conditions['event_type']:
                return False
        
        # 檢查動作類型
        if 'action' in conditions:
            if event.action.value != conditions['action']:
                return False
        
        # 檢查閾值規則
        if rule.rule_type == 'threshold':
            return await self._evaluate_threshold_rule(conditions, event)
        
        # 檢查異常規則
        elif rule.rule_type == 'anomaly':
            return await self._evaluate_anomaly_rule(conditions, event)
        
        # 檢查數量規則
        elif rule.rule_type == 'volume':
            return await self._evaluate_volume_rule(conditions, event)
        
        return True
    
    async def _evaluate_threshold_rule(self, conditions: Dict[str, Any], event: SecurityEvent) -> bool:
        """評估閾值規則"""
        threshold = conditions.get('threshold', 5)
        time_window = conditions.get('time_window', 300)  # 秒
        
        # 計算在時間窗口內的相同事件數量
        cutoff_time = event.timestamp - timedelta(seconds=time_window)
        
        matching_events = [
            e for e in self.event_buffer
            if (e.event_type == event.event_type and
                e.user_id == event.user_id and
                e.timestamp > cutoff_time)
        ]
        
        return len(matching_events) >= threshold
    
    async def _evaluate_anomaly_rule(self, conditions: Dict[str, Any], event: SecurityEvent) -> bool:
        """評估異常規則"""
        if conditions.get('check_elevation') and event.event_type == SecurityEventType.ROLE_ASSIGNMENT:
            # 檢查是否為權限提升
            details = event.details
            old_roles = details.get('old_roles', [])
            new_roles = details.get('new_roles', [])
            
            # 簡單檢查：如果新角色數量大於舊角色，可能是提升
            return len(new_roles) > len(old_roles)
        
        return False
    
    async def _evaluate_volume_rule(self, conditions: Dict[str, Any], event: SecurityEvent) -> bool:
        """評估數量規則"""
        volume_threshold = conditions.get('volume_threshold', 1000)
        time_window = conditions.get('time_window', 3600)
        
        if event.action.value != conditions.get('action'):
            return False
        
        # 計算時間窗口內的操作總量
        cutoff_time = event.timestamp - timedelta(seconds=time_window)
        
        total_volume = sum(
            e.details.get('record_count', 1) for e in self.event_buffer
            if (e.action == event.action and
                e.user_id == event.user_id and
                e.timestamp > cutoff_time)
        )
        
        return total_volume >= volume_threshold
    
    async def _execute_rule_actions(self, rule: SecurityRule, event: SecurityEvent):
        """執行規則動作"""
        for action in rule.actions:
            action_type = action.get('type')
            
            try:
                if action_type == 'alert':
                    await self._send_security_alert(rule, event, action)
                elif action_type == 'temporary_ban':
                    await self._apply_temporary_restriction(event.user_id, action)
                elif action_type == 'require_approval':
                    await self._require_approval(event, action)
                elif action_type == 'log_detail':
                    await self._log_detailed_information(event, action)
                
            except Exception as e:
                logger.error(f"執行安全規則動作失敗 {action_type}: {e}")
    
    async def _send_security_alert(self, rule: SecurityRule, event: SecurityEvent, action: Dict[str, Any]):
        """發送安全警報"""
        severity = action.get('severity', 'medium')
        
        alert_details = {
            'rule_name': rule.name,
            'rule_id': rule.id,
            'event_id': event.id,
            'severity': severity,
            'user_id': event.user_id,
            'event_type': event.event_type.value,
            'timestamp': event.timestamp.isoformat(),
            'resource': event.resource
        }
        
        logger.warning(f"🚨 安全警報: {rule.name} - {severity.upper()}")
        # 這裡可以整合外部警報系統
    
    async def _apply_temporary_restriction(self, user_id: int, action: Dict[str, Any]):
        """應用臨時限制"""
        duration = action.get('duration', 1800)  # 預設30分鐘
        restriction_end = datetime.now(timezone.utc) + timedelta(seconds=duration)
        
        # 記錄限制
        logger.info(f"⚠️ 對用戶 {user_id} 應用臨時限制，持續 {duration} 秒")
        # 實際限制邏輯需要與Bot的權限系統整合
    
    async def _require_approval(self, event: SecurityEvent, action: Dict[str, Any]):
        """要求審批"""
        # 將事件標記為需要審批
        logger.info(f"📋 事件 {event.id} 需要管理員審批")
        # 可以發送通知給管理員
    
    async def _log_detailed_information(self, event: SecurityEvent, action: Dict[str, Any]):
        """記錄詳細資訊"""
        detailed_info = {
            'event_id': event.id,
            'detailed_context': {
                'session_id': event.session_id,
                'correlation_id': event.correlation_id,
                'user_agent': event.user_agent,
                'ip_address': event.ip_address
            }
        }
        
        logger.info(f"📝 詳細記錄事件 {event.id}")
    
    # ========== 數據處理和加密 ==========
    
    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理敏感數據"""
        sensitive_patterns = [
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # 信用卡號
            r'\b\d{3}-\d{2}-\d{4}\b',                        # SSN
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email (部分)
        ]
        
        sanitized_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized_value = value
                for pattern in sensitive_patterns:
                    sanitized_value = re.sub(pattern, '[REDACTED]', sanitized_value)
                sanitized_data[key] = sanitized_value
            else:
                sanitized_data[key] = value
        
        return sanitized_data
    
    def _contains_sensitive_data(self, data: Dict[str, Any]) -> bool:
        """檢查是否包含敏感數據"""
        sensitive_keys = ['password', 'token', 'key', 'secret', 'private', 'credential']
        
        for key in data.keys():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                return True
        
        return False
    
    def _encrypt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """加密敏感數據"""
        try:
            json_data = json.dumps(data)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode())
            return {'encrypted': True, 'data': encrypted_data.hex()}
        except Exception as e:
            logger.error(f"加密數據失敗: {e}")
            return data
    
    def _decrypt_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """解密數據"""
        try:
            if not encrypted_data.get('encrypted'):
                return encrypted_data
            
            hex_data = encrypted_data['data']
            encrypted_bytes = bytes.fromhex(hex_data)
            decrypted_bytes = self.cipher_suite.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode())
        except Exception as e:
            logger.error(f"解密數據失敗: {e}")
            return {}
    
    # ========== 會話管理 ==========
    
    def _get_session_id(self, user_id: int) -> Optional[str]:
        """獲取用戶會話ID"""
        # 簡化的會話管理
        session_key = f"user_{user_id}"
        if session_key not in self.active_sessions:
            session_id = str(uuid.uuid4())
            self.active_sessions[session_key] = {
                'session_id': session_id,
                'created_at': datetime.now(timezone.utc),
                'last_activity': datetime.now(timezone.utc)
            }
            return session_id
        else:
            self.active_sessions[session_key]['last_activity'] = datetime.now(timezone.utc)
            return self.active_sessions[session_key]['session_id']
    
    async def cleanup_expired_sessions(self):
        """清理過期會話"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        expired_sessions = [
            key for key, session in self.active_sessions.items()
            if session['last_activity'] < cutoff_time
        ]
        
        for session_key in expired_sessions:
            del self.active_sessions[session_key]
        
        logger.info(f"清理了 {len(expired_sessions)} 個過期會話")
    
    # ========== 合規報告 ==========
    
    async def generate_compliance_report(
        self,
        guild_id: int,
        standard: ComplianceStandard,
        start_date: datetime,
        end_date: datetime,
        generated_by: int
    ) -> ComplianceReport:
        """生成合規報告"""
        try:
            report_id = str(uuid.uuid4())
            
            # 根據合規標準篩選相關事件
            relevant_events = [
                event for event in self.event_buffer
                if (event.guild_id == guild_id and
                    start_date <= event.timestamp <= end_date)
            ]
            
            # 分析違規情況
            violations = await self._analyze_compliance_violations(relevant_events, standard)
            
            # 生成摘要
            summary = await self._generate_compliance_summary(relevant_events, standard)
            
            # 提供建議
            recommendations = await self._generate_compliance_recommendations(violations, standard)
            
            report = ComplianceReport(
                id=report_id,
                standard=standard,
                period_start=start_date,
                period_end=end_date,
                guild_id=guild_id,
                generated_by=generated_by,
                generated_at=datetime.now(timezone.utc),
                summary=summary,
                violations=violations,
                recommendations=recommendations
            )
            
            logger.info(f"✅ 合規報告已生成: {standard.value} for guild {guild_id}")
            return report
            
        except Exception as e:
            logger.error(f"生成合規報告失敗: {e}")
            raise
    
    async def _analyze_compliance_violations(
        self,
        events: List[SecurityEvent],
        standard: ComplianceStandard
    ) -> List[Dict[str, Any]]:
        """分析合規違規"""
        violations = []
        
        if standard == ComplianceStandard.GDPR:
            # GDPR相關檢查
            data_access_events = [e for e in events if e.event_type == SecurityEventType.DATA_ACCESS]
            
            for event in data_access_events:
                if event.risk_level == RiskLevel.HIGH and 'personal_data' in str(event.details):
                    violations.append({
                        'type': 'unauthorized_personal_data_access',
                        'event_id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'description': '可能的未授權個人數據存取',
                        'severity': 'high'
                    })
        
        elif standard == ComplianceStandard.SOX:
            # SOX相關檢查
            financial_events = [
                e for e in events 
                if 'financial' in str(e.resource) or 'audit' in str(e.resource)
            ]
            
            for event in financial_events:
                if event.action == AuditAction.DELETE:
                    violations.append({
                        'type': 'financial_record_deletion',
                        'event_id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'description': '財務記錄刪除操作',
                        'severity': 'critical'
                    })
        
        return violations
    
    async def _generate_compliance_summary(
        self,
        events: List[SecurityEvent],
        standard: ComplianceStandard
    ) -> Dict[str, Any]:
        """生成合規摘要"""
        return {
            'total_events': len(events),
            'high_risk_events': len([e for e in events if e.risk_level == RiskLevel.HIGH]),
            'critical_events': len([e for e in events if e.risk_level == RiskLevel.CRITICAL]),
            'data_access_events': len([e for e in events if e.event_type == SecurityEventType.DATA_ACCESS]),
            'user_management_events': len([e for e in events if e.event_type == SecurityEventType.USER_MANAGEMENT]),
            'unique_users': len(set(e.user_id for e in events)),
            'compliance_standard': standard.value
        }
    
    async def _generate_compliance_recommendations(
        self,
        violations: List[Dict[str, Any]],
        standard: ComplianceStandard
    ) -> List[str]:
        """生成合規建議"""
        recommendations = []
        
        if violations:
            recommendations.append("檢查並修正所有檢測到的違規行為")
            recommendations.append("加強用戶培訓和意識")
            recommendations.append("實施更嚴格的存取控制")
        
        if standard == ComplianceStandard.GDPR:
            recommendations.extend([
                "實施數據保護影響評估(DPIA)",
                "確保所有個人數據處理都有合法基礎",
                "建立數據主體權利回應程序"
            ])
        
        elif standard == ComplianceStandard.SOX:
            recommendations.extend([
                "建立財務數據變更的雙重認證",
                "實施財務系統的定期稽核",
                "確保財務記錄的完整性和不可否認性"
            ])
        
        return recommendations
    
    # ========== 事件緩衝區管理 ==========
    
    async def _flush_event_buffer(self):
        """將事件緩衝區刷新到資料庫"""
        if not self.event_buffer:
            return
        
        try:
            # 這裡應該實現將事件寫入資料庫的邏輯
            # 目前先記錄日誌
            logger.info(f"將 {len(self.event_buffer)} 個安全事件寫入資料庫")
            
            # 清空緩衝區
            self.event_buffer.clear()
            
        except Exception as e:
            logger.error(f"刷新事件緩衝區失敗: {e}")
    
    # ========== 統計和報告 ==========
    
    async def get_security_statistics(
        self,
        guild_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """獲取安全統計資訊"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        relevant_events = [
            event for event in self.event_buffer
            if (event.guild_id == guild_id and event.timestamp > cutoff_date)
        ]
        
        return {
            'total_events': len(relevant_events),
            'events_by_type': self._count_events_by_type(relevant_events),
            'events_by_risk_level': self._count_events_by_risk_level(relevant_events),
            'top_users': self._get_top_users_by_activity(relevant_events),
            'suspicious_activities': len([
                e for e in relevant_events 
                if e.event_type == SecurityEventType.SUSPICIOUS_ACTIVITY
            ]),
            'security_violations': len([
                e for e in relevant_events 
                if e.event_type == SecurityEventType.SECURITY_VIOLATION
            ])
        }
    
    def _count_events_by_type(self, events: List[SecurityEvent]) -> Dict[str, int]:
        """按類型統計事件"""
        counts = {}
        for event in events:
            event_type = event.event_type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def _count_events_by_risk_level(self, events: List[SecurityEvent]) -> Dict[str, int]:
        """按風險等級統計事件"""
        counts = {}
        for event in events:
            risk_level = event.risk_level.value
            counts[risk_level] = counts.get(risk_level, 0) + 1
        return counts
    
    def _get_top_users_by_activity(self, events: List[SecurityEvent], limit: int = 10) -> List[Dict[str, Any]]:
        """獲取活動最多的用戶"""
        user_counts = {}
        for event in events:
            user_id = event.user_id
            if user_id not in user_counts:
                user_counts[user_id] = {'count': 0, 'high_risk_count': 0}
            user_counts[user_id]['count'] += 1
            if event.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                user_counts[user_id]['high_risk_count'] += 1
        
        sorted_users = sorted(
            user_counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:limit]
        
        return [
            {'user_id': user_id, **stats}
            for user_id, stats in sorted_users
        ]

# 全域實例
security_audit_manager = SecurityAuditManager()