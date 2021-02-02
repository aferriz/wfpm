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
import re
import json
import tempfile
import random
import string
import questionary
from shutil import copytree
from collections import OrderedDict
from click import echo
from cookiecutter.main import cookiecutter
from wfpm import PKG_NAME_REGEX
from ..pkg_templates import tool_tmplt
from ..pkg_templates import workflow_tmplt
from ..pkg_templates import function_tmplt
from ..utils import run_cmd
from .install_cmd import install_cmd


def new_cmd(ctx, pkg_type, pkg_name, conf_json=None):
    project = ctx.obj['PROJECT']
    if not project.root:
        echo("Not in a package project directory.")
        ctx.abort()

    if project.root != os.getcwd():
        echo(f"Must run this command under the project root dir: {project.root}")
        ctx.abort()

    if not re.match(PKG_NAME_REGEX, pkg_name):
        echo(f"'{pkg_name}' is not a valid package name, expected name pattern: '{PKG_NAME_REGEX}'")
        ctx.abort()

    if os.path.isdir(os.path.join(project.root, pkg_name)):
        echo(f"Package '{ pkg_name }' already exists.")
        ctx.abort()

    name_parts = pkg_name.split('-')
    workflow_name = ''.join([p.capitalize() for p in name_parts])  # workflow name starts with upper
    process_name = workflow_name[0].lower() + workflow_name[1:]  # tool/function name starts with lower

    if pkg_type == 'tool':
        extra_context = {
            '_pkg_name': pkg_name,
            '_repo_type': project.repo_type,
            '_repo_server': project.repo_server,
            '_repo_account': project.repo_account,
            '_repo_name': project.name,
            '_license': project.license,
            '_name': process_name
        }

        template = tool_tmplt

    elif pkg_type == 'workflow':
        extra_context = {
            '_pkg_name': pkg_name,
            '_repo_type': project.repo_type,
            '_repo_server': project.repo_server,
            '_repo_account': project.repo_account,
            '_repo_name': project.name,
            '_license': project.license,
            '_name': workflow_name
        }

        template = workflow_tmplt

    elif pkg_type == 'function':
        template = function_tmplt

        echo("Not implemented yet")
        ctx.exit()

    path = gen_template(
            ctx,
            project,
            template=template,
            pkg_name=pkg_name,
            extra_context=extra_context,
            conf_json=conf_json
        )

    # create symlinks for 'wfpr_modules'
    cmd = f"cd {path} && ln -s ../wfpr_modules && cd tests && ln -s ../wfpr_modules"
    run_cmd(cmd)
    echo(f"New package created in: {os.path.basename(path)}")

    # start installation of dependencies
    # TODO: temp solution here, should have better way to know whether there are dependencies
    # need to be installed
    os.chdir(path)
    install_cmd(ctx)


def gen_template(
    ctx,
    project=None,
    template=None,
    pkg_name=None,
    extra_context=None,
    conf_json=None
):
    """
    generate template in a temp dir by calling cookiecutter, then perform necessary post-gen
    check and processing, finally copy the template into the current project root dir
    """
    pkg_type = os.path.basename(template)
    conf_dict = {}
    if conf_json:
        conf_dict = json.load(conf_json)
        # TODO: validate of user supplied config JSON

        if pkg_type == 'tool' and conf_dict.get("container_registry", "") == "ghcr.io":
            conf_dict['registry_account'] = project.repo_account

    else:
        conf_dict = collect_new_pkg_info(ctx, project, template)

    hidden_fields = {
        "_pkg_name": "{{ cookiecutter._pkg_name }}",
        "_repo_account": "{{ cookiecutter._repo_account }}",
        "_repo_type": "{{ cookiecutter._repo_type }}",
        "_repo_server": "{{ cookiecutter._repo_server }}",
        "_repo_name": "{{ cookiecutter._repo_name }}",
        "_name": "{{ cookiecutter._name }}",
        "_license": "{{ cookiecutter._license }}",
        "_copy_without_render": ["*.gz"]
    }

    conf_dict = {**conf_dict, **hidden_fields}

    with tempfile.TemporaryDirectory() as tmpdirname:
        # copy template directory tree to under tmpdir so that we can replace cookiecutter.json when needed
        dirname = ''.join(random.choice(string.ascii_letters) for i in range(20))
        new_tmplt_dir = os.path.join(tmpdirname, dirname)
        copytree(template, new_tmplt_dir)

        if conf_dict:
            # replace the default cookiecutter.json with user supplied
            with open(os.path.join(new_tmplt_dir, 'cookiecutter.json'), 'w') as j:
                json.dump(conf_dict, j)

        path = cookiecutter(
                template=new_tmplt_dir,
                extra_context=extra_context,
                output_dir=tmpdirname,
                no_input=True if conf_dict else False
            )

        # fix the list fields in pkg.json
        pkg_dict = json.load(
            open(os.path.join(path, 'pkg.json')),
            object_pairs_hook=OrderedDict
        )

        pkg_dict['keywords'] = [
            d.strip() for d in pkg_dict['keywords'] if d.strip()
        ]

        pkg_dict['dependencies'] = [
            d.strip() for d in pkg_dict['dependencies'] if d.strip()
        ]

        pkg_dict['devDependencies'] = [
            d.strip() for d in pkg_dict['devDependencies'] if d.strip()
        ]

        with open(os.path.join(path, 'pkg.json'), 'w') as p:
            p.write(json.dumps(pkg_dict, indent=4))

        dest = os.path.join(os.getcwd(), pkg_name)
        copytree(path, dest)

    return dest


