from __future__ import annotations

import socket
from contextlib import nullcontext


class FakeConn:
    """Giả lập 1 connection của psutil (net_connections)."""

    def __init__(self, ip, port, pid=None, udp=False):
        self.laddr = (ip, port)
        self.raddr = ()
        self.family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        self.type = socket.SOCK_DGRAM if udp else socket.SOCK_STREAM
        self.status = "NONE" if udp else "LISTEN"
        self.pid = pid


class FakeProcess:
    """Giả lập 1 tiến trình (psutil.Process)."""

    def __init__(self, name="fake.exe", access_denied=False):
        self._name = name
        self._access_denied = access_denied

    def name(self):
        if self._access_denied:
            raise PermissionError("AccessDenied")
        return self._name

    def oneshot(self):
        return nullcontext()

    def exe(self):
        self.name()
        return "C:\\Apps\\" + self._name

    def username(self):
        self.name()
        return "TEST\\user"

    def create_time(self):
        self.name()
        return 1.0


class FakePsutil:
    """Fake toàn bộ psutil dùng bởi modules/port_scanner/scanner.py.

    - net_connections() trả về danh sách connection đã chuẩn bị sẵn
      (hoặc raise AccessDenied nếu deny_net=True).
    - Process(pid) trả về tiến trình theo proc_map hoặc raise NoSuchProcess.
    """

    CONN_LISTEN = "LISTEN"
    AccessDenied = PermissionError
    NoSuchProcess = ProcessLookupError
    ZombieProcess = ProcessLookupError

    def __init__(self, conns=None, proc_map=None):
        self.connections = list(conns or [])
        self.proc_map = dict(proc_map or {})
        self.deny_net = False
        self.inventory_calls = 0
        self.process_calls = 0

    def net_connections(self, kind="inet"):
        self.inventory_calls += 1
        if self.deny_net:
            raise self.AccessDenied("no permission to read connections")
        return self.connections

    def Process(self, pid):
        self.process_calls += 1
        proc = self.proc_map.get(pid)
        if proc is not None:
            return proc
        raise self.NoSuchProcess(pid)


def fake_conn(ip, port, pid=None, udp=False):
    return FakeConn(ip, port, pid, udp)


def fake_process(name="fake.exe", access_denied=False):
    return FakeProcess(name, access_denied)
