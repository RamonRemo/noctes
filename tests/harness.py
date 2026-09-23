"""Loading the tool, and running it without touching the real Noctalia.

`noctes-widget` has no `.py` extension and no import guard beyond
`if __name__ == "__main__"`, so it loads by path. Two things have to be taken
away from it before a test runs: the settings path, which points at the user's
own file, and `subprocess`, which shells out to `noctalia`.
"""

import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "noctes" / "tools" / "noctes-widget"

# Loading the tool by path would otherwise drop a __pycache__ next to it, inside
# the directory that ships as the plugin.
sys.dont_write_bytecode = True


def load():
    """A fresh module object, so one test's patches cannot reach another."""
    spec = importlib.util.spec_from_loader(
        "noctes_widget", importlib.machinery.SourceFileLoader("noctes_widget", str(TOOL))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Noctalia:
    """Stands in for the `subprocess` module the tool imports.

    Swapped in whole rather than patching `subprocess.run`, which is one shared
    object: patching it there would reach the test runner and every other test.
    """

    CompletedProcess = subprocess.CompletedProcess

    def __init__(self):
        self.calls = []
        self.validate_returncode = 0
        self.validate_stderr = ""

    def run(self, argv, **kwargs):
        self.calls.append(list(argv))
        code = self.validate_returncode if argv[:2] == ["noctalia", "config"] else 0
        return subprocess.CompletedProcess(
            argv, code, stdout="", stderr=self.validate_stderr if code else ""
        )

    @property
    def validated(self):
        return ["noctalia", "config", "validate"] in self.calls

    @property
    def reloaded(self):
        return ["noctalia", "msg", "config-reload"] in self.calls


class ToolCase(unittest.TestCase):
    """A temp directory standing in for ~/.local/state/noctalia."""

    def setUp(self):
        self.module = load()
        self.tmp = Path(tempfile.mkdtemp(prefix="noctes-tests-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.settings = self.tmp / "settings.toml"
        self.module.SETTINGS = self.settings
        self.noctalia = Noctalia()
        self.module.subprocess = self.noctalia

        # Angles are random by design; pin them so a test can assert on output.
        self.module.random.uniform = lambda low, high: (low + high) / 2
        self.module.random.choice = lambda options: options[0]

    def write(self, text):
        self.settings.write_text(text)
        return text

    def read(self):
        return self.settings.read_text()

    def lines(self):
        return self.read().splitlines(keepends=True)

    def run_tool(self, *argv):
        """Drive the real argument parser, the way the service does.

        The tool reports on stdout; it is captured so a test run stays readable,
        and left on `self.output` for the tests that read what it printed.
        """
        old = sys.argv
        sys.argv = ["noctes-widget", *argv]
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                return self.module.main()
        finally:
            sys.argv = old
            self.output = buffer.getvalue()

    def backups(self):
        return sorted(p.name for p in self.tmp.iterdir() if ".bak" in p.name)

    def assertValidToml(self, text=None):
        """Every write has to survive Noctalia's parser.

        An unrecognised key does not fail gracefully there - it breaks the parse
        and takes the shell down - so this is the invariant that matters most.
        """
        import tomllib

        try:
            return tomllib.loads(text if text is not None else self.read())
        except tomllib.TOMLDecodeError as error:
            self.fail(f"tool wrote TOML that does not parse: {error}")
