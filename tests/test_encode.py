import sys
import unittest

from pipeline.encode import run_checked


def py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


class RunCheckedTest(unittest.TestCase):
    def test_success_returns_completed_process(self):
        for text in (True, False):
            with self.subTest(text=text):
                self.assertEqual(run_checked(py("print('ok')"), text=text).returncode, 0)

    def test_failure_names_exit_code_command_and_stderr(self):
        cmd = py("import sys; sys.stderr.write('boom from ffmpeg'); sys.exit(3)")
        for text in (True, False):
            with self.subTest(text=text):
                with self.assertRaises(RuntimeError) as caught:
                    run_checked(cmd, text=text)
                msg = str(caught.exception)
                self.assertIn("exit 3", msg)
                self.assertIn(sys.executable, msg)
                self.assertIn("boom from ffmpeg", msg)

    def test_undecodable_stderr_still_raises_runtime_error(self):
        cmd = py("import sys; sys.stderr.buffer.write(b'bad \\xff byte'); sys.exit(1)")
        with self.assertRaises(RuntimeError) as caught:
            run_checked(cmd)
        self.assertIn("bad � byte", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
