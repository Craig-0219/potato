# bot/services/fivem_push_server.py
"""
FiveM 狀態推送 API（跨機腳本上報）
"""

from __future__ import annotations

import hmac
from typing import Any, Dict, Optional

from aiohttp import web

from potato_shared.logger import logger


class FiveMPushServer:
    """FiveM 狀態推送 API Server"""

    def __init__(self, bot, host: str, port: int, api_key: str):
        self.bot = bot
        self.host = host
        self.port = port
        self.api_key = api_key
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    async def start(self) -> None:
        if self._runner:
            return

        self._app = web.Application()
        self._app.router.add_post("/fivem/push", self._handle_push)
        self._app.router.add_get("/health", self._health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info("✅ FiveM Push API 已啟動: http://%s:%s/fivem/push", self.host, self.port)

    async def stop(self) -> None:
        if not self._runner:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None
        self._app = None
        logger.info("✅ FiveM Push API 已關閉")

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    def _check_api_key(self, request: web.Request) -> bool:
        if not self.api_key:
            return False
        provided = request.headers.get("X-API-Key", "")
        if not provided:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                provided = auth[7:]
        if not provided:
            return False
        return hmac.compare_digest(provided, self.api_key)

    async def _handle_push(self, request: web.Request) -> web.Response:
        if not self._check_api_key(request):
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

        guild_id = payload.get("guild_id")
        if not guild_id:
            return web.json_response({"ok": False, "error": "guild_id_required"}, status=400)

        try:
            guild_id = int(guild_id)
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "guild_id_invalid"}, status=400)

        payload["guild_id"] = guild_id

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"ok": False, "error": "guild_not_found"}, status=404)

        fivem_cog = self.bot.get_cog("FiveMStatusCore")
        if not fivem_cog or not hasattr(fivem_cog, "handle_push"):
            return web.json_response({"ok": False, "error": "service_unavailable"}, status=503)

        try:
            result: Dict[str, Any] = await fivem_cog.handle_push(payload)
        except Exception as exc:
            logger.error("FiveM Push 處理失敗: %s", exc)
            return web.json_response({"ok": False, "error": "internal_error"}, status=500)

        return web.json_response(result)
