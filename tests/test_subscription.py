from __future__ import annotations

import grp
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mihomo-subscription"


def load_module():
    loader = importlib.machinery.SourceFileLoader("mihomo_subscription", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sub = load_module()


def fixture_text(name: str) -> str:
    return (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8")


class SubscriptionTests(unittest.TestCase):
    def test_base_config_uses_explicit_dns_upstreams(self):
        document = yaml.safe_load(
            (ROOT / "config.base.yaml").read_text(encoding="utf-8")
        )
        dns = document["dns"]

        self.assertTrue(dns["enable"])
        self.assertEqual(dns["enhanced-mode"], "fake-ip")
        self.assertEqual(dns["default-nameserver"][0], "223.5.5.5")
        self.assertNotIn("system", dns["default-nameserver"])
        self.assertNotIn("system", dns["nameserver"])
        self.assertNotIn("system", dns["proxy-server-nameserver"])
        self.assertNotIn("geosite", dns["fallback-filter"])

    def test_extracts_only_proxies_from_full_clash_config(self):
        proxies = sub.extract_proxies(fixture_text("clash-full.yaml"), "test")
        prefixed = sub.apply_prefix_and_validate_names(
            proxies,
            source_id="test",
            prefix="[test] ",
        )

        self.assertEqual(
            prefixed,
            [
                {
                    "name": "[test] HK",
                    "type": "ss",
                    "server": "127.0.0.1",
                    "port": 8388,
                    "cipher": "aes-128-gcm",
                    "password": "test",
                }
            ],
        )

    def test_extracts_provider_payload(self):
        proxies = sub.extract_proxies(fixture_text("provider.yaml"), "test")
        self.assertEqual(proxies[0]["name"], "JP")
        self.assertEqual(proxies[0]["type"], "trojan")

    def test_rejects_empty_source_by_default(self):
        with mock.patch.dict(os.environ, {"SUB_URL": "https://example.invalid/sub"}):
            with mock.patch.object(sub, "fetch_url", return_value=b"proxies: []\n"):
                with self.assertRaisesRegex(sub.SubscriptionError, "没有节点"):
                    sub.normalize_source(
                        {
                            "id": "empty",
                            "url_env": "SUB_URL",
                            "converter": {"type": "direct"},
                        },
                        timeout=1,
                        max_bytes=1024,
                    )

    def test_falls_back_to_cache_when_source_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_dir = Path(temporary_directory) / "cache"
            cache_dir.mkdir()
            (cache_dir / "backup.yaml").write_text(
                yaml.safe_dump(
                    {
                        "payload": [
                            {
                                "name": "[backup] OLD",
                                "type": "ss",
                                "server": "127.0.0.1",
                                "port": 8388,
                                "cipher": "aes-128-gcm",
                                "password": "old",
                            }
                        ]
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            def fake_fetch(url, **kwargs):
                if url.endswith("/backup"):
                    raise sub.SubscriptionError("boom")
                return fixture_text("clash-full.yaml").encode("utf-8")

            environment = {
                "MAIN_URL": "https://example.invalid/main",
                "BACKUP_URL": "https://example.invalid/backup",
            }
            with mock.patch.dict(os.environ, environment):
                with mock.patch.object(sub, "fetch_url", side_effect=fake_fetch):
                    provider_bytes, cache_candidates, fallback_sources = sub.build_candidate(
                        {
                            "cache_dir": str(cache_dir),
                            "timeout_seconds": 1,
                            "max_download_bytes": 4096,
                        },
                        [
                            {
                                "id": "main",
                                "url_env": "MAIN_URL",
                                "prefix": "[main] ",
                                "converter": {"type": "direct"},
                            },
                            {
                                "id": "backup",
                                "url_env": "BACKUP_URL",
                                "prefix": "[backup] ",
                                "converter": {"type": "direct"},
                            },
                        ],
                        strict=False,
                    )

            provider = yaml.safe_load(provider_bytes)
            names = [item["name"] for item in provider["proxies"]]
            self.assertNotIn("payload", provider)
            self.assertEqual(names, ["[main] HK", "[backup] OLD"])
            self.assertEqual(list(cache_candidates), ["main"])
            self.assertEqual(fallback_sources, ["backup"])

    def test_rejects_remote_subconverter_by_default(self):
        with self.assertRaisesRegex(sub.SubscriptionError, "默认只允许本机"):
            sub.convert_with_subconverter(
                "https://example.invalid/token",
                {
                    "type": "subconverter",
                    "endpoint": "https://unknown.example.com/sub",
                    "allow_remote": False,
                },
                timeout=1,
                max_bytes=1024,
            )

    def test_load_env_file_supports_quoted_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / "secrets.env"
            env_file.write_text(
                "MIHOMO_SUB_MAIN='https://example.com/api?token=a=b&name=test user'\n",
                encoding="utf-8",
            )
            old_value = os.environ.pop("MIHOMO_SUB_MAIN", None)
            try:
                sub.load_env_file(env_file)
                self.assertEqual(
                    os.environ["MIHOMO_SUB_MAIN"],
                    "https://example.com/api?token=a=b&name=test user",
                )
            finally:
                if old_value is None:
                    os.environ.pop("MIHOMO_SUB_MAIN", None)
                else:
                    os.environ["MIHOMO_SUB_MAIN"] = old_value

    def test_read_env_file_value_reads_existing_secret(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / "secrets.env"
            env_file.write_text(
                "# comment\n"
                "OTHER=value\n"
                "MIHOMO_SUB_MAIN='https://example.com/api?token=a=b&name=test user'\n",
                encoding="utf-8",
            )

            self.assertEqual(
                sub.read_env_file_value(env_file, "MIHOMO_SUB_MAIN"),
                "https://example.com/api?token=a=b&name=test user",
            )
            self.assertIsNone(sub.read_env_file_value(env_file, "MISSING"))

    def test_set_env_file_value_replaces_existing_secret(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / "secrets.env"
            env_file.write_text(
                "# keep this\nMIHOMO_SUB_MAIN='old'\nOTHER=value\n",
                encoding="utf-8",
            )

            sub.set_env_file_value(
                env_file,
                "MIHOMO_SUB_MAIN",
                "https://example.com/api?token=a=b&name=test user",
            )

            text = env_file.read_text(encoding="utf-8")
            self.assertIn("# keep this\n", text)
            self.assertIn("OTHER=value\n", text)
            self.assertIn(
                "MIHOMO_SUB_MAIN='https://example.com/api?token=a=b&name=test user'\n",
                text,
            )
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)

    def test_enable_source_in_control_file_enables_main(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            control_file = Path(temporary_directory) / "subscriptions.yaml"
            control_file.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "settings": {},
                        "sources": [
                            {
                                "id": "main",
                                "enabled": False,
                                "url_env": "OLD_ENV",
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            sub.enable_source_in_control_file(
                control_file,
                source_id="main",
                url_env="MIHOMO_SUB_MAIN",
            )

            control = yaml.safe_load(control_file.read_text(encoding="utf-8"))
            self.assertTrue(control["sources"][0]["enabled"])
            self.assertEqual(control["sources"][0]["url_env"], "MIHOMO_SUB_MAIN")
            self.assertEqual(control["sources"][0]["converter"], {"type": "direct"})
            self.assertEqual(control_file.stat().st_mode & 0o777, 0o600)

    def test_enable_source_in_control_file_can_set_subconverter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            control_file = Path(temporary_directory) / "subscriptions.yaml"
            control_file.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "settings": {},
                        "sources": [
                            {
                                "id": "main",
                                "enabled": False,
                                "url_env": "OLD_ENV",
                                "converter": {"type": "direct"},
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            sub.enable_source_in_control_file(
                control_file,
                source_id="main",
                url_env="MIHOMO_SUB_MAIN",
                converter_type="subconverter",
            )

            control = yaml.safe_load(control_file.read_text(encoding="utf-8"))
            converter = control["sources"][0]["converter"]
            self.assertEqual(converter["type"], "subconverter")
            self.assertEqual(converter["endpoint"], "http://127.0.0.1:25500/sub")
            self.assertFalse(converter["allow_remote"])

    def test_ensure_inside_rejects_parent_escape(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory) / "home"
            with self.assertRaisesRegex(sub.SubscriptionError, "home_dir"):
                sub.ensure_inside(base, Path(temporary_directory) / "outside")

    def test_configures_controller_and_proxy_lan_independently(self):
        template = (
            "mixed-port: 7890\n"
            "allow-lan: false\n"
            "external-controller: 127.0.0.1:9090\n"
        )

        configured = sub.configure_mihomo_template(
            template,
            controller_listen="192.168.1.10:9090",
            allow_proxy_lan=False,
        )
        document = yaml.safe_load(configured)
        self.assertEqual(document["external-controller"], "192.168.1.10:9090")
        self.assertFalse(document["allow-lan"])

        configured = sub.configure_mihomo_template(
            template,
            controller_listen=None,
            allow_proxy_lan=True,
        )
        document = yaml.safe_load(configured)
        self.assertEqual(document["external-controller"], "127.0.0.1:9090")
        self.assertTrue(document["allow-lan"])

    def test_validates_controller_listen(self):
        self.assertEqual(
            sub.validate_controller_listen("[::1]:9090"),
            "[::1]:9090",
        )
        with self.assertRaisesRegex(Exception, "HOST:PORT"):
            sub.validate_controller_listen("https://example.com:9090/path")

    def test_install_provider_applies_group_and_mode(self):
        group_name = grp.getgrgid(os.getgid()).gr_name
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            settings = {
                "home_dir": str(base / "home"),
                "state_dir": str(base / "state"),
                "provider_group": group_name,
            }

            provider_file = sub.install_provider(
                settings,
                b"proxies: []\n",
                {"main": b"payload: []\n"},
                dry_run=False,
            )

            stat_result = provider_file.stat()
            self.assertEqual(stat_result.st_mode & 0o777, 0o640)
            self.assertEqual(stat_result.st_gid, os.getgid())
            cache_file = base / "state" / "cache" / "main.yaml"
            self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)

    def test_install_provider_keeps_0600_when_group_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            settings = {
                "home_dir": str(base / "home"),
                "state_dir": str(base / "state"),
                "provider_group": "definitely-not-a-group-xyz",
            }

            provider_file = sub.install_provider(
                settings,
                b"proxies: []\n",
                {},
                dry_run=False,
            )

            self.assertEqual(provider_file.stat().st_mode & 0o777, 0o600)

    def test_validation_allows_absolute_external_ui(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            home = base / "home"
            home.mkdir()
            config_file = home / "config.yaml"
            config_file.write_text(
                yaml.safe_dump(
                    {
                        "external-ui": "/usr/share/metacubexd",
                        "proxy-providers": {
                            "subscriptions": {
                                "type": "file",
                                "path": "./providers/subscriptions.yaml",
                            }
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            settings = {
                "mihomo_binary": "/usr/bin/mihomo",
                "home_dir": str(home),
                "config_file": str(config_file),
            }

            completed = subprocess.CompletedProcess([], 0, stdout="")
            with mock.patch.object(sub.subprocess, "run", return_value=completed) as run:
                sub.validate_with_mihomo(settings, b"proxies: []\n")

            validation_environment = run.call_args.kwargs["env"]
            self.assertIn(
                "/usr/share/metacubexd",
                validation_environment["SAFE_PATHS"].split(os.pathsep),
            )

    def test_reload_falls_back_to_restart_when_not_supported(self):
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[1] == "show":
                return subprocess.CompletedProcess(cmd, 0, stdout="no\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        with mock.patch.object(sub.subprocess, "run", side_effect=fake_run):
            sub.reload_mihomo({"service_name": "mihomo.service"}, no_reload=False)

        self.assertEqual(calls[-1][:2], ["systemctl", "restart"])

    def test_reload_uses_reload_when_supported(self):
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[1] == "show":
                return subprocess.CompletedProcess(cmd, 0, stdout="yes\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        with mock.patch.object(sub.subprocess, "run", side_effect=fake_run):
            sub.reload_mihomo({"service_name": "mihomo.service"}, no_reload=False)

        self.assertEqual(calls[-1][:2], ["systemctl", "reload"])


if __name__ == "__main__":
    unittest.main()
