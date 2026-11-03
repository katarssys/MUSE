"""Windows checkout/environment regressions; no evaluator files are modified."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from muse_eval.agents.model import run_benchmark as benchmark


class ModelPortabilityTests(unittest.TestCase):
    def test_crlf_checkout_matches_frozen_lf_content_and_hashes(self):
        expected=benchmark.frozen_fingerprint()
        read_bytes=Path.read_bytes
        def windows_checkout(path):
            return read_bytes(path).replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
        with patch.object(Path,'read_bytes',windows_checkout):
            self.assertEqual(benchmark.frozen_fingerprint(),expected)

    def test_crlf_normalization_does_not_hide_content_change(self):
        read_bytes=Path.read_bytes
        target=benchmark.ROOT/'muse_eval/harness/check_rules.py'
        def changed_checkout(path):
            data=read_bytes(path).replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
            if path==target:data+=b"\r\nraise RuntimeError('frozen guard regression probe')\r\n"
            return data
        with patch.object(Path,'read_bytes',changed_checkout):
            with self.assertRaisesRegex(RuntimeError,'FROZEN_P02_CHANGED: muse_eval/harness/check_rules.py'):
                benchmark.frozen_fingerprint()

    def test_guard_still_rejects_whitespace_and_lone_carriage_return_changes(self):
        read_bytes=Path.read_bytes
        target=benchmark.ROOT/'muse_eval/harness/check_rules.py'
        for addition in (b' ',b'\r'):
            with self.subTest(addition=addition):
                def changed_checkout(path):
                    data=read_bytes(path)
                    return data+addition if path==target else data
                with patch.object(Path,'read_bytes',changed_checkout):
                    with self.assertRaisesRegex(RuntimeError,'FROZEN_P02_CHANGED'):
                        benchmark.frozen_fingerprint()

    def test_absolute_git_works_after_environment_and_path_are_cleared(self):
        self.assertTrue(Path(benchmark.GIT_EXECUTABLE).is_absolute())
        with patch.dict(os.environ,{},clear=True):
            self.assertNotIn('PATH',os.environ)
            self.assertTrue(benchmark.frozen_fingerprint())

    def test_windows_git_path_with_spaces_is_passed_as_one_argument(self):
        executable=r'C:\Program Files\Git\cmd\git.exe'
        with patch.object(benchmark,'GIT_EXECUTABLE',executable):
            with patch.object(benchmark.subprocess,'check_output',return_value=b'output') as call:
                self.assertEqual(benchmark._git_output('show','HEAD:example.py'),b'output')
        self.assertEqual(call.call_args.args[0],[executable,'-C',str(benchmark.ROOT),'show','HEAD:example.py'])
        self.assertFalse(call.call_args.kwargs.get('shell',False))

    def test_unknown_binary_formats_are_not_newline_normalized(self):
        data=b'\x00\r\n\xff'
        self.assertEqual(benchmark._canonical_content('fixture.bin',data),data)


if __name__=='__main__':unittest.main()
