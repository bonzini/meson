# SPDX-License-Identifier: Apache-2.0
# Copyright © 2022-2023 Intel Corporation

from __future__ import annotations
import unittest
import os
import tempfile
import textwrap
import typing as T

from mesonbuild.cargo import builder, cfg, load_wraps
from mesonbuild.cargo.cfg import TokenType
from mesonbuild.cargo.manifest import Manifest
from mesonbuild.cargo.toml import load_toml
from mesonbuild.cargo.validate import validator, typeddict_validator
from mesonbuild.cargo.version import convert


class CargoVersionTest(unittest.TestCase):

    def test_cargo_to_meson(self) -> None:
        cases: T.List[T.Tuple[str, T.List[str]]] = [
            # Basic requirements
            ('>= 1', ['>= 1']),
            ('> 1', ['> 1']),
            ('= 1', ['= 1']),
            ('< 1', ['< 1']),
            ('<= 1', ['<= 1']),

            # tilde tests
            ('~1', ['>= 1', '< 2']),
            ('~1.1', ['>= 1.1', '< 1.2']),
            ('~1.1.2', ['>= 1.1.2', '< 1.2.0']),

            # Wildcards
            ('*', []),
            ('1.*', ['>= 1', '< 2']),
            ('2.3.*', ['>= 2.3', '< 2.4']),

            # Unqualified
            ('2', ['>= 2', '< 3']),
            ('2.4', ['>= 2.4', '< 3']),
            ('2.4.5', ['>= 2.4.5', '< 3']),
            ('0.0.0', ['< 1']),
            ('0.0', ['< 1']),
            ('0', ['< 1']),
            ('0.0.5', ['>= 0.0.5', '< 0.0.6']),
            ('0.5.0', ['>= 0.5.0', '< 0.6']),
            ('0.5', ['>= 0.5', '< 0.6']),
            ('1.0.45', ['>= 1.0.45', '< 2']),

            # Caret (Which is the same as unqualified)
            ('^2', ['>= 2', '< 3']),
            ('^2.4', ['>= 2.4', '< 3']),
            ('^2.4.5', ['>= 2.4.5', '< 3']),
            ('^0.0.0', ['< 1']),
            ('^0.0', ['< 1']),
            ('^0', ['< 1']),
            ('^0.0.5', ['>= 0.0.5', '< 0.0.6']),
            ('^0.5.0', ['>= 0.5.0', '< 0.6']),
            ('^0.5', ['>= 0.5', '< 0.6']),

            # Multiple requirements
            ('>= 1.2.3, < 1.4.7', ['>= 1.2.3', '< 1.4.7']),
        ]

        for (data, expected) in cases:
            with self.subTest():
                self.assertListEqual(convert(data), expected)


