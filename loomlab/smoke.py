"""Dual Codex identity smoke test for Hearthdaemon."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
from typing import Any, TextIO

import yaml


@dataclass(frozen=True, slots=True)
class AgentConfig:
    key: str
    display_name: str
    linux_user: str
    codex_path: str


class AppServer:
    def __init__(self, agent: AgentConfig, *, model: str) -> None:
        self.agent = agent
        self.model = model
        self._next_id = 1
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        current_user = pwd.getpwuid(os.getuid()).pw_name
        base = [self.agent.codex_path, "app-server", "--listen", "stdio://"]
        if self.agent.linux_user == current_user:
            command = base
        else:
            command = ["sudo", "-n", "-u", self.agent.linux_user, "-H", *base]

        agent_home = pwd.getpwnam(self.agent.linux_user).pw_dir

        self.process = subprocess.Popen(
            command,
            cwd=agent_home,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def _streams(self) -> tuple[TextIO, TextIO]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError(f"{self.agent.display_name}: app-server is not running")
        return self.process.stdin, self.process.stdout

    def _send(self, method: str, params: dict[str, Any]) -> int:
        stdin, _ = self._streams()
        request_id = self._next_id
        self._next_id += 1
        payload = {"id": request_id, "method": method, "params": params}
        stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        stdin.flush()
        return request_id

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        stdin, _ = self._streams()
        stdin.write(
            json.dumps({"method": method, "params": params}, separators=(",", ":")) + "\n"
        )
        stdin.flush()

    def _read(self) -> dict[str, Any]:
        _, stdout = self._streams()
        while True:
            line = stdout.readline()
            if line == "":
                code = self.process.poll() if self.process is not None else None
                raise RuntimeError(
                    f"{self.agent.display_name}: app-server exited unexpectedly ({code})"
                )
            line = line.strip()
            if line:
                return json.loads(line)

    def _wait_response(self, request_id: int) -> dict[str, Any]:
        while True:
            event = self._read()
            if event.get("id") != request_id:
                continue
            if "error" in event:
                raise RuntimeError(
                    f"{self.agent.display_name}: RPC error: {event['error']}"
                )
            result = event.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(
                    f"{self.agent.display_name}: malformed RPC result: {event}"
                )
            return result

    def initialize(self) -> None:
        request_id = self._send(
            "initialize",
            {
                "clientInfo": {
                    "name": "loomlab_relaid",
                    "title": "LoomLab Relaid",
                    "version": "0.1.0",
                }
            },
        )
        self._wait_response(request_id)
        self._notify("initialized", {})

    def start_thread(self) -> str:
        request_id = self._send("thread/start", {"model": self.model})
        result = self._wait_response(request_id)
        thread = result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise RuntimeError(
                f"{self.agent.display_name}: thread/start returned no thread id: {result}"
            )
        return thread["id"]

    def ask(self, thread_id: str, prompt: str) -> tuple[str, str]:
        request_id = self._send(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
            },
        )
        chunks: list[str] = []
        accepted = False

        while True:
            event = self._read()

            if event.get("id") == request_id:
                if "error" in event:
                    raise RuntimeError(
                        f"{self.agent.display_name}: turn/start error: {event['error']}"
                    )
                accepted = True
                continue

            method = event.get("method")
            params = event.get("params", {})

            if method == "item/agentMessage/delta":
                delta = params.get("delta")
                if isinstance(delta, str):
                    chunks.append(delta)
                continue

            if method == "turn/completed":
                turn = params.get("turn", {})
                status = turn.get("status")
                if not accepted:
                    raise RuntimeError(
                        f"{self.agent.display_name}: turn completed before turn/start acknowledgement"
                    )
                return "".join(chunks).strip(), str(status)


def load_agents(path: Path) -> list[AgentConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    agents = raw.get("agents", {})
    result: list[AgentConfig] = []
    for key in ("scribe", "forge"):
        data = agents[key]
        result.append(
            AgentConfig(
                key=key,
                display_name=data["display_name"],
                linux_user=data["linux_user"],
                codex_path=data["codex_path"],
            )
        )
    return result


def run_agent(agent: AgentConfig, model: str) -> tuple[str, str, str]:
    server = AppServer(agent, model=model)
    try:
        server.start()
        server.initialize()
        thread_id = server.start_thread()
        reply, status = server.ask(
            thread_id,
            (
                f"You are {agent.display_name}, one of two named collaborators in LoomLab Relaid. "
                f"Reply in one short sentence beginning exactly with '{agent.display_name}:' "
                "and identify yourself."
            ),
        )
        return thread_id, status, reply
    finally:
        server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config/agents.yaml",
        type=Path,
        help="agent configuration file",
    )
    parser.add_argument(
        "--model",
        default="gpt-6.1-sol",
        help="Codex model slug for the smoke turn",
    )
    args = parser.parse_args()

    agents = load_agents(args.config)

    for agent in agents:
        print(f"\n== {agent.display_name} ==")
        try:
            thread_id, status, reply = run_agent(agent, args.model)
        except Exception as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        print(f"thread: {thread_id}")
        print(f"status: {status}")
        print(f"reply:  {reply}")

        if status != "completed":
            raise SystemExit(f"{agent.display_name} did not complete successfully")

    print("\nDual identity smoke test passed.")


if __name__ == "__main__":
    main()
