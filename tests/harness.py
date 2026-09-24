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

    `noctalia config validate <candidate>` is answered the way the real one
    answers the only error class that matters here: a candidate that does not
    parse is rejected. `validate_returncode` forces an answer instead. The same
    command pointed at settings.toml itself is the read-only check `scatter`
    uses to find stale settings, and prints `validate_stdout`.
    """

    CompletedProcess = subprocess.CompletedProcess

    def __init__(self):
        self.calls = []
        self.validate_returncode = None
        self.validate_stderr = ""
        self.validate_stdout = ""
        # (settings.toml, candidate) as they stood when a candidate was checked.
        self.seen_at_validate = []

    def run(self, argv, **kwargs):
        import tomllib

        self.calls.append(list(argv))
        if argv[:3] != ["noctalia", "config", "validate"] or len(argv) < 4:
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        path = Path(argv[3])
        if not path.name.endswith(".noctes-new"):
            return subprocess.CompletedProcess(argv, 0, stdout=self.validate_stdout, stderr="")

        live = path.with_name(path.name.removesuffix(".noctes-new"))
        self.seen_at_validate.append((live.read_text(), path.read_text()))
        code, stderr = self.validate_returncode, self.validate_stderr
        if code is None:
            try:
                tomllib.loads(path.read_text())
                code = 0
            except tomllib.TOMLDecodeError as error:
                code, stderr = 1, str(error)
        return subprocess.CompletedProcess(argv, code, stdout="", stderr=stderr if code else "")

    @property
    def validated(self):
        """A candidate was checked, which is to say a write was attempted."""
        return bool(self.seen_at_validate)

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

    def files(self):
        return sorted(p.name for p in self.tmp.iterdir())

    def assertValidToml(self, text=None):
        """Every write has to survive Noctalia's parser.

        A settings file that does not parse is one the shell refuses to load: it
        keeps running on the config it had, so the change never takes effect.
        """
        import tomllib

        try:
            return tomllib.loads(text if text is not None else self.read())
        except tomllib.TOMLDecodeError as error:
            self.fail(f"tool wrote TOML that does not parse: {error}")