class CargoCfgTest(unittest.TestCase):

    def test_lex(self) -> None:
        cases: T.List[T.Tuple[str, T.List[T.Tuple[TokenType, T.Optional[str]]]]] = [
            ('"unix"', [(TokenType.STRING, 'unix')]),
            ('unix', [(TokenType.IDENTIFIER, 'unix')]),
            ('not(unix)', [
                (TokenType.NOT, None),
                (TokenType.LPAREN, None),
                (TokenType.IDENTIFIER, 'unix'),
                (TokenType.RPAREN, None),
            ]),
            ('any(unix, windows)', [
                (TokenType.ANY, None),
                (TokenType.LPAREN, None),
                (TokenType.IDENTIFIER, 'unix'),
                (TokenType.COMMA, None),
                (TokenType.IDENTIFIER, 'windows'),
                (TokenType.RPAREN, None),
            ]),
            ('target_arch = "x86_64"', [
                (TokenType.IDENTIFIER, 'target_arch'),
                (TokenType.EQUAL, None),
                (TokenType.STRING, 'x86_64'),
            ]),
            ('all(target_arch = "x86_64", unix)', [
                (TokenType.ALL, None),
                (TokenType.LPAREN, None),
                (TokenType.IDENTIFIER, 'target_arch'),
                (TokenType.EQUAL, None),
                (TokenType.STRING, 'x86_64'),
                (TokenType.COMMA, None),
                (TokenType.IDENTIFIER, 'unix'),
                (TokenType.RPAREN, None),
            ]),
            ('cfg(windows)', [
                (TokenType.CFG, None),
                (TokenType.LPAREN, None),
                (TokenType.IDENTIFIER, 'windows'),
                (TokenType.RPAREN, None),
            ]),
        ]
        for data, expected in cases:
            with self.subTest():
                self.assertListEqual(list(cfg.lexer(data)), expected)

    def test_parse(self) -> None:
        cases = [
            ('target_os = "windows"', cfg.Equal(cfg.Identifier("target_os"), cfg.String("windows"))),
            ('target_arch = "x86"', cfg.Equal(cfg.Identifier("target_arch"), cfg.String("x86"))),
            ('target_family = "unix"', cfg.Equal(cfg.Identifier("target_family"), cfg.String("unix"))),
            ('any(target_arch = "x86", target_arch = "x86_64")',
                cfg.Any(
                    [
                        cfg.Equal(cfg.Identifier("target_arch"), cfg.String("x86")),
                        cfg.Equal(cfg.Identifier("target_arch"), cfg.String("x86_64")),
                    ])),
            ('all(target_arch = "x86", target_os = "linux")',
                cfg.All(
                    [
                        cfg.Equal(cfg.Identifier("target_arch"), cfg.String("x86")),
                        cfg.Equal(cfg.Identifier("target_os"), cfg.String("linux")),
                    ])),
            ('not(all(target_arch = "x86", target_os = "linux"))',
                cfg.Not(
                    cfg.All(
                        [
                            cfg.Equal(cfg.Identifier("target_arch"), cfg.String("x86")),
                            cfg.Equal(cfg.Identifier("target_os"), cfg.String("linux")),
                        ]))),
            ('cfg(all(any(target_os = "android", target_os = "linux"), any(custom_cfg)))',
                cfg.All([
                    cfg.Any([
                        cfg.Equal(cfg.Identifier("target_os"), cfg.String("android")),
                        cfg.Equal(cfg.Identifier("target_os"), cfg.String("linux")),
                    ]),
                    cfg.Any([
                        cfg.Identifier("custom_cfg"),
                    ]),
                ])),
        ]
        for data, expected in cases:
            with self.subTest():
                self.assertEqual(cfg.parse(iter(cfg.lexer(data))), expected)

    def test_eval_ir(self) -> None:
        d = {
            'target_os': 'unix',
            'unix': '',
        }
        cases = [
            ('target_os = "windows"', False),
            ('target_os = "unix"', True),
            ('doesnotexist = "unix"', False),
            ('not(target_os = "windows")', True),
            ('any(target_os = "windows", target_arch = "x86_64")', False),
            ('any(target_os = "windows", target_os = "unix")', True),
            ('all(target_os = "windows", target_os = "unix")', False),
            ('all(not(target_os = "windows"), target_os = "unix")', True),
            ('any(unix, windows)', True),
            ('all()', True),
            ('any()', False),
            ('cfg(unix)', True),
            ('cfg(windows)', False),
        ]
        for data, expected in cases:
            with self.subTest():
                value = cfg.eval_cfg(data, d)
                self.assertEqual(value, expected)

