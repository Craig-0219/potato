# bot/services/workflow_engine.py - 智能工作流程引擎 v1.6.0
"""
智能工作流程引擎
提供可視化流程設計、條件觸發、自動執行等企業級工作流程功能
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from shared.logger import logger


class WorkflowStatus(Enum):
    """工作流程狀態"""
    DRAFT = "draft"           # 草稿
    ACTIVE = "active"         # 啟用中
    PAUSED = "paused"         # 暫停
    DISABLED = "disabled"     # 停用
    ARCHIVED = "archived"     # 封存

class TriggerType(Enum):
    """觸發類型"""
    MANUAL = "manual"                    # 手動觸發
    TICKET_CREATED = "ticket_created"    # 票券建立
    TICKET_UPDATED = "ticket_updated"    # 票券更新
    TICKET_CLOSED = "ticket_closed"     # 票券關閉
    MEMBER_JOINED = "member_joined"      # 成員加入
    MEMBER_LEFT = "member_left"          # 成員離開
    SCHEDULED = "scheduled"              # 定時觸發
    WEBHOOK = "webhook"                  # Webhook觸發
    SLA_BREACH = "sla_breach"           # SLA違規
    CUSTOM_EVENT = "custom_event"        # 自定義事件

class ActionType(Enum):
    """動作類型"""
    ASSIGN_TICKET = "assign_ticket"              # 指派票券
    SEND_MESSAGE = "send_message"                # 發送訊息
    ADD_TAG = "add_tag"                         # 添加標籤
    CHANGE_PRIORITY = "change_priority"          # 變更優先級
    NOTIFY_USER = "notify_user"                 # 通知用戶
    UPDATE_DATABASE = "update_database"          # 更新資料庫
    CALL_WEBHOOK = "call_webhook"               # 調用Webhook
    DELAY = "delay"                             # 延遲執行
    BRANCH_CONDITION = "branch_condition"        # 條件分支
    CLOSE_TICKET = "close_ticket"               # 關閉票券

@dataclass
class WorkflowCondition:
    """工作流程條件"""
    field: str                    # 條件欄位
    operator: str                 # 操作符 (==, !=, >, <, contains, etc.)
    value: Any                    # 比較值
    logic: str = "AND"           # 邏輯關係 (AND, OR)

@dataclass
class WorkflowAction:
    """工作流程動作"""
    id: str                       # 動作ID
    type: ActionType              # 動作類型
    parameters: Dict[str, Any]    # 動作參數
    conditions: List[WorkflowCondition] = field(default_factory=list)
    delay_seconds: int = 0        # 延遲執行秒數
    retry_count: int = 0          # 重試次數
    on_error: str = "continue"    # 錯誤處理 (continue, stop, retry)

@dataclass
class WorkflowTrigger:
    """工作流程觸發器"""
    type: TriggerType             # 觸發類型
    conditions: List[WorkflowCondition] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowExecution:
    """工作流程執行記錄"""
    id: str                       # 執行ID
    workflow_id: str              # 工作流程ID
    trigger_data: Dict[str, Any]  # 觸發數據
    start_time: datetime          # 開始時間
    end_time: Optional[datetime] = None
    status: str = "running"       # 執行狀態
    current_action: Optional[str] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

@dataclass
class Workflow:
    """工作流程定義"""
    id: str                       # 工作流程ID
    name: str                     # 工作流程名稱
    description: str              # 描述
    guild_id: int                 # 伺服器ID
    trigger: WorkflowTrigger      # 觸發器
    actions: List[WorkflowAction] # 動作列表
    status: WorkflowStatus = WorkflowStatus.DRAFT
    created_by: int = 0           # 創建者ID
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_count: int = 0      # 執行次數
    last_executed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    version: int = 1

class WorkflowEngine:
    """智能工作流程引擎"""

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.running_executions: Dict[str, asyncio.Task] = {}
        self.trigger_handlers: Dict[TriggerType, List[str]] = {}
        self._action_registry: Dict[ActionType, Callable] = {}
        self._register_builtin_actions()

    def _register_builtin_actions(self):
        """註冊內建動作處理器"""
        self._action_registry[ActionType.SEND_MESSAGE] = self._action_send_message
        self._action_registry[ActionType.ASSIGN_TICKET] = self._action_assign_ticket
        self._action_registry[ActionType.ADD_TAG] = self._action_add_tag
        self._action_registry[ActionType.CHANGE_PRIORITY] = self._action_change_priority
        self._action_registry[ActionType.NOTIFY_USER] = self._action_notify_user
        self._action_registry[ActionType.DELAY] = self._action_delay
        self._action_registry[ActionType.BRANCH_CONDITION] = self._action_branch_condition
        self._action_registry[ActionType.CLOSE_TICKET] = self._action_close_ticket

    # ========== 工作流程管理 ==========

    async def create_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """創建工作流程"""
        try:
            workflow_id = str(uuid.uuid4())

            # 構建觸發器
            trigger_data = workflow_data.get('trigger', {})
            trigger = WorkflowTrigger(
                type=TriggerType(trigger_data.get('type', 'manual')),
                conditions=[
                    WorkflowCondition(**cond)
                    for cond in trigger_data.get('conditions', [])
                ],
                parameters=trigger_data.get('parameters', {})
            )

            # 構建動作列表
            actions = []
            for action_data in workflow_data.get('actions', []):
                action = WorkflowAction(
                    id=action_data.get('id', str(uuid.uuid4())),
                    type=ActionType(action_data['type']),
                    parameters=action_data.get('parameters', {}),
                    conditions=[
                        WorkflowCondition(**cond)
                        for cond in action_data.get('conditions', [])
                    ],
                    delay_seconds=action_data.get('delay_seconds', 0),
                    retry_count=action_data.get('retry_count', 0),
                    on_error=action_data.get('on_error', 'continue')
                )
                actions.append(action)

            # 創建工作流程
            workflow = Workflow(
                id=workflow_id,
                name=workflow_data['name'],
                description=workflow_data.get('description', ''),
                guild_id=workflow_data['guild_id'],
                trigger=trigger,
                actions=actions,
                created_by=workflow_data.get('created_by', 0),
                tags=workflow_data.get('tags', [])
            )

            self.workflows[workflow_id] = workflow
            self._register_trigger(workflow)

            logger.info(f"✅ 工作流程已創建: {workflow.name} (ID: {workflow_id})")
            return workflow_id

        except Exception as e:
            logger.error(f"❌ 創建工作流程失敗: {e}")
            raise

    async def update_workflow(self, workflow_id: str, updates: Dict[str, Any]) -> bool:
        """更新工作流程"""
        try:
            if workflow_id not in self.workflows:
                raise ValueError(f"工作流程不存在: {workflow_id}")

            workflow = self.workflows[workflow_id]

            # 更新基本資訊
            if 'name' in updates:
                workflow.name = updates['name']
            if 'description' in updates:
                workflow.description = updates['description']
            if 'status' in updates:
                workflow.status = WorkflowStatus(updates['status'])
            if 'tags' in updates:
                workflow.tags = updates['tags']

            # 更新觸發器
            if 'trigger' in updates:
                trigger_data = updates['trigger']
                workflow.trigger = WorkflowTrigger(
                    type=TriggerType(trigger_data.get('type', workflow.trigger.type.value)),
                    conditions=[
                        WorkflowCondition(**cond)
                        for cond in trigger_data.get('conditions', [])
                    ],
                    parameters=trigger_data.get('parameters', workflow.trigger.parameters)
                )

            # 更新動作
            if 'actions' in updates:
                actions = []
                for action_data in updates['actions']:
                    action = WorkflowAction(
                        id=action_data.get('id', str(uuid.uuid4())),
                        type=ActionType(action_data['type']),
                        parameters=action_data.get('parameters', {}),
                        conditions=[
                            WorkflowCondition(**cond)
                            for cond in action_data.get('conditions', [])
                        ],
                        delay_seconds=action_data.get('delay_seconds', 0),
                        retry_count=action_data.get('retry_count', 0),
                        on_error=action_data.get('on_error', 'continue')
                    )
                    actions.append(action)
                workflow.actions = actions

            workflow.updated_at = datetime.now(timezone.utc)
            workflow.version += 1

            # 重新註冊觸發器
            self._unregister_trigger(workflow_id)
            self._register_trigger(workflow)

            logger.info(f"✅ 工作流程已更新: {workflow.name}")
            return True

        except Exception as e:
            logger.error(f"❌ 更新工作流程失敗: {e}")
            return False

    async def delete_workflow(self, workflow_id: str) -> bool:
        """刪除工作流程"""
        try:
            if workflow_id not in self.workflows:
                return False

            # 停止執行中的實例
            running_executions = [
                exec_id for exec_id, execution in self.executions.items()
                if execution.workflow_id == workflow_id and execution.status == "running"
            ]

            for exec_id in running_executions:
                await self.cancel_execution(exec_id)

            # 移除觸發器註冊
            self._unregister_trigger(workflow_id)

            # 刪除工作流程
            workflow_name = self.workflows[workflow_id].name
            del self.workflows[workflow_id]

            logger.info(f"✅ 工作流程已刪除: {workflow_name}")
            return True

        except Exception as e:
            logger.error(f"❌ 刪除工作流程失敗: {e}")
            return False

    # ========== 觸發器管理 ==========

    def _register_trigger(self, workflow: Workflow):
        """註冊觸發器"""
        trigger_type = workflow.trigger.type
        if trigger_type not in self.trigger_handlers:
            self.trigger_handlers[trigger_type] = []

        if workflow.id not in self.trigger_handlers[trigger_type]:
            self.trigger_handlers[trigger_type].append(workflow.id)

                                break
                            except Exception:
                                if retry == action.retry_count - 1:
                                    logger.error(f"❌ 重試失敗: {action.type.value}")

            # 完成執行
            execution.status = "completed"
            execution.end_time = datetime.now(timezone.utc)

            # 清理運行任務
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]

            logger.info(f"✅ 工作流程執行完成: {workflow.name}")

        except Exception as e:
            execution.status = "failed"
            execution.end_time = datetime.now(timezone.utc)
            execution.errors.append(f"工作流程執行失敗: {e}")

            if execution_id in self.running_executions:
                del self.running_executions[execution_id]

            logger.error(f"❌ 工作流程執行失敗: {e}")

    async def _execute_action(self, action: WorkflowAction, execution: WorkflowExecution):
        """執行單個動作"""
        if action.type not in self._action_registry:
            raise ValueError(f"未知的動作類型: {action.type.value}")

        handler = self._action_registry[action.type]
        result = await handler(action, execution)

        # 記錄執行結果
        execution.results[action.id] = result

        return result

    # ========== 內建動作處理器 ==========

    async def _action_send_message(self, action: WorkflowAction, execution: WorkflowExecution):
        """發送訊息動作"""
        # 這裡需要整合Discord bot的訊息發送功能
        logger.info(f"📨 發送訊息: {action.parameters.get('message', '')}")
        return {"status": "sent", "message": action.parameters.get('message')}

    async def _action_assign_ticket(self, action: WorkflowAction, execution: WorkflowExecution):
        """指派票券動作"""
        # 這裡需要整合票券系統的指派功能
        logger.info(f"🎫 指派票券: {action.parameters}")
        return {"status": "assigned", "ticket_id": execution.trigger_data.get('ticket_id')}

    async def _action_add_tag(self, action: WorkflowAction, execution: WorkflowExecution):
        """添加標籤動作"""
        logger.info(f"🏷️ 添加標籤: {action.parameters.get('tags', [])}")
        return {"status": "tagged", "tags": action.parameters.get('tags', [])}

    async def _action_change_priority(self, action: WorkflowAction, execution: WorkflowExecution):
        """變更優先級動作"""
        logger.info(f"⚡ 變更優先級: {action.parameters.get('priority')}")
        return {"status": "priority_changed", "priority": action.parameters.get('priority')}

    async def _action_notify_user(self, action: WorkflowAction, execution: WorkflowExecution):
        """通知用戶動作"""
        logger.info(f"🔔 通知用戶: {action.parameters}")
        return {"status": "notified", "user_id": action.parameters.get('user_id')}

    async def _action_delay(self, action: WorkflowAction, execution: WorkflowExecution):
        """延遲動作"""
        delay_seconds = action.parameters.get('seconds', 0)
        logger.info(f"⏱️ 延遲: {delay_seconds}秒")
        await asyncio.sleep(delay_seconds)
        return {"status": "delayed", "seconds": delay_seconds}

    async def _action_branch_condition(self, action: WorkflowAction, execution: WorkflowExecution):
        """條件分支動作"""
        # 實現條件分支邏輯
        logger.info(f"🔀 條件分支: {action.parameters}")
        return {"status": "branched", "condition_result": True}

    async def _action_close_ticket(self, action: WorkflowAction, execution: WorkflowExecution):
        """關閉票券動作"""
        logger.info(f"🔒 關閉票券: {execution.trigger_data.get('ticket_id')}")
        return {"status": "closed", "ticket_id": execution.trigger_data.get('ticket_id')}

    # ========== 條件檢查 ==========

    def _check_conditions(self, conditions: List[WorkflowCondition], data: Dict[str, Any]) -> bool:
        """檢查條件"""
        if not conditions:
            return True

        results = []

        for condition in conditions:
            field_value = self._get_nested_value(data, condition.field)
            result = self._evaluate_condition(field_value, condition.operator, condition.value)
            results.append((result, condition.logic))

        # 評估邏輯表達式
        return self._evaluate_logic_expression(results)

    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """獲取嵌套欄位值"""
        keys = field_path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _evaluate_condition(self, field_value: Any, operator: str, compare_value: Any) -> bool:
        """評估單個條件"""
        try:
            if operator == "==":
                return field_value == compare_value
            elif operator == "!=":
                return field_value != compare_value
            elif operator == ">":
                return field_value > compare_value
            elif operator == "<":
                return field_value < compare_value
            elif operator == ">=":
                return field_value >= compare_value
            elif operator == "<=":
                return field_value <= compare_value
            elif operator == "contains":
                return compare_value in str(field_value)
            elif operator == "startswith":
                return str(field_value).startswith(str(compare_value))
            elif operator == "endswith":
                return str(field_value).endswith(str(compare_value))
            elif operator == "in":
                return field_value in compare_value
            elif operator == "not_in":
                return field_value not in compare_value
            elif operator == "is_null":
                return field_value is None
            elif operator == "is_not_null":
                return field_value is not None
            else:
                logger.warning(f"未知的操作符: {operator}")
                return False

        except Exception as e:
            logger.error(f"條件評估錯誤: {e}")
            return False

    def _evaluate_logic_expression(self, results: List[tuple]) -> bool:
        """評估邏輯表達式"""
        if not results:
            return True

        final_result = results[0][0]  # 第一個條件的結果

        for i in range(1, len(results)):
            current_result, logic = results[i]

            if logic == "AND":
                final_result = final_result and current_result
            elif logic == "OR":
                final_result = final_result or current_result

        return final_result

    # ========== 執行管理 ==========

    async def cancel_execution(self, execution_id: str) -> bool:
        """取消執行"""
        try:
            if execution_id in self.running_executions:
                task = self.running_executions[execution_id]
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                del self.running_executions[execution_id]

            if execution_id in self.executions:
                execution = self.executions[execution_id]
                execution.status = "cancelled"
                execution.end_time = datetime.now(timezone.utc)

            logger.info(f"✅ 工作流程執行已取消: {execution_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 取消執行失敗: {e}")
            return False

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """獲取執行狀態"""
        if execution_id not in self.executions:
            return None

        execution = self.executions[execution_id]

        return {
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "workflow_name": self.workflows.get(execution.workflow_id, {}).name if execution.workflow_id in self.workflows else "未知",
            "status": execution.status,
            "current_action": execution.current_action,
            "start_time": execution.start_time.isoformat(),
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "errors": execution.errors,
            "progress": self._calculate_execution_progress(execution)
        }

    def _calculate_execution_progress(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """計算執行進度"""
        if execution.workflow_id not in self.workflows:
            return {"completed": 0, "total": 0, "percentage": 0}

        workflow = self.workflows[execution.workflow_id]
        total_actions = len(workflow.actions)

        if not execution.current_action:
            return {"completed": 0, "total": total_actions, "percentage": 0}

        # 找到當前動作的索引
        current_index = 0
        for i, action in enumerate(workflow.actions):
            if action.id == execution.current_action:
                current_index = i + 1
                break

        percentage = (current_index / total_actions * 100) if total_actions > 0 else 100

        return {
            "completed": current_index,
            "total": total_actions,
            "percentage": round(percentage, 2)
        }

    # ========== 統計和查詢 ==========

    def get_workflows(self, guild_id: int = None, status: WorkflowStatus = None) -> List[Dict[str, Any]]:
        """獲取工作流程列表"""
        workflows = []

        for workflow in self.workflows.values():
            if guild_id and workflow.guild_id != guild_id:
                continue

            if status and workflow.status != status:
                continue

            workflows.append({
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "status": workflow.status.value,
                "trigger_type": workflow.trigger.type.value,
                "action_count": len(workflow.actions),
                "execution_count": workflow.execution_count,
                "last_executed": workflow.last_executed.isoformat() if workflow.last_executed else None,
                "created_at": workflow.created_at.isoformat(),
                "tags": workflow.tags
            })

        return workflows

    def get_workflow_statistics(self, guild_id: int = None) -> Dict[str, Any]:
        """獲取工作流程統計"""
        workflows = [w for w in self.workflows.values() if not guild_id or w.guild_id == guild_id]
        executions = [e for e in self.executions.values() if not guild_id or self.workflows.get(e.workflow_id, {}).guild_id == guild_id]

        status_counts = {}
        for workflow in workflows:
            status = workflow.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        trigger_counts = {}
        for workflow in workflows:
            trigger = workflow.trigger.type.value
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1

        execution_status_counts = {}
        for execution in executions:
            status = execution.status
            execution_status_counts[status] = execution_status_counts.get(status, 0) + 1

        return {
            "total_workflows": len(workflows),
            "total_executions": len(executions),
            "active_workflows": status_counts.get("active", 0),
            "running_executions": len(self.running_executions),
            "status_distribution": status_counts,
            "trigger_distribution": trigger_counts,
            "execution_status_distribution": execution_status_counts,
            "average_execution_time": self._calculate_average_execution_time(executions)
        }

    def _calculate_average_execution_time(self, executions: List[WorkflowExecution]) -> float:
        """計算平均執行時間"""
        completed_executions = [
            e for e in executions
            if e.status == "completed" and e.end_time
        ]

        if not completed_executions:
            return 0.0

        total_time = sum(
            (e.end_time - e.start_time).total_seconds()
            for e in completed_executions
        )

        return total_time / len(completed_executions)

# 全域工作流程引擎實例
workflow_engine = WorkflowEngine()
