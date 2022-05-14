# -*- coding: utf-8 -*-
import pytest

from renutil import cli
from click.testing import CliRunner


@pytest.fixture(scope="session")
def tmp_registry(tmpdir_factory):
    # Create session-scoped temporary directory
    # This way we don't have to re-install Ren'Py for every test
    return tmpdir_factory.mktemp("tmp_registry")


def test_install(tmp_registry):
    runner = CliRunner()
    result = runner.invoke(cli, ["-r", tmp_registry, "install", "7.3.5"])
    assert result.exit_code == 0


def test_list_empty():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["-r tmp_registry", "list"])
        assert result.exit_code == 0
        assert not result.output


def test_list_populated(tmp_registry):
    runner = CliRunner()
    result = runner.invoke(cli, ["-r", tmp_registry, "list"])
    assert result.exit_code == 0
    assert result.stdout == "7.3.5\n"
