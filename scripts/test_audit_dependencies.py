"""Tests for the separate Python >=3.11 security tooling."""

import unittest

from audit_dependencies import audit_status, locked_requirements, requirement_batches


class AuditTests(unittest.TestCase):
    def test_batches_retain_every_version_without_duplicate_names(self):
        packages = {("a", "1"), ("a", "2"), ("b", "1")}
        batches = requirement_batches(packages)
        self.assertEqual(set.union(*batches), packages)
        self.assertEqual(len(batches), 2)
        for batch in batches:
            self.assertEqual(len(batch), len({name for name, _ in batch}))

    def test_all_versions_and_platforms_are_included(self):
        lock = {
            "package": [
                {"name": "rhinestone", "version": "0.1.1", "source": {"editable": "."}},
                {"name": "a", "version": "1", "source": {"registry": "pypi"}},
                {"name": "a", "version": "2", "source": {"registry": "pypi"}},
                {
                    "name": "windows-only",
                    "version": "1",
                    "source": {"registry": "pypi"},
                },
            ]
        }
        self.assertEqual(
            locked_requirements(lock), {("a", "1"), ("a", "2"), ("windows-only", "1")}
        )

    def test_non_registry_dependency_is_not_silently_skipped(self):
        with self.assertRaises(ValueError):
            locked_requirements({"package": [{"name": "a", "source": {"git": "url"}}]})

    def test_empty_lock_fails(self):
        with self.assertRaises(ValueError):
            locked_requirements({"package": []})

    def test_clean_report(self):
        self.assertEqual(
            audit_status(
                {"dependencies": [{"name": "a", "version": "1", "vulns": []}]},
                {("a", "1")},
                0,
            ),
            0,
        )

    def test_findings(self):
        self.assertEqual(
            audit_status(
                {
                    "dependencies": [
                        {"name": "a", "version": "1", "vulns": [{"id": "example"}]}
                    ]
                },
                {("a", "1")},
                1,
            ),
            1,
        )

    def test_missing_or_skipped_package_fails(self):
        for dependencies in (
            [],
            [{"name": "a", "version": "1", "skip_reason": "unavailable"}],
        ):
            with self.assertRaises(ValueError):
                audit_status({"dependencies": dependencies}, {("a", "1")}, 0)

    def test_network_failure_is_not_reported_as_vulnerabilities(self):
        with self.assertRaises(ValueError):
            audit_status(
                {"dependencies": [{"name": "a", "version": "1", "vulns": []}]},
                {("a", "1")},
                1,
            )


if __name__ == "__main__":
    unittest.main()
