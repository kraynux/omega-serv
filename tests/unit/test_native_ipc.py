"""Trames IPC cote Python (contrat IPC v1) ; les memes octets sont verifies cote C++ (vecteurs ipc)."""
import fcntl
import os
import socket
import unittest

from omega_serv.infrastructure.server import native_ipc as ipc


class TestFrames(unittest.TestCase):
    def test_round_trip(self):
        frame = ipc.Frame(ipc.HEALTH, request_id=7, generation=3).add_uint(1, 12, 8).add(2, "é")
        decoded = ipc.decode(ipc.encode(frame))
        self.assertEqual((decoded.type, decoded.request_id, decoded.generation), (ipc.HEALTH, 7, 3))
        self.assertEqual(decoded.uint(1), 12)
        self.assertEqual(decoded.text(2), "é")

    def test_prebuilt_continue_verdict_is_the_encoded_frame(self):
        for request_id in (0, 1, 0x0123456789ABCDEF, 2**64 - 1):
            self.assertEqual(ipc.continue_verdict_bytes(request_id),
                             ipc.encode(ipc.verdict_frame(request_id, None, True)))

    def test_invalid_frames_refused(self):
        good = ipc.encode(ipc.hello_ack(True))
        for bad in (good[:10], b"XXXX" + good[4:], good[:4] + b"\x02\x00" + good[6:], good + b"\x00", good[:-1]):
            with self.assertRaises(ipc.FrameError):
                ipc.decode(bad)

    def test_config_travels_in_a_sealed_memfd(self):
        content = b'{"format": 1}' * 30000  # > taille d'un message SOCK_SEQPACKET par defaut
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with left, right:
            memfd = ipc.sealed_memfd(content)
            try:
                ipc.send_frame(left, ipc.config_frame(5, content), pass_fd=memfd)
            finally:
                os.close(memfd)
            received = ipc.recv_frame(right, 1.0)
            assert received is not None
            frame, fd = received
            self.assertIsNotNone(fd)
            try:
                self.assertEqual(frame.generation, 5)
                self.assertEqual(frame.uint(ipc.CONFIG_SIZE), len(content))
                self.assertEqual(os.pread(fd, len(content) + 1, 0), content)
                with self.assertRaises(PermissionError):
                    os.pwrite(fd, b"x", 0)  # scelle : le natif lit exactement ce que Python a valide
                self.assertTrue(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & fcntl.F_SEAL_WRITE)
            finally:
                os.close(fd)

    def test_end_of_channel_and_timeout(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with right:
            with self.assertRaises(TimeoutError):
                ipc.recv_frame(right, 0.05)
            left.close()
            self.assertIsNone(ipc.recv_frame(right, 1.0))


if __name__ == "__main__":
    unittest.main()