class CargoLockTest(unittest.TestCase):
    def test_cargo_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'Cargo.lock'), 'w', encoding='utf-8') as f:
                f.write(textwrap.dedent('''\
                    version = 3
                    [[package]]
                    name = "foo"
                    version = "0.1"
                    source = "registry+https://github.com/rust-lang/crates.io-index"
                    checksum = "8a30b2e23b9e17a9f90641c7ab1549cd9b44f296d3ccbf309d2863cfe398a0cb"
                    [[package]]
                    name = "bar"
                    version = "0.1"
                    source = "git+https://github.com/gtk-rs/gtk-rs-core?branch=0.19#23c5599424cc75ec66618891c915d9f490f6e4c2"
                    '''))
            wraps = load_wraps(tmpdir, 'subprojects')
            self.assertEqual(len(wraps), 2)
            self.assertEqual(wraps[0].name, 'foo-0.1-rs')
            self.assertEqual(wraps[0].directory, 'foo-0.1')
            self.assertEqual(wraps[0].type, 'file')
            self.assertEqual(wraps[0].get('method'), 'cargo')
            self.assertEqual(wraps[0].get('source_url'), 'https://crates.io/api/v1/crates/foo/0.1/download')
            self.assertEqual(wraps[0].get('source_hash'), '8a30b2e23b9e17a9f90641c7ab1549cd9b44f296d3ccbf309d2863cfe398a0cb')
            self.assertEqual(wraps[1].name, 'bar-0.1-rs')
            self.assertEqual(wraps[1].directory, 'bar')
            self.assertEqual(wraps[1].type, 'git')
            self.assertEqual(wraps[1].get('method'), 'cargo')
            self.assertEqual(wraps[1].get('url'), 'https://github.com/gtk-rs/gtk-rs-core')
            self.assertEqual(wraps[1].get('revision'), '23c5599424cc75ec66618891c915d9f490f6e4c2')