def collect_new_pkg_info(ctx, project=None, template=None):
    pkg_type = os.path.basename(template)

    defaults = {
        "full_name": f"{project.config.git_user_name}",
        "email": f"{project.config.git_user_email}",
        "pkg_version": "0.1.0",
    }

    if pkg_type == 'tool':
        defaults.update({
            "pkg_description": "FastQC tool",
            "keywords": "bioinformatics, seq, qc metrics",
            "docker_base_image": "pegi3s/fastqc:0.11.9",
            "container_registry": "ghcr.io",
            "registry_account": f"{project.repo_account}",
            "dependencies": "",
            "devDependencies": "",
        })
    elif pkg_type == 'workflow':
        defaults.update({
            "pkg_description": "FastQC workflow",
            "keywords": "bioinformatics, seq, qc metrics",
            "dependencies": "github.com/icgc-argo/demo-wfpkgs/demo-utils@1.1.0",
            "devDependencies": "",
        })
    elif pkg_type == 'function':
        defaults.update({
            "pkg_description": "Awesome functions",
            "keywords": "bioinformatics",
            "dependencies": "",
            "devDependencies": "",
        })

    answers_1 = questionary.form(
        full_name=questionary.text(f"Your name [{defaults['full_name']}]:", default=""),
        email=questionary.text(f"Your email [{defaults['email']}]:", default=""),
        pkg_version=questionary.text(f"Package version [{defaults['pkg_version']}]:", default=""),
        pkg_description=questionary.text(f"Package description [{defaults['pkg_description']}]:", default=""),
        keywords=questionary.text(f"Keywords (use ',' to separate keywords) [{defaults['keywords']}]:", default=""),
    ).ask()

    if not answers_1:
        ctx.abort()

    if pkg_type == 'tool':
        tool_only_answers = questionary.form(
            docker_base_image=questionary.text(
                f"Docker base image [{defaults.get('docker_base_image', '')}]:", default=""),
            container_registry=questionary.text(
                f"Container registory [{defaults.get('container_registry', '')}]:", default=""),
            registry_account=questionary.text(
                f"Container registory account [{defaults.get('registry_account', '')}]:", default=""),
        ).ask()

        if not tool_only_answers:
            ctx.abort()
    else:
        tool_only_answers = {}

    dependencies = questionary.text(
            f"Dependencies (use ',' to separate dependencies) [{defaults['dependencies']}]:", default=""
        ).ask()

    if dependencies is None:
        ctx.abort()
    elif dependencies == '':
        dependencies = defaults['dependencies']

    # TODO: validate the dependencies, format and availability

    devDependencies = questionary.text(
            f"devDependencies (use ',' to separate devDependencies) [{defaults['devDependencies']}]:", default=""
        ).ask()

    if devDependencies is None:
        ctx.abort()
    elif devDependencies == '':
        devDependencies = defaults['devDependencies']

    # TODO: validate the devDependencies, format and availability

    answers = {
        **answers_1,
        **tool_only_answers,
        'dependencies': dependencies,
        'devDependencies': devDependencies
    }

    for q in answers:
        if answers[q] == "" and defaults.get(q):
            answers[q] = defaults[q]

    echo(json.dumps(answers, indent=4))
    res = questionary.confirm("Please confirm the information and continue:", default=True).ask()

    if not res:
        ctx.abort()

    return answers
