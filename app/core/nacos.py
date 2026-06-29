from __future__ import annotations

from typing import Any

import requests

from app.core.config import Settings


class NacosClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = f"http://{settings.nacos_server_addr}"

    def _login(self) -> str | None:
        if not self.settings.nacos_username or not self.settings.nacos_password:
            return None
        try:
            response = requests.post(
                f"{self.base_url}/nacos/v1/auth/users/login",
                data={"username": self.settings.nacos_username, "password": self.settings.nacos_password},
                timeout=self.settings.nacos_timeout_ms / 1000,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload.get("accessToken")
        except Exception:
            return None

    def get_text_config(self, data_id: str, group: str | None = None) -> str | None:
        params = {
            "dataId": data_id,
            "group": group or self.settings.nacos_group,
        }
        if self.settings.nacos_namespace:
            params["tenant"] = self.settings.nacos_namespace
        token = self._login()
        if token:
            params["accessToken"] = token
        try:
            response = requests.get(
                f"{self.base_url}/nacos/v1/cs/configs",
                params=params,
                timeout=self.settings.nacos_timeout_ms / 1000,
            )
            response.raise_for_status()
            text = response.text.strip()
            return text or None
        except Exception:
            return None
