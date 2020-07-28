import os
import argparse
import subprocess

# working directory
cwd = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--increase-memory-limit",help="increase USB-FS memory limit",action="store_true",default=False)
parser.add_argument("--memory-limit",help="ubfs memory limit to set",default=1200)
parser.add_argument("--default-grub",help="filepath for the grub config file",default='/etc/default/grub')
args = parser.parse_args()

# collect the libraries
libraries = list()
for root, folders, files in os.walk(cwd):
    for file in files:
        if file.endswith('.deb'):
            libraries.append(os.path.join(root,file))

# collect the dependencies
with open(os.path.join(cwd,'dependencies.txt')) as stream:
    dependencies = [line.strip('\n') for line in stream.readlines()]

# install the libraries
for library in libraries:
    subprocess.call(['sudo','dpkg','-i',library])

# install the dependencies
subprocess.call(['sudo','apt-get','install'] + dependencies)

# install the PySpin wheel file
wheel = os.path.join(cwd,'spinnaker_python-1.27.0.48-cp37-cp37m-linux_x86_64')
subprocess.call(['sudo','pip','install',wheel])

# modify GRUB's config file
if args.increase_memory_limit:

    with open(args.default_grub,'r') as stream:
        lines = stream.readlines()

    iline = lines.index('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n')
    lines[iline] = 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb={}"\n'.format(args.memory_limit)

    with open(args.default_grub,'w') as stream:
        stream.writelines(lines)

    subprocess.call(['sudo','update-grub'])

    # reboot
    answer = input('The computer needs to be rebooted for these changes to take effect. Reboot now? [Y/N]\n')
    if answer in ['y','Y','yes','Yes']:
        subproces.run(['reboot','now'])