class CargoTomlTest(unittest.TestCase):
    CARGO_TOML_1 = textwrap.dedent('''\
        [package]
        name = "mandelbrot"
        version = "0.1.0"
        authors = ["Sebastian Dröge <sebastian@centricular.com>"]
        edition = "2018"
        license = "GPL-3.0"

        [package.metadata.docs.rs]
        all-features = true
        rustc-args = [
            "--cfg",
            "docsrs",
        ]
        rustdoc-args = [
            "--cfg",
            "docsrs",
            "--generate-link-to-definition",
        ]

        [dependencies]
        gtk = { package = "gtk4", version = "0.9" }
        num-complex = "0.4"
        rayon = "1.0"
        once_cell = "1"
        async-channel = "2.0"
        zerocopy = { version = "0.7", features = ["derive"] }

        [dev-dependencies.gir-format-check]
        version = "^0.1"
        ''')

    CARGO_TOML_2 = textwrap.dedent('''\
        [package]
        name = "pango"
        edition = "2021"
        rust-version = "1.70"
        version = "0.20.4"
        authors = ["The gtk-rs Project Developers"]

        [package.metadata.system-deps.pango]
        name = "pango"
        version = "1.40"

        [package.metadata.system-deps.pango.v1_42]
        version = "1.42"

        [lib]
        name = "pango"

        [[test]]
        name = "check_gir"
        path = "tests/check_gir.rs"

        [features]
        v1_42 = ["pango-sys/v1_42"]
        v1_44 = [
            "v1_42",
            "pango-sys/v1_44",
        ]
    ''')

    def test_cargo_toml_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'Cargo.toml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(self.CARGO_TOML_1)
            manifest_toml = load_toml(fname)
            manifest = Manifest.from_raw(manifest_toml, 'Cargo.toml')

        self.assertEqual(manifest.package.name, "mandelbrot")
        self.assertEqual(manifest.package.version, "0.1.0")
        self.assertEqual(manifest.package.authors[0], "Sebastian Dröge <sebastian@centricular.com>")
        self.assertEqual(manifest.package.edition, "2018")
        self.assertEqual(manifest.package.license, "GPL-3.0")

        print(manifest.package.metadata)
        self.assertEqual(len(manifest.package.metadata), 1)

    def test_cargo_toml_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'Cargo.toml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(self.CARGO_TOML_1)
            manifest_toml = load_toml(fname)
            manifest = Manifest.from_raw(manifest_toml, 'Cargo.toml')

        self.assertEqual(len(manifest.dependencies), 6)
        self.assertEqual(manifest.dependencies["gtk"].package, "gtk4")
        self.assertEqual(manifest.dependencies["gtk"].version, [">= 0.9", "< 0.10"])
        self.assertEqual(manifest.dependencies["gtk"].api, "0.9")
        self.assertEqual(manifest.dependencies["num-complex"].package, "num-complex")
        self.assertEqual(manifest.dependencies["num-complex"].version, [">= 0.4", "< 0.5"])
        self.assertEqual(manifest.dependencies["num-complex"].api, "0.4")
        self.assertEqual(manifest.dependencies["rayon"].package, "rayon")
        self.assertEqual(manifest.dependencies["rayon"].version, [">= 1.0", "< 2"])
        self.assertEqual(manifest.dependencies["rayon"].api, "1")
        self.assertEqual(manifest.dependencies["once_cell"].package, "once_cell")
        self.assertEqual(manifest.dependencies["once_cell"].version, [">= 1", "< 2"])
        self.assertEqual(manifest.dependencies["once_cell"].api, "1")
        self.assertEqual(manifest.dependencies["async-channel"].package, "async-channel")
        self.assertEqual(manifest.dependencies["async-channel"].version, [">= 2.0", "< 3"])
        self.assertEqual(manifest.dependencies["async-channel"].api, "2")
        self.assertEqual(manifest.dependencies["zerocopy"].package, "zerocopy")
        self.assertEqual(manifest.dependencies["zerocopy"].version, [">= 0.7", "< 0.8"])
        self.assertEqual(manifest.dependencies["zerocopy"].features, ["derive"])
        self.assertEqual(manifest.dependencies["zerocopy"].api, "0.7")

        self.assertEqual(len(manifest.dev_dependencies), 1)
        self.assertEqual(manifest.dev_dependencies["gir-format-check"].package, "gir-format-check")
        self.assertEqual(manifest.dev_dependencies["gir-format-check"].version, [">= 0.1", "< 0.2"])
        self.assertEqual(manifest.dev_dependencies["gir-format-check"].api, "0.1")

    def test_cargo_toml_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'Cargo.toml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(self.CARGO_TOML_2)
            manifest_toml = load_toml(fname)
            manifest = Manifest.from_raw(manifest_toml, 'Cargo.toml')

        self.assertEqual(manifest.lib.name, "pango")
        self.assertEqual(manifest.lib.crate_type, ["lib"])
        self.assertEqual(manifest.lib.path, "src/lib.rs")
        self.assertEqual(manifest.lib.test, True)
        self.assertEqual(manifest.lib.doctest, True)
        self.assertEqual(manifest.lib.bench, True)
        self.assertEqual(manifest.lib.doc, True)
        self.assertEqual(manifest.lib.harness, True)
        self.assertEqual(manifest.lib.edition, "2015")
        self.assertEqual(manifest.lib.required_features, [])
        self.assertEqual(manifest.lib.plugin, False)
        self.assertEqual(manifest.lib.proc_macro, False)
        self.assertEqual(manifest.lib.doc_scrape_examples, True)

        self.assertEqual(len(manifest.test), 1)
        self.assertEqual(manifest.test[0].name, "check_gir")
        self.assertEqual(manifest.test[0].crate_type, ["lib"])
        self.assertEqual(manifest.test[0].path, "tests/check_gir.rs")
        self.assertEqual(manifest.test[0].test, True)
        self.assertEqual(manifest.test[0].doctest, False)
        self.assertEqual(manifest.test[0].bench, True)
        self.assertEqual(manifest.test[0].doc, False)
        self.assertEqual(manifest.test[0].harness, True)
        self.assertEqual(manifest.test[0].edition, "2015")
        self.assertEqual(manifest.test[0].required_features, [])
        self.assertEqual(manifest.test[0].plugin, False)

    def test_cargo_toml_system_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'Cargo.toml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(self.CARGO_TOML_2)
            manifest_toml = load_toml(fname)
            manifest = Manifest.from_raw(manifest_toml, 'Cargo.toml')

        self.assertIn('system-deps', manifest.package.metadata)

        self.assertEqual(len(manifest.system_dependencies), 1)
        self.assertEqual(manifest.system_dependencies["pango"].name, "pango")
        self.assertEqual(manifest.system_dependencies["pango"].version, [">=1.40"])
        self.assertEqual(manifest.system_dependencies["pango"].optional, False)
        self.assertEqual(manifest.system_dependencies["pango"].feature, None)

        self.assertEqual(len(manifest.system_dependencies["pango"].feature_overrides), 1)
        self.assertEqual(manifest.system_dependencies["pango"].feature_overrides["v1_42"], {"version": "1.42"})

    def test_cargo_toml_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'Cargo.toml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(self.CARGO_TOML_2)
            manifest_toml = load_toml(fname)
            manifest = Manifest.from_raw(manifest_toml, 'Cargo.toml')

        self.assertEqual(len(manifest.features), 3)
        self.assertEqual(manifest.features["v1_42"], ["pango-sys/v1_42"])
        self.assertEqual(manifest.features["v1_44"], ["v1_42", "pango-sys/v1_44"])
        self.assertEqual(manifest.features["default"], [])


