#!/usr/bin/env python3
#
# fsl-maintenance - A helper script to maintain the Security Lab package list
# and other relevant maintenance tasks.
#
# Copyright (c) 2012-2018 Fabian Affolter <fab@fedoraproject.org>
#
# All rights reserved.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Credits goes to Robert Scheck. He did a lot brain work for the initial
# approach. This script is heavy based on his Perl scripts.
import argparse
import operator
import itertools
import datetime
import re
import sys
import os
try:
    import columnize
except ImportError:
    print("Please install pycolumnize first -> sudo dnf -y install python3-columnize")
import dnf
try:
    import git
except ImportError:
    print("Please install GitPython first -> sudo dnf -y install python3-GitPython")
try:
    import yaml
except ImportError:
    print("Please install PyYAML first -> sudo dnf -y install PyYAML")
try:
    import click
except ImportError:
    print("Please install click first -> sudo dnf -y install python3-click")

DEFAULT_FILENAME = 'pkglist.yaml'
repo = git.Repo(os.getcwd())


def getPackages():
    """Read YAML package file and return all packages."""
    file = open(DEFAULT_FILENAME, 'r')
    pkgslist = yaml.safe_load(file)
    file.close()
    return pkgslist

@click.group()
@click.version_option()
def cli():
    """fsl-maintenance

    This tool can be used for maintaining the Fedora Security Lab package list.
    """


@cli.group()
def display():
    """Display the details about the packages."""


@display.command('full')
def full():
    """All included tools and details will be printed to STDOUT."""
    pkgslist = getPackages()

    pkgslistIn = []
    pkgslistEx = []
    pkgslistAll = []

    # All packages
    pkgslistAll = []
    for pkg in pkgslist:
        pkgslistAll.append(pkg['pkg'])

    # Split list of packages into included and excluded packages
    # Not used at the moment
    #for pkg in pkgslist:
    #    if 'exclude' in pkg:
    #        pkgslistEx.append(pkg['pkg'])
    #    else:
    #        pkgslistIn.append(pkg['pkg'])

    # Displays the details to STDOUT
    print("\nDetails about the packages in the Fedora Security Lab.\n")
    print("Packages in comps               : ", len(pkgslist))
    #print("Packages included in live media : ", len(pkgslistIn))
    print("\nPackage listing:")
    sorted_pkgslist = sorted(pkgslistAll)
    print(columnize.columnize(sorted_pkgslist, displaywidth=72))


@display.command('raw')
def raw():
    """The pkglist.yaml file will be printed to STDOUT."""
    pkgslist = getPackages()
    print(yaml.dump(pkgslist))


@display.command('short')
def short():
    """Only show the absolute minimum about the package list."""
    pkgslist = getPackages()

    # Displays the details to STDOUT
    print("\nDetails about the packages in the Fedora Security Lab\n")
    print("Packages in comps               : ", len(pkgslist))
    print("\nTo see all available options use -h or --help.")


@cli.group()
def output():
    """Create various output from the package list."""


@output.command('comps')
def comps():
    """
    Generates the entries to include into the comps-fXX.xml.in file.
    <packagelist>
      ...
    </packagelist>
    """
    pkgslist = getPackages()
    # Split list of packages into eincluded and excluded packages
    sorted_pkgslist = sorted(pkgslist, key=operator.itemgetter('pkg'))
    for pkg in sorted_pkgslist:
        entry = '      <packagereq type="default">{}</packagereq>'.format(pkg['pkg'])
        print(entry)


@output.command('playbook')
def playbook():
    """Generate an Ansible playbook for the installation."""
    pkgslist = getPackages()

    part1 = """# This playbook installs all Fedora Security Lab packages.
#
# Copyright (c) 2013-2018 Fabian Affolter <fab@fedoraproject.org>
#
# All rights reserved.
# This file is licensed under GPLv2, for more details check COPYING.
#
# Generated by fsl-maintenance.py at %s
#
# Usage: ansible-playbook fsl-packages.yml -f 10

---
- hosts: fsl_hosts
  user: root
  tasks:
  - name: install all packages from the FSL
    dnf: pkg={{ item }}
         state=present
    with_items:\n""" % (datetime.date.today())

    # Split list of packages into included and excluded packages
    sorted_pkgslist = sorted(pkgslist, key=operator.itemgetter('pkg'))

    # Write the playbook files
    fileOut = open('ansible-playbooks/fsl-packages.yml', 'w')
    fileOut.write(part1)
    for pkg in sorted_pkgslist:
        fileOut.write('       - %s\n' %  pkg['pkg'])
    fileOut.close()

    # Commit the changed file to the repository
    repo.git.add('ansible-playbooks/fsl-packages.yml')
    repo.git.commit(m='Update playbook')
    repo.git.push()


@output.command('live')
def live():
    """Generate the exclude list for the kickstart file."""
    pkgslist = getPackages()
    # Split list of packages into included and excluded packages
    sorted_pkgslist = sorted(pkgslist, key=operator.itemgetter('pkg'))

    for pkg in sorted_pkgslist:
        if pkg['exclude'] == 1:
            print("- ", pkg['pkg'])

@output.command('menus')
def menus():
    """Generate the .desktop files which are used for the menu structure."""
    pkgslist = getPackages()
    # Terminal is the standard terminal application of the Xfce desktop
    terminal = 'xfce4-terminal'

    # Collects all files in the directory
    filelist = []
    os.chdir('security-menu')
    for files in os.listdir("."):
        if files.endswith(".desktop"):
            filelist.append(files)
    # Write the .desktop files
    for pkg in pkgslist:
        if 'command' and 'name' in pkg:
            file_out = open('security-{}.desktop'.format(pkg['pkg']), 'w')
            file_out.write('[Desktop Entry]\n')
            file_out.write('Name={}\n'.format(pkg['name']))
            file_out.write("Exec={} -e \"su -c '{}; bash'\"\n".format(
                terminal, pkg['command']))
            file_out.write('TryExec={}\n'.format(pkg['pkg']))
            file_out.write('Type=Application\n')
            file_out.write('Categories=System;Security;X-SecurityLab;'
                          'X-{};\n'.format(pkg['category']))
            file_out.close()

    # Compare the needed .desktop file against the included packages, remove
    # .desktop files from exclude packages
    dellist = filelist
    for pkg in pkgslist:
            if 'command' in pkg:
                dellist.remove('security-{}.desktop'.format(pkg['pkg']))
            if 'exclude' in pkg:
                if pkg['exclude'] == 1:
                    dellist.append('security-{}.desktop'.format(pkg['pkg']))

    # Remove the .desktop files which are no longer needed
    if len(dellist) != 0:
        for file in dellist:
            os.remove(file)

if __name__ == '__main__':
    cli()

