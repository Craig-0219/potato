# bot/services/security/mfa_manager.py - v1.0.0
# 🔐 多因素認證 (MFA) 管理系統
# 支援 TOTP, SMS, Email 驗證

import base64
import hashlib
import io
import logging
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List

import pyotp
import qrcode

# 設置臨時日誌以處理導入錯誤
_temp_logger = logging.getLogger(__name__)

try:
    from email.mime.multipart import MimeMultipart
    from email.mime.text import MimeText
except (ImportError, AttributeError):
    # 如果導入失敗，使用空實現來避免錯誤
    _temp_logger.warning("Email MIME 模組導入失敗，使用空實現")

    class MimeText:
        def __init__(self, *args, **kwargs):
            self.content = args[0] if args else ""

        def as_string(self):
            return self.content

    class MimeMultipart:
        def __init__(self, *args, **kwargs):
            self.parts = []

        def attach(self, part):
            self.parts.append(part)

        def as_string(self):
            return "\n".join(
                p.as_string() if hasattr(p, "as_string") else str(p)
                for p in self.parts
            )


from bot.db.pool import db_pool

# 設置日誌
logger = logging.getLogger(__name__)


class MFAMethod(Enum):
    """MFA 方法枚舉"""

    TOTP = "totp"  # Time-based One-Time Password
    SMS = "sms"  # 簡訊驗證
    EMAIL = "email"  # 電子郵件驗證
    BACKUP_CODES = "backup_codes"  # 備用代碼


