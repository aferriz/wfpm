# -*- coding: utf-8 -*-

"""
    Copyright (c) 2021, Ontario Institute for Cancer Research (OICR).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Authors:
        Junjun Zhang <junjun.zhang@oicr.on.ca>
"""

import os
import sys
from click import echo
from wfpm.project import Project


def workon_cmd(
    project: Project = None,
    pkg: str = None,
    stop: bool = False
):
    if stop and pkg:
        echo("When '-s' is used, no pkg argument can be supplied.")
        sys.exit(1)

    if pkg is None and not stop:
        display_pkg_info(project)
        sys.exit()

    if stop:
        stop_workon(project)
        sys.exit()

    if project.pkg_workon and (pkg == project.pkg_workon or pkg == project.pkg_workon.split('@')[0]):
        echo(f"Working on '{project.pkg_workon}'")

    elif pkg in project.pkgs_in_dev:
        project.set_workon(pkg)
        echo(f"Now work on '{pkg}'")

    elif pkg in project.git.rel_candidates:
        if len(project.git.rel_candidates[pkg]) == 1:
            workon_pkg = '@'.join([pkg, project.git.rel_candidates[pkg][0]])
            project.set_workon(workon_pkg)
            echo(f"Now work on '{workon_pkg}'")

        else:
            echo(f"Multiple versions of the package are in development: {', '.join(project.git.rel_candidates[pkg])}")

            workon_pkg_1 = '@'.join([pkg, project.git.rel_candidates[pkg][0]])
            workon_pkg_2 = '@'.join([pkg, project.git.rel_candidates[pkg][1]])
            echo("Please specify which version to work on, eg, ", nl=False)
            echo(f"'wfpm workon {workon_pkg_1}' or 'wfpm workon {workon_pkg_2}'")

    else:
        echo(f"Not a package in development: '{pkg}'")


def display_pkg_info(project=None):
    echo(f"Package being worked on: {project.pkg_workon if project.pkg_workon else '<none>'}")

    echo("Packages in development:", nl=False)
    if not project.git.rel_candidates:
        echo(" <none>")
    else:
        echo("")

    for pkg in sorted(project.git.rel_candidates):
        echo(f"  {pkg}: ", nl=False)
        echo(', '.join(project.git.rel_candidates[pkg]))

    echo("Packages released:", nl=False)
    if not project.git.releases:
        echo(" <none>")
    else:
        echo("")

    for pkg in sorted(project.git.releases):
        echo(f"  {pkg}: ", nl=False)
        echo(', '.join(project.git.releases[pkg]))


def stop_workon(project=None):
    if project.pkg_workon:
        if os.getcwd() != project.root:
            echo("Must run this command under project root dir.")
            sys.exit(1)

        if not project.git.branch_clean():
            echo(f"Package branch '{project.pkg_workon}' not clean, please complete on-going work and commit changes.")
            sys.exit(1)

        project.git.cmd_checkout_branch('main')
        echo(f"Stopped work on {project.pkg_workon}")

    else:
        echo("Not working on any package.")
