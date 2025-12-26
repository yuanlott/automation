#!/usr/bin/env python3
"""
Wrapper to run IOL image for Automation
- forks a child process
- wires child process' stdin/stdout to a UNIX socketpair
- exposes a single client Telnet console on a TCP port
- sends the same Telnet option negotiation bytes
- forwards bytes both directions using selectors
- cleans up child + sockets on exit
"""
import argparse
import os
import selectors
import signal
import socket
import sys
import time
from typing import Optional

# Telnet negotiation bytes:
# FF FB 01: IAC WILL ECHO
# FF FB 03: IAC WILL SUPPRESS-GA
# FF FB 00: IAC WILL BINARY
# FF FD 00: IAC DO BINARY
TELNET_OPTS = bytes(
    [
        0xFF, 0xFB, 0x01,
        0xFF, 0xFB, 0x03,
        0xFF, 0xFB, 0x00,
        0xFF, 0xFD, 0x00,
    ]
)

BUF_SZ = 4096


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrap a program (e.g., Cisco IOL) and expose its console via Telnet on a TCP port."
    )
    parser.add_argument(
        "-m", "--program", required=True, help="Program to wrap (full path if needed)."
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=10000,
        help="TCP port for Telnet access (default: 10000; must be >= 1024).",
    )
    parser.add_argument(
        "-n",
        "--name",
        default=None,
        help="argv[0] name passed to exec (optional; defaults to program).",
    )
    # `-- [OPTIONS]` passthrough
    parser.add_argument(
        "program_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the wrapped program. Use: -- <args...>",
    )
    args = parser.parse_args()

    if args.port < 1024:
        parser.error("Port must be >= 1024.")
    if args.name is None:
        args.name = args.program

    # If user included a leading "--" in remainder, argparse keeps it; drop it.
    if args.program_args and args.program_args[0] == "--":
        args.program_args = args.program_args[1:]

    return args