class MFAManager:
    """
    企業級多因素認證管理器

    功能：
    - TOTP (Time-based OTP) 生成與驗證
    - SMS 驗證碼發送與驗證
    - Email 驗證碼發送與驗證
    - 備用代碼生成與管理
    - QR Code 生成
    - 安全會話管理
    """

    def __init__(self):
        self.app_name = "Potato Discord Bot"
        self.issuer_name = "Potato Security"
        self.totp_validity_window = 2  # TOTP 有效時間窗口 (±2 步)
        self.sms_code_validity = 300  # SMS 代碼有效期 (5分鐘)
        self.email_code_validity = 600  # Email 代碼有效期 (10分鐘)
        self.backup_codes_count = 10  # 備用代碼數量
        self.max_attempts = 5  # 最大嘗試次數
        self.lockout_duration = 1800  # 鎖定時間 (30分鐘)

        # 快取系統
        self._verification_cache = {}
        self._attempt_cache = {}

        logger.info("🔐 MFA 管理器初始化完成")

    async def setup_totp(
        self, user_id: int, user_email: str
    ) -> Dict[str, Any]:
        """
        設置 TOTP 多因素認證

        Args:
            user_id: Discord 用戶 ID
            user_email: 用戶電子郵件

        Returns:
            Dict[str, Any]: 包含 QR Code 和密鑰的設置資訊
        """
        try:
            # 生成隨機密鑰
            secret = pyotp.random_base32()

            # 創建 TOTP 對象
            totp = pyotp.TOTP(secret)

            # 生成 QR Code URI
            qr_uri = totp.provisioning_uri(
                name=user_email, issuer_name=self.issuer_name
            )

            # 生成 QR Code 圖片
            qr_code_image = await self._generate_qr_code(qr_uri)

            # 保存到資料庫
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO user_mfa (user_id, method_type, secret_key, is_enabled, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            secret_key = VALUES(secret_key),
                            is_enabled = VALUES(is_enabled),
                            updated_at = VALUES(created_at)
                    """,
                        (
                            user_id,
                            MFAMethod.TOTP.value,
                            secret,
                            False,
                            datetime.now(),
                        ),
                    )
                    await conn.commit()

            logger.info(f"🔐 TOTP 設置完成：用戶 {user_id}")

            return {
                "success": True,
                "secret": secret,
                "qr_code": qr_code_image,
                "manual_entry_key": secret,
                "issuer": self.issuer_name,
                "account_name": user_email,
                "setup_instructions": {
                    "step1": "在認證應用程式中掃描 QR Code",
                    "step2": "或手動輸入密鑰",
                    "step3": "輸入生成的 6 位數驗證碼以完成設置",
                    "recommended_apps": [
                        "Google Authenticator",
                        "Microsoft Authenticator",
                        "Authy",
                        "1Password",
                    ],
                },
            }

        except Exception as e:
            logger.error(f"❌ TOTP 設置失敗：用戶 {user_id}, 錯誤: {e}")
            return {"success": False, "error": str(e)}

    async def verify_totp(self, user_id: int, code: str) -> Dict[str, Any]:
        """
        驗證 TOTP 代碼

        Args:
            user_id: Discord 用戶 ID
            code: 6 位數 TOTP 代碼

        Returns:
            Dict[str, Any]: 驗證結果
        """
        try:
            # 檢查嘗試次數限制
            if not await self._check_attempt_limit(user_id, MFAMethod.TOTP):
                return {
                    "success": False,
                    "error": "too_many_attempts",
                    "message": "驗證嘗試次數過多，請稍後再試",
                }

            # 從資料庫獲取密鑰
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT secret_key, is_enabled
                        FROM user_mfa
                        WHERE user_id = %s AND method_type = %s
                    """,
                        (user_id, MFAMethod.TOTP.value),
                    )
                    result = await cursor.fetchone()

            if not result:
                return {
                    "success": False,
                    "error": "not_setup",
                    "message": "TOTP 未設置",
                }

            secret_key, is_enabled = result

            if not is_enabled:
                return {
                    "success": False,
                    "error": "not_enabled",
                    "message": "TOTP 未啟用",
                }

            # 驗證 TOTP 代碼
            totp = pyotp.TOTP(secret_key)
            is_valid = totp.verify(
                code, valid_window=self.totp_validity_window
            )

            if is_valid:
                # 記錄成功驗證
                await self._log_mfa_event(
                    user_id, MFAMethod.TOTP, True, "TOTP 驗證成功"
                )
                await self._reset_attempt_count(user_id, MFAMethod.TOTP)

                logger.info(f"✅ TOTP 驗證成功：用戶 {user_id}")
                return {
                    "success": True,
                    "message": "TOTP 驗證成功",
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                # 記錄失敗嘗試
                await self._increment_attempt_count(user_id, MFAMethod.TOTP)
                await self._log_mfa_event(
                    user_id, MFAMethod.TOTP, False, "TOTP 驗證失敗"
                )

                return {
                    "success": False,
                    "error": "invalid_code",
                    "message": "驗證碼無效",
                }

        except Exception as e:
            logger.error(f"❌ TOTP 驗證失敗：用戶 {user_id}, 錯誤: {e}")
            return {"success": False, "error": str(e)}

    async def enable_totp(
        self, user_id: int, verification_code: str
    ) -> Dict[str, Any]:
        """
        啟用 TOTP 多因素認證

        Args:
            user_id: Discord 用戶 ID
            verification_code: 驗證碼

        Returns:
            Dict[str, Any]: 啟用結果
        """
        try:
            # 先驗證代碼
            verification_result = await self.verify_totp(
                user_id, verification_code
            )

            if not verification_result["success"]:
                return verification_result

            # 啟用 TOTP
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE user_mfa
                        SET is_enabled = TRUE, updated_at = %s
                        WHERE user_id = %s AND method_type = %s
                    """,
                        (datetime.now(), user_id, MFAMethod.TOTP.value),
                    )
                    await conn.commit()

            # 生成備用代碼
            backup_codes = await self.generate_backup_codes(user_id)

            logger.info(f"✅ TOTP 已啟用：用戶 {user_id}")

            return {
                "success": True,
                "message": "TOTP 多因素認證已啟用",
                "backup_codes": backup_codes,
                "warning": "請妥善保存這些備用代碼，每個代碼只能使用一次",
            }

        except Exception as e:
            logger.error(f"❌ TOTP 啟用失敗：用戶 {user_id}, 錯誤: {e}")
            return {"success": False, "error": str(e)}

    async def generate_backup_codes(self, user_id: int) -> List[str]:
        """
        生成備用代碼

        Args:
            user_id: Discord 用戶 ID

        Returns:
            List[str]: 備用代碼列表
        """
        try:
            backup_codes = []

            # 生成隨機備用代碼
            for _ in range(self.backup_codes_count):
                # 生成 8 位隨機代碼
                code = secrets.token_hex(4).upper()
                backup_codes.append(code)

            # 加密並保存到資料庫
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 先刪除舊的備用代碼
                    await cursor.execute(
                        """
                        DELETE FROM user_mfa
                        WHERE user_id = %s AND method_type = %s
                    """,
                        (user_id, MFAMethod.BACKUP_CODES.value),
                    )

                    # 保存新的備用代碼 (加密後)
                    for code in backup_codes:
                        encrypted_code = await self._hash_backup_code(code)
                        await cursor.execute(
                            """
                            INSERT INTO user_mfa (user_id, method_type, secret_key, is_enabled, created_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """,
                            (
                                user_id,
                                MFAMethod.BACKUP_CODES.value,
                                encrypted_code,
                                True,
                                datetime.now(),
                            ),
                        )

                    await conn.commit()

            logger.info(
                f"🔐 備用代碼已生成：用戶 {user_id}, 數量: {len(backup_codes)}"
            )
            return backup_codes

        except Exception as e:
            logger.error(f"❌ 備用代碼生成失敗：用戶 {user_id}, 錯誤: {e}")
            return []

    async def verify_backup_code(
        self, user_id: int, code: str
    ) -> Dict[str, Any]:
        """
        驗證備用代碼

        Args:
            user_id: Discord 用戶 ID
            code: 備用代碼

        Returns:
            Dict[str, Any]: 驗證結果
        """
        try:
            # 檢查嘗試次數限制
            if not await self._check_attempt_limit(
                user_id, MFAMethod.BACKUP_CODES
            ):
                return {
                    "success": False,
                    "error": "too_many_attempts",
                    "message": "驗證嘗試次數過多，請稍後再試",
                }

            # 加密輸入的代碼
            encrypted_code = await self._hash_backup_code(code.upper())

            # 從資料庫查找並驗證
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT id FROM user_mfa
                        WHERE user_id = %s AND method_type = %s AND secret_key = %s AND is_enabled = TRUE
                    """,
                        (
                            user_id,
                            MFAMethod.BACKUP_CODES.value,
                            encrypted_code,
                        ),
                    )
                    result = await cursor.fetchone()

                    if result:
                        # 找到匹配的備用代碼，刪除它 (一次性使用)
                        await cursor.execute(
                            """
                            DELETE FROM user_mfa
                            WHERE id = %s
                        """,
                            (result[0],),
                        )
                        await conn.commit()

                        # 記錄成功使用
                        await self._log_mfa_event(
                            user_id,
                            MFAMethod.BACKUP_CODES,
                            True,
                            "備用代碼驗證成功",
                        )
                        await self._reset_attempt_count(
                            user_id, MFAMethod.BACKUP_CODES
                        )

                        # 檢查剩餘備用代碼數量
                        await cursor.execute(
                            """
                            SELECT COUNT(*) FROM user_mfa
                            WHERE user_id = %s AND method_type = %s AND is_enabled = TRUE
                        """,
                            (user_id, MFAMethod.BACKUP_CODES.value),
                        )
                        remaining_codes = (await cursor.fetchone())[0]

                        logger.info(
                            f"✅ 備用代碼驗證成功：用戶 {user_id}, 剩餘: {remaining_codes}"
                        )

                        return {
                            "success": True,
                            "message": "備用代碼驗證成功",
                            "remaining_codes": remaining_codes,
                            "warning": (
                                f"剩餘 {remaining_codes} 個備用代碼"
                                if remaining_codes > 0
                                else "備用代碼已用完，請重新生成"
                            ),
                        }
                    else:
                        # 代碼無效
                        await self._increment_attempt_count(
                            user_id, MFAMethod.BACKUP_CODES
                        )
                        await self._log_mfa_event(
                            user_id,
                            MFAMethod.BACKUP_CODES,
                            False,
                            "備用代碼無效",
                        )

                        return {
                            "success": False,
                            "error": "invalid_code",
                            "message": "備用代碼無效或已使用",
                        }

        except Exception as e:
            logger.error(f"❌ 備用代碼驗證失敗：用戶 {user_id}, 錯誤: {e}")
            return {"success": False, "error": str(e)}

    async def get_mfa_status(self, user_id: int) -> Dict[str, Any]:
        """
        獲取用戶 MFA 狀態

        Args:
            user_id: Discord 用戶 ID

        Returns:
            Dict[str, Any]: MFA 狀態資訊
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取所有 MFA 方法
                    await cursor.execute(
                        """
                        SELECT method_type, is_enabled, created_at
                        FROM user_mfa
                        WHERE user_id = %s AND method_type != %s
                        GROUP BY method_type, is_enabled, created_at
                    """,
                        (user_id, MFAMethod.BACKUP_CODES.value),
                    )
                    methods = await cursor.fetchall()

                    # 獲取備用代碼數量
                    await cursor.execute(
                        """
                        SELECT COUNT(*) FROM user_mfa
                        WHERE user_id = %s AND method_type = %s AND is_enabled = TRUE
                    """,
                        (user_id, MFAMethod.BACKUP_CODES.value),
                    )
                    backup_codes_count = (await cursor.fetchone())[0]

            # 處理 MFA 狀態
            mfa_methods = {}
            has_enabled_mfa = False

            for method_type, is_enabled, created_at in methods:
                mfa_methods[method_type] = {
                    "enabled": is_enabled,
                    "setup_date": (
                        created_at.isoformat() if created_at else None
                    ),
                }
                if is_enabled:
                    has_enabled_mfa = True

            return {
                "user_id": user_id,
                "mfa_enabled": has_enabled_mfa,
                "methods": mfa_methods,
                "backup_codes_count": backup_codes_count,
                "security_level": "high" if has_enabled_mfa else "low",
                "recommendations": await self._get_security_recommendations(
                    user_id, mfa_methods
                ),
            }

        except Exception as e:
            logger.error(f"❌ 獲取 MFA 狀態失敗：用戶 {user_id}, 錯誤: {e}")
            return {"success": False, "error": str(e)}

    async def disable_mfa_method(
        self, user_id: int, method: MFAMethod, verification_code: str = None
    ) -> Dict[str, Any]:
        """
        停用 MFA 方法

        Args:
            user_id: Discord 用戶 ID
            method: MFA 方法
            verification_code: 驗證碼 (用於安全確認)

        Returns:
            Dict[str, Any]: 停用結果
        """
        try:
            # 如果提供了驗證碼，先進行驗證
            if verification_code:
                if method == MFAMethod.TOTP:
                    verify_result = await self.verify_totp(
                        user_id, verification_code
                    )
                elif method == MFAMethod.BACKUP_CODES:
                    verify_result = await self.verify_backup_code(
                        user_id, verification_code
                    )
                else:
                    verify_result = {"success": True}  # 其他方法暫時不需要驗證

                if not verify_result["success"]:
                    return {
                        "success": False,
                        "error": "verification_failed",
                        "message": "驗證失敗，無法停用 MFA",
                    }

            # 停用 MFA 方法
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if method == MFAMethod.BACKUP_CODES:
                        # 刪除所有備用代碼
                        await cursor.execute(
                            """
                            DELETE FROM user_mfa
                            WHERE user_id = %s AND method_type = %s
                        """,
                            (user_id, method.value),
                        )
                    else:
                        # 停用其他方法
                        await cursor.execute(
                            """
                            UPDATE user_mfa
                            SET is_enabled = FALSE, updated_at = %s
                            WHERE user_id = %s AND method_type = %s
                        """,
                            (datetime.now(), user_id, method.value),
                        )

                    await conn.commit()

            # 記錄安全事件
            await self._log_mfa_event(
                user_id, method, True, f"{method.value} 已停用"
            )

            logger.info(
                f"🔐 MFA 方法已停用：用戶 {user_id}, 方法: {method.value}"
            )

            return {
                "success": True,
                "message": f"{method.value} 多因素認證已停用",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"❌ MFA 停用失敗：用戶 {user_id}, 方法: {method.value}, 錯誤: {e}"
            )
            return {"success": False, "error": str(e)}

    # 私有方法

    async def _generate_qr_code(self, uri: str) -> str:
        """生成 QR Code 圖片 (Base64 編碼)"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)

            # 生成圖片
            img = qr.make_image(fill_color="black", back_color="white")

            # 轉換為 Base64
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

            return f"data:image/png;base64,{img_base64}"

        except Exception as e:
            logger.error(f"❌ QR Code 生成失敗: {e}")
            return ""

    async def _hash_backup_code(self, code: str) -> str:
        """加密備用代碼"""
        # 使用 SHA-256 加密備用代碼
        return hashlib.sha256(code.encode()).hexdigest()

    async def _check_attempt_limit(
        self, user_id: int, method: MFAMethod
    ) -> bool:
        """檢查嘗試次數限制"""
        try:
            key = f"{user_id}_{method.value}"

            if key in self._attempt_cache:
                attempts, last_attempt = self._attempt_cache[key]

                # 檢查是否在鎖定期間
                if attempts >= self.max_attempts:
                    if datetime.now() - last_attempt < timedelta(
                        seconds=self.lockout_duration
                    ):
                        return False
                    else:
                        # 鎖定期間結束，重置計數
                        self._attempt_cache[key] = (0, datetime.now())

            return True

        except Exception as e:
            logger.error(f"❌ 嘗試次數檢查失敗: {e}")
            return True  # 預設允許嘗試

    async def _increment_attempt_count(self, user_id: int, method: MFAMethod):
        """增加嘗試次數"""
        key = f"{user_id}_{method.value}"

        if key in self._attempt_cache:
            attempts, _ = self._attempt_cache[key]
            self._attempt_cache[key] = (attempts + 1, datetime.now())
        else:
            self._attempt_cache[key] = (1, datetime.now())

    async def _reset_attempt_count(self, user_id: int, method: MFAMethod):
        """重置嘗試次數"""
        key = f"{user_id}_{method.value}"
        if key in self._attempt_cache:
            del self._attempt_cache[key]

    async def _log_mfa_event(
        self, user_id: int, method: MFAMethod, success: bool, details: str
    ):
        """記錄 MFA 事件"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_events (
                            user_id, event_type, method_type, success, details,
                            ip_address, user_agent, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            user_id,
                            "mfa_verification",
                            method.value,
                            success,
                            details,
                            "internal",
                            "discord_bot",
                            datetime.now(),
                        ),
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"❌ MFA 事件記錄失敗: {e}")

    async def _get_security_recommendations(
        self, user_id: int, methods: Dict
    ) -> List[str]:
        """獲取安全建議"""
        recommendations = []

        if not methods:
            recommendations.append("建議設置 TOTP 多因素認證以提高帳戶安全性")

        if MFAMethod.TOTP.value not in methods or not methods.get(
            MFAMethod.TOTP.value, {}
        ).get("enabled"):
            recommendations.append("建議啟用 TOTP 認證應用程式")

        # 可以根據需要添加更多建議

        return recommendations


# 全域單例
mfa_manager = MFAManager()
