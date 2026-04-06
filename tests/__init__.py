"""Synthetic test support for FLyteTest.

This package installs a minimal Flyte test double so the Exonerate suite can
exercise task logic in environments where the real `flyte` package is absent.
"""

from tests.flyte_stub import install_flyte_stub

install_flyte_stub()
