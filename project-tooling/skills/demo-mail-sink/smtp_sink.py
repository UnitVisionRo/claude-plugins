"""Local SMTP server that accepts every e-mail and delivers none of them: a discard sink for demo and test instances.

Dependency-free (standard library only; Python 3.12+ no longer ships `smtpd`). It answers 250 to every command,
advertises no AUTH and no STARTTLS, reads each message up to the lone "." and throws it away. Point the instance's
mail settings at it: server 127.0.0.1, its port, no STARTTLS, no SSL/TLS, credentials off.

As a process, for an instance started by hand (a demo instance), printing one line per message::

    python3 smtp_sink.py                  # listens on 127.0.0.1:2525
    python3 smtp_sink.py --port 2626      # a second instance running at the same time

In-process, for an instance started by a script (the end-to-end instance): the sink runs on a daemon thread, on a
free port, and stops with the process::

    from smtp_sink import start_in_background
    mail_port = start_in_background()     # silent; pass log=True to print one line per message

Copied into each application that uses it, from the `project-tooling:demo-mail-sink` skill.
"""

import argparse
import asyncio
import sys
import threading
from collections.abc import Awaitable, Callable

LINE_LIMIT = 1024 * 1024  # longest line accepted; asyncio's 64 KiB default would choke on long encoded lines


Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


def _handler(log: bool) -> Handler:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await handle(reader, writer, log=log)

    return handler


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, *, log: bool = True) -> None:
    """One minimal SMTP conversation: 250 to every command, read DATA up to the lone "." and discard it."""

    def reply(line: str) -> None:
        writer.write(f"{line}\r\n".encode())

    recipients: list[str] = []
    reply("220 localhost smtp-sink")
    try:
        while line := await reader.readline():
            command = line.decode(errors="replace").strip()
            verb = command.split(" ", 1)[0].upper()
            if verb == "QUIT":
                reply("221 bye")
                break
            if verb == "DATA":
                reply("354 end with <CRLF>.<CRLF>")
                await writer.drain()
                while (data_line := await reader.readline()) and data_line.rstrip(b"\r\n") != b".":
                    pass
                if log:
                    print(f"accepted and discarded, to: {', '.join(recipients) or '?'}", flush=True)
                recipients = []
                reply("250 discarded")
            else:
                if verb == "RCPT":
                    recipients.append(command.split(":", 1)[-1].strip())
                elif verb in ("MAIL", "RSET"):
                    recipients = []
                reply("250 localhost" if verb in ("EHLO", "HELO") else "250 ok")
            await writer.drain()
    except (ConnectionError, asyncio.LimitOverrunError, ValueError):
        pass  # client went away, or sent a line longer than LINE_LIMIT: drop the connection
    finally:
        writer.close()


def start_in_background(host: str = "127.0.0.1", port: int = 0, *, log: bool = False) -> int:
    """Start the sink on a daemon thread with its own event loop and return the port it listens on.

    `port=0` lets the system pick a free port, so parallel instances never collide. The thread dies with the process.
    Raises `OSError` if the address cannot be bound.
    """
    ready = threading.Event()
    outcome: dict[str, int | OSError] = {}

    def run() -> None:
        loop = asyncio.new_event_loop()
        try:
            server = loop.run_until_complete(asyncio.start_server(_handler(log), host, port, limit=LINE_LIMIT))
        except OSError as error:
            outcome["error"] = error
            ready.set()
            return
        outcome["port"] = server.sockets[0].getsockname()[1]
        ready.set()
        loop.run_forever()

    threading.Thread(target=run, name="smtp-sink", daemon=True).start()
    ready.wait()
    if isinstance(error := outcome.get("error"), OSError):
        raise error
    return int(outcome["port"])


async def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2525)
    args = parser.parse_args()
    try:
        server = await asyncio.start_server(_handler(True), args.host, args.port, limit=LINE_LIMIT)
    except OSError as error:
        sys.exit(f"smtp-sink: cannot listen on {args.host}:{args.port}: {error.strerror or error}")
    print(f"smtp-sink listening on {args.host}:{args.port}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