class Wrapper:
    def __init__(self, program: str, name: str, program_args: list[str], port: int):
        self.program = program
        self.name = name
        self.program_args = program_args
        self.port = port

        self.sel = selectors.DefaultSelector()

        self.listen_sock: Optional[socket.socket] = None
        self.client_sock: Optional[socket.socket] = None

        self.child_pid: int = 0
        self.parent_end: Optional[socket.socket] = None  # parent side of socketpair
        self.child_end: Optional[socket.socket] = (
            None  # child side (kept only before fork)
        )

        self._stopping = False

    def _install_signals(self):
        # cleanup on exit and on child death.
        signal.signal(signal.SIGINT, self._sig_exit)
        signal.signal(signal.SIGTERM, self._sig_exit)
        signal.signal(signal.SIGHUP, self._sig_exit)
        signal.signal(signal.SIGCHLD, self._sig_child)

    def _sig_exit(self, signum, frame):
        self.stop(f"Received signal {signum}")

    def _sig_child(self, signum, frame):
        # Child exited; reap it and shut down.
        try:
            while True:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                # if the main child died, stop everything
                if pid == self.child_pid:
                    self.stop(f"Child process {pid} exited (status={status})")
        except ChildProcessError:
            # no children
            self.stop("Child process exited")

    def stop(self, reason: str = ""):
        if self._stopping:
            return
        self._stopping = True

        if reason:
            print(reason, file=sys.stderr)

        # Close sockets
        for s in (self.client_sock, self.listen_sock, self.parent_end):
            try:
                if s:
                    s.close()
            except Exception:
                pass

        # Kill child hard
        if self.child_pid:
            try:
                os.kill(self.child_pid, signal.SIGKILL)
                print(f"Killed child process {self.child_pid}", file=sys.stderr)
            except ProcessLookupError:
                pass
            except Exception as e:
                print(f"Failed to kill child {self.child_pid}: {e}", file=sys.stderr)

        # Exit
        raise SystemExit(1)

    def _setup_listen(self):
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind(("0.0.0.0", self.port))
        ls.listen(1)
        ls.setblocking(False)
        self.listen_sock = ls
        self.sel.register(ls, selectors.EVENT_READ, data="listen")

    def _setup_socketpair(self):
        # Use a UNIX-domain socketpair.
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        a.setblocking(False)
        b.setblocking(False)
        self.parent_end = a
        self.child_end = b

        # Parent monitors child output through parent_end
        self.sel.register(self.parent_end, selectors.EVENT_READ, data="childpipe")

    def _fork_and_exec(self):
        pid = os.fork()
        if pid == 0:
            # Child
            try:
                # Close parent end in child
                if self.parent_end:
                    self.parent_end.close()
                    self.parent_end = None

                # Map socketpair to stdin/stdout
                assert self.child_end is not None
                fd = self.child_end.fileno()

                os.dup2(fd, 0)  # stdin
                os.dup2(fd, 1)  # stdout
                # (Optional) also map stderr to same console for visibility
                os.dup2(fd, 2)  # stderr

                # Close the original socket object after dup
                self.child_end.close()
                self.child_end = None

                time.sleep(3)

                argv = [self.name] + self.program_args
                os.execv(self.program, argv)

            except Exception as e:
                print(f"Child exec failed: {e}", file=sys.stderr)
                os._exit(127)
        else:
            # Parent
            self.child_pid = pid
            # Close child end in parent
            if self.child_end:
                self.child_end.close()
                self.child_end = None

            print(
                f"\nParent PID is {os.getpid()}, Child PID is {self.child_pid}.",
                flush=True,
            )

    def _accept_client(self):
        assert self.listen_sock is not None
        cs, addr = self.listen_sock.accept()
        cs.setblocking(False)
        cs.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.client_sock = cs

        # Single client mode: stop listening once connected
        self.sel.unregister(self.listen_sock)

        # Register client socket for reads
        self.sel.register(cs, selectors.EVENT_READ, data="client")

        # Telnet negotiation
        try:
            cs.sendall(TELNET_OPTS)
        except Exception:
            self.stop("Failed sending telnet options to client")

        # Do a non-blocking drain attempt (best effort) to consume
        # the client's telnet replies
        try:
            _ = cs.recv(256)
        except BlockingIOError:
            pass
        except Exception:
            pass

    def _client_closed(self):
        # Drop client and resume listening
        if self.client_sock:
            try:
                self.sel.unregister(self.client_sock)
            except Exception:
                pass
            try:
                self.client_sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.client_sock.close()
            except Exception:
                pass
            self.client_sock = None

        # Re-enable listening
        if self.listen_sock:
            try:
                self.sel.register(self.listen_sock, selectors.EVENT_READ, data="listen")
            except KeyError:
                # already registered
                pass

    def _forward_client_to_child(self):
        assert self.client_sock is not None
        try:
            data = self.client_sock.recv(BUF_SZ)
        except BlockingIOError:
            return
        except Exception:
            self._client_closed()
            return

        if not data:
            self._client_closed()
            return

        # Write to child's stdin via socketpair (parent_end)
        if self.parent_end:
            try:
                self.parent_end.sendall(data)
            except BrokenPipeError:
                self.stop("Child pipe broken")
            except Exception:
                self.stop("Failed writing to child pipe")

    def _forward_child_to_client(self):
        assert self.parent_end is not None
        try:
            data = self.parent_end.recv(BUF_SZ)
        except BlockingIOError:
            return
        except Exception:
            self.stop("Error reading from child pipe")
            return

        if not data:
            # Child died or closed stdout
            self.stop("Wrapped program closed its output")
            return

        if self.client_sock:
            try:
                self.client_sock.sendall(data)
            except BrokenPipeError:
                self._client_closed()
            except Exception:
                self._client_closed()
        # If no client connected, we drop output

    def run(self):
        self._install_signals()
        self._setup_socketpair()
        self._setup_listen()
        self._fork_and_exec()

        while True:
            events = self.sel.select(timeout=None)
            for key, mask in events:
                tag = key.data
                if tag == "listen":
                    self._accept_client()
                elif tag == "client":
                    self._forward_client_to_child()
                elif tag == "childpipe":
                    self._forward_child_to_client()


def main():
    args = parse_args()
    wrapper = Wrapper(
        program=args.program,
        name=args.name,
        program_args=args.program_args,
        port=args.port,
    )
    wrapper.run()


if __name__ == "__main__":
    main()