class A:
    pass


class TypedDictExample(T.TypedDict, total=False):
    name: str
    version: str


class TypedDictReq(T.TypedDict, total=False):
    name: T.Required[str]
    version: str


class TypedDictTotal(T.TypedDict):
    name: T.Required[str]
    version: str


class ValidatorTest(unittest.TestCase):

    def test_validator(self):
        assert validator(bool)(True)
        assert not validator(bool)('')
        assert not validator(bool)('abc')

        assert validator(float)(1)

        assert validator(T.List)([])
        assert validator(T.List)(['abc'])
        assert validator(T.List)(['abc', 'def'])
        assert validator(T.List[str])(['abc', 'def'])
        assert not validator(T.List[int])(['abc', 'def'])
        assert not validator(T.List[int])([123, 'def'])
        assert not validator(T.List[str])([123, 'def'])
        assert not validator(T.List[int])(['abc', 'def'])
        assert not validator(T.List[int])([123, 'def'])
        assert not validator(T.List[str])([123, 'def'])

        assert validator(T.Optional[int])(123)
        assert validator(T.Optional[int])(None)
        assert not validator(int)(None)

        assert validator(T.Union[str, int])(123)
        assert validator(T.Union[str, int])('abc')
        assert not validator(T.Union[str, int])([])
        assert not validator(T.Union[str, int])(['abc'])

        assert validator(T.Dict[str, int])({'abc': 123})
        assert not validator(T.Dict[str, int])({'abc': 'abc'})

        assert validator(T.Mapping[str, int])({'abc': 123})
        assert not validator(T.Mapping[str, int])({'abc': 'abc'})

        assert not validator(T.Tuple[int])(123)
        assert validator(T.Tuple[int])((123, ))
        assert not validator(T.Tuple[int])((123, 456))
        assert validator(T.Tuple[int, ...])((123, 456))
        assert validator(T.Tuple[int, str])((123, 'abc'))

        assert validator(T.Literal['abc', 'def'])('abc')
        assert validator(T.Literal['abc', 'def'])('def')
        assert not validator(T.Literal['abc', 'def'])('ghi')
        assert not validator(T.Literal['abc', 'def'])(123)

        assert validator(T.Type)(A)
        assert not validator(T.Type)(A())
        assert validator(T.Type[A])(A)
        assert not validator(T.Type[A])(A())

        assert validator(A)(A())
        assert not validator(A)(A)

    def test_typeddict_validator(self):
        assert validator(TypedDictExample)({})
        assert validator(TypedDictExample)({'name': 'abc'})
        assert validator(TypedDictExample)({'name': 'abc', 'extra': 123})
        assert not validator(TypedDictExample)({'name': 123})

        assert not validator(TypedDictReq)({})
        assert validator(TypedDictReq)({'name': 'abc'})
        assert validator(TypedDictReq)({'name': 'abc', 'extra': 123})

        assert not validator(TypedDictTotal)({})
        assert validator(TypedDictTotal)({'name': 'abc'})
        assert not validator(TypedDictTotal)({'name': 'abc', 'extra': 123})
