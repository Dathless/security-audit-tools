from __future__ import annotations

import socket


class FakeConn:
    """Giả lập 1 connection của psutil (net_connections)."""

    def __init__(self, ip, port, pid=None, udp=False):
        self.laddr = (ip, port)
        self.type = socket.SOCK_DGRAM if udp else socket.SOCK_STREAM
        self.status = "LISTEN"
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

    def net_connections(self, kind="inet"):
        if self.deny_net:
            raise self.AccessDenied("no permission to read connections")
        return self.connections

    def Process(self, pid):
        proc = self.proc_map.get(pid)
        if proc is not None:
            return proc
        raise self.NoSuchProcess(pid)


def fake_conn(ip, port, pid=None, udp=False):
    return FakeConn(ip, port, pid, udp)


def fake_process(name="fake.exe", access_denied=False):
    return FakeProcess(name, access_denied)
