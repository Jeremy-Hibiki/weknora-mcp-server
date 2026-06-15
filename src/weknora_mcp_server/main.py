#!/usr/bin/env python3
"""
WeKnora MCP Server 主入口点

这个文件提供了一个统一的入口点来启动 WeKnora MCP 服务器。
可以通过多种方式运行：
1. python main.py
2. python -m weknora_mcp_server
3. weknora-mcp-server (安装后)
"""

from starlette.types import ASGIApp, Scope, Receive, Send

from starlette.responses import JSONResponse

from starlette.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware

import argparse
import asyncio
import os
import sys

from .weknora_mcp_server import run_stdio, run_sse, run_http, mcp


class ApiKeyASGIMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: set[str] | None = None,
    ):
        self.app = app
        self.exclude_paths = exclude_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 只拦截 HTTP 请求，WebSocket / lifespan 直接放行
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        # 与 InjectApiKeyMiddleware 一致：HTTP client 可通过 X-Api-Key 头传 key，
        # 缺省时回退到进程环境变量（便于 stdio/HTTP dev 模式从 .env 注入）。
        x_api_key = headers.get(b"x-api-key") or os.environ.get("WEKNORA_API_KEY", "").encode()

        if not x_api_key:
            response = JSONResponse(
                {"detail": "Missing X-Api-Key header"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


app = mcp.http_app(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins; use specific origins for security
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "mcp-protocol-version",
                "mcp-session-id",
                "Authorization",
                "Content-Type",
            ],
            expose_headers=["mcp-session-id"],
        ),
        Middleware(
            ApiKeyASGIMiddleware,
            exclude_paths={"/health", "/healthz"},
        ),
    ]
)


def check_environment_variables() -> bool:
    """检查环境变量配置"""
    base_url = os.getenv("WEKNORA_BASE_URL")
    api_key = os.getenv("WEKNORA_API_KEY")

    print("=== WeKnora MCP Server 环境检查 ===")
    print(f"Base URL: {base_url or 'http://localhost:8080/api/v1 (默认)'}")
    print(f"API Key (env fallback): {'已设置' if api_key else '未设置'}")
    print("HTTP/SSE 模式: 客户端应通过 X-API-Key 请求头传递 API Key")

    if not base_url:
        print("提示: 可以设置 WEKNORA_BASE_URL 环境变量")

    if not api_key:
        print("提示: stdio 模式可设置 WEKNORA_API_KEY；HTTP 模式请使用 X-API-Key 请求头")

    print("=" * 40)
    return True


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="WeKnora MCP Server - Model Context Protocol server for WeKnora API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="启用详细日志输出",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="WeKnora MCP Server 1.0.0",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type: stdio (default), sse, or http",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "0.0.0.0"),
        help="Bind host for network transports (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Bind port for network transports (default: 8000)",
    )

    return parser.parse_args()


async def main() -> None:
    """主函数"""
    args = parse_arguments()

    # 检查环境变量
    check_environment_variables()

    # 设置日志级别
    if args.verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)
        print("已启用详细日志模式")

    try:
        print(f"正在启动 WeKnora MCP Server (transport={args.transport})...")

        # Select transport mode based on CLI argument or MCP_TRANSPORT env var
        # - stdio: Default, used by VS Code Copilot for local integration
        # - sse: Server-Sent Events over HTTP, suitable for cloud/remote deployments
        # - http: Streamable HTTP sessions (MCP 2025-03-26 spec), compatible with REST clients
        if args.transport == "stdio":
            # Stdio mode: communication via stdin/stdout pipes (typical for CLI integrations)
            await run_stdio()
        elif args.transport == "sse":
            # SSE mode: HTTP server with Server-Sent Events for bidirectional streaming
            await run_sse(args.host, args.port)
        elif args.transport == "http":
            # HTTP mode: HTTP REST server with request/response model
            await run_http(args.host, args.port)

    except ImportError as e:
        print(f"导入错误: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"服务器运行错误: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def sync_main() -> None:
    """同步版本的主函数，用于 entry_points"""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
