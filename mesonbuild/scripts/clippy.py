# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 The Meson development team

from __future__ import annotations

from collections import defaultdict
import asyncio
import asyncio.subprocess
import typing as T
import os
import signal
import sys

from .. import build, mlog
from ..compilers.rust import RustCompiler
from ..mintro import get_infodir, load_info_file
from ..mtest import sh_quote, determine_worker_count, complete_all
from ..mesonlib import MachineChoice, PerMachine

class ClippyDriver:
    def __init__(self, build: build.Build):
        self.tools: PerMachine[T.List[str]] = PerMachine([], [])
        self.warned: defaultdict[str, bool] = defaultdict(lambda: False)
        for machine in MachineChoice:
            compilers = build.environment.coredata.compilers[machine]
            if 'rust' in compilers:
                compiler = compilers['rust']
                assert isinstance(compiler, RustCompiler)
                self.tools[machine] = compiler.get_rust_tool('clippy-driver', build.environment)

    def warn_missing_clippy(self, machine: str) -> None:
        if self.warned[machine]:
            return
        mlog.warning(f'clippy-driver not found for {machine} machine')
        self.warned[machine] = True

    def __call__(self, target: T.Dict[str, T.Any]) -> T.Optional[T.List[str]]:
        for src_block in target['target_sources']:
            if src_block['language'] == 'rust':
                clippy = getattr(self.tools, src_block['machine'])
                if not clippy:
                    self.warn_missing_clippy(src_block['machine'])
                    return None

                cmdlist = list(clippy)
                skip = False
                for arg in src_block['parameters']:
                    if skip:
                        skip = False
                        pass
                    elif arg in {'--emit', '--out-dir'}:
                        skip = True
                        pass
                    else:
                        cmdlist.append(arg)
                cmdlist.extend(src_block['sources'])

                return cmdlist
        return None

async def run_tool_on_targets(name: str, targets: T.List[T.Dict[str, T.Any]],
                              fn: T.Callable[[T.Dict[str, T.Any]], T.Optional[T.List[str]]]) -> int:
    futures: T.List[asyncio.Future[int]] = []
    semaphore = asyncio.Semaphore(determine_worker_count())

    async def run_subprocess(cmdlist: T.List[str]) -> int:
        """Run the command in cmdlist, buffering the output so that it is
           not mixed for multiple child processes.  Kill the child on
           cancellation."""
        p = None
        try:
            async with semaphore:
                p = await asyncio.create_subprocess_exec(*cmdlist,
                                                         stdin=asyncio.subprocess.DEVNULL,
                                                         stdout=asyncio.subprocess.PIPE,
                                                         stderr=asyncio.subprocess.STDOUT)
                stdo, _ = await p.communicate()
                if stdo:
                    quoted_cmdline = ' '.join(sh_quote(x) for x in cmdlist)
                    sys.stdout.write(str(mlog.blue('>>>')) + ' ' + quoted_cmdline + '\n')
                    sys.stdout.flush()
                    sys.stdout.buffer.write(stdo)
                    sys.stdout.buffer.flush()
                return p.returncode
        except asyncio.CancelledError:
            if p:
                p.kill()
                return p.returncode or 1
            else:
                return 0

    def sigterm_handler() -> None:
        for f in futures:
            f.cancel()

    if sys.platform != 'win32':
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, sigterm_handler)
        loop.add_signal_handler(signal.SIGTERM, sigterm_handler)

    try:
        for t in targets:
            cmdlist = fn(t)
            if cmdlist:
                futures.append(asyncio.ensure_future(run_subprocess(cmdlist)))
    finally:
        try:
            await complete_all(futures)
        except asyncio.CancelledError:
            pass

        return max(f.result() for f in futures if f.done() and not f.cancelled())

def run(args: T.List[str]) -> int:
    os.chdir(args[0])
    wd = os.getcwd()
    build_data = build.load(wd)
    targets = load_info_file(get_infodir(wd), kind='targets')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ret = asyncio.run(run_tool_on_targets('clippy', targets, ClippyDriver(build_data)))
    sys.exit(ret)
