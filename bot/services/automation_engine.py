# bot/services/automation_engine.py - 進階自動化規則引擎 v1.7.0
"""
進階自動化規則引擎
提供智能化工作流程自動化、規則管理和執行監控功能
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import re

from shared.logger import logger

class TriggerType(Enum):
    """觸發器類型"""
    TICKET_CREATED = "ticket_created"
    TICKET_CLOSED = "ticket_closed"
    TICKET_UPDATED = "ticket_updated"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    MESSAGE_SENT = "message_sent"
    REACTION_ADDED = "reaction_added"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    CUSTOM = "custom"

class ActionType(Enum):
    """動作類型"""
    SEND_MESSAGE = "send_message"
    ASSIGN_ROLE = "assign_role"
    REMOVE_ROLE = "remove_role"
    SEND_DM = "send_dm"
    CREATE_CHANNEL = "create_channel"
    DELETE_CHANNEL = "delete_channel"
    MOVE_TICKET = "move_ticket"
    CLOSE_TICKET = "close_ticket"
    SEND_WEBHOOK = "send_webhook"
    EXECUTE_SCRIPT = "execute_script"
    UPDATE_DATABASE = "update_database"
    SEND_EMAIL = "send_email"

class ConditionOperator(Enum):
    """條件操作符"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    REGEX_MATCH = "regex_match"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"

