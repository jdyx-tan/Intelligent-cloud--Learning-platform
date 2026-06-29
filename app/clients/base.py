from __future__ import annotations

from typing import Any

import requests
from requests import Response

from app.core.config import Settings


class HttpClientError(RuntimeError):
    """微服务 HTTP 调用异常基类。"""


class ServiceUnavailableError(HttpClientError):
    """目标服务不可用，例如连接失败或超时。"""


class RemoteServiceError(HttpClientError):
    """目标服务已响应，但返回了错误状态码或非法响应。"""


class BaseHttpClient:
    """微服务 HTTP 调用基类，统一处理请求/超时/异常。"""

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        return self._request_json("GET", url, params=params)

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        return self._request_json("POST", url, json=json)

    def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            raise ServiceUnavailableError(f"请求超时：{url}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ServiceUnavailableError(f"无法连接服务：{url}") from exc
        except requests.exceptions.HTTPError as exc:
            raise RemoteServiceError(self._format_http_error(exc.response, url)) from exc
        except ValueError as exc:
            raise RemoteServiceError(f"服务返回了无法解析的响应：{url}") from exc
        except requests.exceptions.RequestException as exc:
            raise RemoteServiceError(f"请求服务失败：{url}，原因：{exc}") from exc

    @staticmethod
    def _format_http_error(response: Response | None, url: str) -> str:
        if response is None:
            return f"服务返回异常状态：{url}"
        return f"服务返回异常状态：{response.status_code} {url}"
