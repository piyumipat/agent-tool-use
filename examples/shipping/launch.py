import argparse
import os
import socket
import subprocess
import sys
import time

from dotenv import load_dotenv


def wait_for_server(server: subprocess.Popen, port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Shipping MCP server stopped during startup")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Shipping MCP server did not start within 15 seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local shipping server and agent")
    parser.add_argument("--book", action="store_true", help="Enable approved fictional booking")
    args = parser.parse_args()
    load_dotenv()
    port = int(os.environ.get("MCP_PORT", "8000"))
    if not 1 <= port <= 65535:
        parser.error("MCP_PORT must be between 1 and 65535")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            parser.error(f"Port {port} is already in use")
    except OSError:
        pass

    env = os.environ.copy()
    env["MCP_URL"] = f"http://127.0.0.1:{port}/mcp"
    print(f"[launcher] Starting local MCP server on port {port}", flush=True)
    server = subprocess.Popen([sys.executable, "-m", "examples.shipping.server"], env=env)
    try:
        wait_for_server(server, port)
        print("[launcher] MCP server ready", flush=True)
        command = [sys.executable, "-m", "examples.shipping.agent"]
        if args.book:
            command.append("--book")
        return subprocess.run(command, env=env, check=False).returncode
    except KeyboardInterrupt:
        return 130
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        if server.poll() is None:
            server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        print("[launcher] MCP server stopped", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