class RuleStatus(Enum):
    """規則狀態"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ERROR = "error"

@dataclass
class Condition:
    """條件定義"""
    field: str
    operator: ConditionOperator
    value: Any
    description: Optional[str] = None

@dataclass
class Action:
    """動作定義"""
    type: ActionType
    parameters: Dict[str, Any]
    delay_seconds: int = 0
    retry_count: int = 3
    description: Optional[str] = None

@dataclass
class Trigger:
    """觸發器定義"""
    type: TriggerType
    conditions: List[Condition]
    parameters: Optional[Dict[str, Any]] = None
    cooldown_seconds: int = 0

@dataclass
class AutomationRule:
    """自動化規則"""
    id: str
    name: str
    description: str
    guild_id: int
    trigger: Trigger
    actions: List[Action]
    status: RuleStatus = RuleStatus.DRAFT
    created_by: int = 0
    created_at: datetime = None
    updated_at: datetime = None
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    tags: List[str] = None
    priority: int = 5  # 1-10, 10 為最高優先級

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = []

@dataclass
class ExecutionContext:
    """執行上下文"""
    rule_id: str
    trigger_event: Dict[str, Any]
    guild_id: int
    user_id: Optional[int] = None
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    execution_id: str = None
    started_at: datetime = None
    variables: Dict[str, Any] = None

    def __post_init__(self):
        if self.execution_id is None:
            self.execution_id = str(uuid.uuid4())
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        if self.variables is None:
            self.variables = {}

@dataclass
class ExecutionResult:
    """執行結果"""
    execution_id: str
    rule_id: str
    success: bool
    executed_actions: int
    failed_actions: int
    execution_time: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = None
    completed_at: datetime = None

    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)
        if self.details is None:
            self.details = {}

class AutomationEngine:
    """進階自動化規則引擎"""
    
    def __init__(self):
        self.rules: Dict[str, AutomationRule] = {}
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_history: List[ExecutionResult] = []
        self.action_handlers: Dict[ActionType, Callable] = {}
        self.condition_evaluators: Dict[ConditionOperator, Callable] = {}
        self._setup_default_handlers()
        logger.info("✅ 進階自動化規則引擎已初始化")

    def _setup_default_handlers(self):
        """設置默認的處理器"""
        # 動作處理器
        self.action_handlers.update({
            ActionType.SEND_MESSAGE: self._handle_send_message,
            ActionType.ASSIGN_ROLE: self._handle_assign_role,
            ActionType.REMOVE_ROLE: self._handle_remove_role,
            ActionType.SEND_DM: self._handle_send_dm,
            ActionType.CREATE_CHANNEL: self._handle_create_channel,
            ActionType.DELETE_CHANNEL: self._handle_delete_channel,
            ActionType.MOVE_TICKET: self._handle_move_ticket,
            ActionType.CLOSE_TICKET: self._handle_close_ticket,
            ActionType.SEND_WEBHOOK: self._handle_send_webhook,
            ActionType.EXECUTE_SCRIPT: self._handle_execute_script,
            ActionType.UPDATE_DATABASE: self._handle_update_database,
            ActionType.SEND_EMAIL: self._handle_send_email,
        })
        
        # 條件評估器
        self.condition_evaluators.update({
            ConditionOperator.EQUALS: lambda x, y: x == y,
            ConditionOperator.NOT_EQUALS: lambda x, y: x != y,
            ConditionOperator.CONTAINS: lambda x, y: str(y) in str(x),
            ConditionOperator.NOT_CONTAINS: lambda x, y: str(y) not in str(x),
            ConditionOperator.STARTS_WITH: lambda x, y: str(x).startswith(str(y)),
            ConditionOperator.ENDS_WITH: lambda x, y: str(x).endswith(str(y)),
            ConditionOperator.GREATER_THAN: lambda x, y: float(x) > float(y),
            ConditionOperator.LESS_THAN: lambda x, y: float(x) < float(y),
            ConditionOperator.REGEX_MATCH: lambda x, y: bool(re.search(str(y), str(x))),
            ConditionOperator.IN_LIST: lambda x, y: x in (y if isinstance(y, list) else [y]),
            ConditionOperator.NOT_IN_LIST: lambda x, y: x not in (y if isinstance(y, list) else [y]),
        })

    # ========== 規則管理 ==========

    async def create_rule(self, rule_data: Dict[str, Any]) -> AutomationRule:
        """創建自動化規則"""
        try:
            # 創建觸發器
            trigger_data = rule_data['trigger']
            trigger = Trigger(
                type=TriggerType(trigger_data['type']),
                conditions=[
                    Condition(
                        field=cond['field'],
                        operator=ConditionOperator(cond['operator']),
                        value=cond['value'],
                        description=cond.get('description')
                    ) for cond in trigger_data.get('conditions', [])
                ],
                parameters=trigger_data.get('parameters', {}),
                cooldown_seconds=trigger_data.get('cooldown_seconds', 0)
            )
            
            # 創建動作列表
            actions = [
                Action(
                    type=ActionType(action['type']),
                    parameters=action['parameters'],
                    delay_seconds=action.get('delay_seconds', 0),
                    retry_count=action.get('retry_count', 3),
                    description=action.get('description')
                ) for action in rule_data['actions']
            ]
            
            # 創建規則
            rule = AutomationRule(
                id=rule_data.get('id', str(uuid.uuid4())),
                name=rule_data['name'],
                description=rule_data['description'],
                guild_id=rule_data['guild_id'],
                trigger=trigger,
                actions=actions,
                status=RuleStatus(rule_data.get('status', 'draft')),
                created_by=rule_data.get('created_by', 0),
                tags=rule_data.get('tags', []),
                priority=rule_data.get('priority', 5)
            )
            
            self.rules[rule.id] = rule
            logger.info(f"✅ 自動化規則已創建: {rule.name} ({rule.id})")
            return rule
            
        except Exception as e:
            logger.error(f"創建自動化規則失敗: {e}")
            raise

    async def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[AutomationRule]:
        """更新自動化規則"""
        try:
            if rule_id not in self.rules:
                return None
                
            rule = self.rules[rule_id]
            
            # 更新基本屬性
            if 'name' in updates:
                rule.name = updates['name']
            if 'description' in updates:
                rule.description = updates['description']
            if 'status' in updates:
                rule.status = RuleStatus(updates['status'])
            if 'tags' in updates:
                rule.tags = updates['tags']
            if 'priority' in updates:
                rule.priority = updates['priority']
                
            rule.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"✅ 自動化規則已更新: {rule.name} ({rule.id})")
            return rule
            
        except Exception as e:
            logger.error(f"更新自動化規則失敗: {e}")
            return None

    async def delete_rule(self, rule_id: str) -> bool:
        """刪除自動化規則"""
        try:
            if rule_id in self.rules:
                rule = self.rules.pop(rule_id)
                logger.info(f"✅ 自動化規則已刪除: {rule.name} ({rule.id})")
                return True
            return False
            
        except Exception as e:
            logger.error(f"刪除自動化規則失敗: {e}")
            return False

    async def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        """獲取自動化規則"""
        return self.rules.get(rule_id)

    async def get_rules(self, guild_id: int = None, status: RuleStatus = None) -> List[AutomationRule]:
        """獲取自動化規則列表"""
        rules = list(self.rules.values())
        
        if guild_id:
            rules = [r for r in rules if r.guild_id == guild_id]
        if status:
            rules = [r for r in rules if r.status == status]
            
        # 按優先級排序
        rules.sort(key=lambda r: r.priority, reverse=True)
        return rules

    # ========== 事件處理 ==========

    async def process_event(self, event_type: TriggerType, event_data: Dict[str, Any]) -> List[ExecutionResult]:
        """處理事件並執行匹配的規則"""
        results = []
        guild_id = event_data.get('guild_id')
        
        try:
            # 查找匹配的規則
            matching_rules = await self._find_matching_rules(event_type, event_data)
            
            # 按優先級執行規則
            for rule in matching_rules:
                if await self._can_execute_rule(rule, event_data):
                    result = await self._execute_rule(rule, event_data)
                    results.append(result)
                    
            logger.info(f"事件處理完成: {event_type.value}, 執行了 {len(results)} 個規則")
            return results
            
        except Exception as e:
            logger.error(f"處理事件失敗: {e}")
            return results

    async def _find_matching_rules(self, event_type: TriggerType, event_data: Dict[str, Any]) -> List[AutomationRule]:
        """查找匹配事件的規則"""
        matching_rules = []
        guild_id = event_data.get('guild_id')
        
        for rule in self.rules.values():
            # 檢查基本條件
            if (rule.status != RuleStatus.ACTIVE or 
                rule.trigger.type != event_type or
                rule.guild_id != guild_id):
                continue
                
            # 檢查觸發條件
            if await self._evaluate_trigger_conditions(rule.trigger, event_data):
                matching_rules.append(rule)
                
        # 按優先級排序
        matching_rules.sort(key=lambda r: r.priority, reverse=True)
        return matching_rules

    async def _evaluate_trigger_conditions(self, trigger: Trigger, event_data: Dict[str, Any]) -> bool:
        """評估觸發條件"""
        try:
            if not trigger.conditions:
                return True  # 沒有條件時總是觸發
                
            for condition in trigger.conditions:
                field_value = self._get_field_value(event_data, condition.field)
                
                if not self._evaluate_condition(condition, field_value):
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"評估觸發條件失敗: {e}")
            return False

    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """獲取嵌套字段值"""
        try:
            value = data
            for field in field_path.split('.'):
                if isinstance(value, dict) and field in value:
                    value = value[field]
                else:
                    return None
            return value
        except:
            return None

    def _evaluate_condition(self, condition: Condition, actual_value: Any) -> bool:
        """評估單個條件"""
        try:
            evaluator = self.condition_evaluators.get(condition.operator)
            if not evaluator:
                logger.warning(f"未知的條件操作符: {condition.operator}")
                return False
                
            return evaluator(actual_value, condition.value)
            
        except Exception as e:
            logger.error(f"評估條件失敗: {e}")
            return False

    async def _can_execute_rule(self, rule: AutomationRule, event_data: Dict[str, Any]) -> bool:
        """檢查規則是否可以執行"""
        # 檢查冷卻期
        if rule.trigger.cooldown_seconds > 0 and rule.last_executed:
            cooldown_end = rule.last_executed + timedelta(seconds=rule.trigger.cooldown_seconds)
            if datetime.now(timezone.utc) < cooldown_end:
                return False
                
        return True

    async def _execute_rule(self, rule: AutomationRule, event_data: Dict[str, Any]) -> ExecutionResult:
        """執行自動化規則"""
        context = ExecutionContext(
            rule_id=rule.id,
            trigger_event=event_data,
            guild_id=rule.guild_id,
            user_id=event_data.get('user_id'),
            channel_id=event_data.get('channel_id'),
            message_id=event_data.get('message_id')
        )
        
        self.active_executions[context.execution_id] = context
        
        try:
            start_time = datetime.now(timezone.utc)
            executed_actions = 0
            failed_actions = 0
            
            # 執行所有動作
            for action in rule.actions:
                try:
                    if action.delay_seconds > 0:
                        await asyncio.sleep(action.delay_seconds)
                        
                    success = await self._execute_action(action, context)
                    if success:
                        executed_actions += 1
                    else:
                        failed_actions += 1
                        
                except Exception as e:
                    logger.error(f"執行動作失敗: {action.type.value}, {e}")
                    failed_actions += 1
            
            # 更新統計
            rule.execution_count += 1
            rule.last_executed = datetime.now(timezone.utc)
            
            if failed_actions == 0:
                rule.success_count += 1
            else:
                rule.failure_count += 1
            
            # 計算執行時間
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # 創建執行結果
            result = ExecutionResult(
                execution_id=context.execution_id,
                rule_id=rule.id,
                success=failed_actions == 0,
                executed_actions=executed_actions,
                failed_actions=failed_actions,
                execution_time=execution_time
            )
            
            self.execution_history.append(result)
            logger.info(f"規則執行完成: {rule.name}, 成功: {result.success}")
            
            return result
            
        except Exception as e:
            logger.error(f"執行規則失敗: {rule.name}, {e}")
            return ExecutionResult(
                execution_id=context.execution_id,
                rule_id=rule.id,
                success=False,
                executed_actions=0,
                failed_actions=len(rule.actions),
                execution_time=0,
                error_message=str(e)
            )
            
        finally:
            # 清理活動執行
            if context.execution_id in self.active_executions:
                del self.active_executions[context.execution_id]

    # ========== 動作處理器 ==========

    async def _execute_action(self, action: Action, context: ExecutionContext) -> bool:
        """執行單個動作"""
        handler = self.action_handlers.get(action.type)
        if not handler:
            logger.error(f"未找到動作處理器: {action.type}")
            return False
            
        retry_count = 0
        while retry_count <= action.retry_count:
            try:
                result = await handler(action.parameters, context)
                if result:
                    return True
                    
            except Exception as e:
                logger.error(f"執行動作失敗 (嘗試 {retry_count + 1}/{action.retry_count + 1}): {e}")
                
            retry_count += 1
            if retry_count <= action.retry_count:
                await asyncio.sleep(2 ** retry_count)  # 指數退避
                
        return False

    # ========== 默認動作處理器實現 ==========

    async def _handle_send_message(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """發送訊息"""
        try:
            # 這裡應該集成 Discord bot 實例來發送訊息
            # 現在返回模擬成功
            logger.info(f"模擬發送訊息: {params}")
            return True
        except Exception as e:
            logger.error(f"發送訊息失敗: {e}")
            return False

    async def _handle_assign_role(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """分配角色"""
        try:
            logger.info(f"模擬分配角色: {params}")
            return True
        except Exception as e:
            logger.error(f"分配角色失敗: {e}")
            return False

    async def _handle_remove_role(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """移除角色"""
        try:
            logger.info(f"模擬移除角色: {params}")
            return True
        except Exception as e:
            logger.error(f"移除角色失敗: {e}")
            return False

    async def _handle_send_dm(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """發送私訊"""
        try:
            logger.info(f"模擬發送私訊: {params}")
            return True
        except Exception as e:
            logger.error(f"發送私訊失敗: {e}")
            return False

    async def _handle_create_channel(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """創建頻道"""
        try:
            logger.info(f"模擬創建頻道: {params}")
            return True
        except Exception as e:
            logger.error(f"創建頻道失敗: {e}")
            return False

    async def _handle_delete_channel(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """刪除頻道"""
        try:
            logger.info(f"模擬刪除頻道: {params}")
            return True
        except Exception as e:
            logger.error(f"刪除頻道失敗: {e}")
            return False

    async def _handle_move_ticket(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """移動票券"""
        try:
            logger.info(f"模擬移動票券: {params}")
            return True
        except Exception as e:
            logger.error(f"移動票券失敗: {e}")
            return False

    async def _handle_close_ticket(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """關閉票券"""
        try:
            logger.info(f"模擬關閉票券: {params}")
            return True
        except Exception as e:
            logger.error(f"關閉票券失敗: {e}")
            return False

    async def _handle_send_webhook(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """發送 Webhook"""
        try:
            logger.info(f"模擬發送 Webhook: {params}")
            return True
        except Exception as e:
            logger.error(f"發送 Webhook 失敗: {e}")
            return False

    async def _handle_execute_script(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """執行腳本"""
        try:
            logger.info(f"模擬執行腳本: {params}")
            return True
        except Exception as e:
            logger.error(f"執行腳本失敗: {e}")
            return False

    async def _handle_update_database(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """更新資料庫"""
        try:
            logger.info(f"模擬更新資料庫: {params}")
            return True
        except Exception as e:
            logger.error(f"更新資料庫失敗: {e}")
            return False

    async def _handle_send_email(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        """發送郵件"""
        try:
            logger.info(f"模擬發送郵件: {params}")
            return True
        except Exception as e:
            logger.error(f"發送郵件失敗: {e}")
            return False

    # ========== 統計和監控 ==========

    async def get_execution_stats(self, guild_id: int = None) -> Dict[str, Any]:
        """獲取執行統計"""
        try:
            rules = await self.get_rules(guild_id)
            
            total_rules = len(rules)
            active_rules = len([r for r in rules if r.status == RuleStatus.ACTIVE])
            total_executions = sum(r.execution_count for r in rules)
            total_success = sum(r.success_count for r in rules)
            total_failures = sum(r.failure_count for r in rules)
            
            success_rate = (total_success / total_executions * 100) if total_executions > 0 else 0
            
            return {
                'total_rules': total_rules,
                'active_rules': active_rules,
                'total_executions': total_executions,
                'success_count': total_success,
                'failure_count': total_failures,
                'success_rate': round(success_rate, 2),
                'active_executions': len(self.active_executions)
            }
            
        except Exception as e:
            logger.error(f"獲取執行統計失敗: {e}")
            return {}

    async def get_recent_executions(self, limit: int = 50) -> List[ExecutionResult]:
        """獲取最近執行記錄"""
        return sorted(self.execution_history, key=lambda x: x.completed_at, reverse=True)[:limit]

    async def cleanup_old_history(self, days: int = 30):
        """清理舊的執行記錄"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            old_count = len(self.execution_history)
            
            self.execution_history = [
                record for record in self.execution_history 
                if record.completed_at > cutoff_date
            ]
            
            cleaned_count = old_count - len(self.execution_history)
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 條舊執行記錄")
                
        except Exception as e:
            logger.error(f"清理執行記錄失敗: {e}")

# 全局引擎實例
automation_engine = AutomationEngine()