import argparse
import jsonpickle
from sys import exit
from lxml import html
from re import compile
from requests import get
from semantic_version import Version
from os import mkdir, R_OK, W_OK, access, listdir
from os.path import expanduser, join, isdir, isfile


semver = compile(
    r"^((0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(\+[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*)?)/?$")


CACHE = join(expanduser("~"), ".renutil")
INSTANCE_REGISTRY = join(CACHE, "index.json")


class ComparableVersion():

    def __init__(self, version=None):
        self.version = version

    def __repr__(self):
        return f"ComparableVersion(version={self.version})"

    def __eq__(self, other):
        return self.version == other.version

    def __ne__(self, other):
        return self.version != other.version

    def __lt__(self, other):
        return self.version < other.version

    def __le__(self, other):
        return self.version <= other.version

    def __gt__(self, other):
        return self.version > other.version

    def __ge__(self, other):
        return self.version >= other.version


class RenpyInstance(ComparableVersion):

    def __init__(self, version=None, path=None):
        super(RenpyInstance, self).__init__(version)
        self.path = path

    def __repr__(self):
        return f"RenpyInstance(version={self.version}, path='{self.path}')"


class RenpyRelease(ComparableVersion):

    def __init__(self, version=None, url=None):
        super(RenpyRelease, self).__init__(version)
        self.url = url

    def __repr__(self):
        return f"RenpyRelease(version={self.version}, url='{self.url}')"


def is_online():
    return True
    # TODO: check to see if we are completely offline or renpy.org itself is
    # down


def scan_instances(path):
    instances = []
    for folder in listdir(path):
        m = semver.match(folder)
        if m:
            version = Version(m.group(1))
            instances.append(RenpyInstance(version, folder))
    return instances


def assure_state(func):
    def wrapper(args):
        if not access(CACHE, R_OK | W_OK):
            print(f"Cache directory is not writeable:\n{CACHE}\nPlease make sure this script has permission to write to this directory.")
            exit(1)
        if not isdir(CACHE):
            print(f"Cache directory does not exist, creating it:\n{CACHE}")
            mkdir(CACHE)
        if not isfile(INSTANCE_REGISTRY):
            print(f"Instance registry does not exist, creating it:\n{INSTANCE_REGISTRY}")
            instances = scan_instances(CACHE)
            with open(INSTANCE_REGISTRY, "w") as f:
                f.write(jsonpickle.encode(instances))
        else:
            pass
            # TODO: if exists, scan for instances and add if they are not yet in the registry.
            # likewise, remove them if they are not available anymore.
        return func(args)
    return wrapper


@assure_state
def get_installed_versions(n=None):
    registry = open(INSTANCE_REGISTRY, "r")
    instances = jsonpickle.decode(registry.read())
    if n:
        return instances[:n]
    return instances


@assure_state
def get_available_versions(n=None):
    if not is_online():
        print("Could not retrieve version list: No connection could be established.")
        exit(1)
    releases = []
    r = get("https://www.renpy.org/dl/")
    tree = html.fromstring(r.content)
    links = tree.xpath("//a/text()")
    for link in links:
        m = semver.match(link)
        if not m:
            continue
        version = Version(m.group(1))
        url = "https://www.renpy.org/dl/{0}/renpy-{0}-sdk.zip".format(
            m.group(1))
        release = RenpyRelease(version, url)
        releases.append(release)
    if n:
        return sorted(releases, reverse=True)[:n]
    return sorted(releases, reverse=True)


@assure_state
def list_versions(args):
    if args.installed:
        print("Installed versions:")
        instances = get_installed_versions(args.n)
        if not instances:
            print("No instances are currently installed.")
        else:
            for release in instances:
                print(release.version)
    else:
        print("Available versions:")
        releases = get_available_versions(args.n)
        if not releases:
            print("No releases are available.")
        else:
            for release in releases:
                print(release.version)


def installed(version):
    for v in get_installed_versions():
        if v == version:
            return True
    return False


@assure_state
def install(args):
    if installed(args.version):
        print("{} is already installed!".format(args.version))
        exit(1)
    print("Installing {}".format(args.version))


@assure_state
def uninstall(args):
    if not installed(args.version):
        print("{} is not installed!".format(args.version))
        exit(1)
    print("Uninstalling {}".format(args.version))


@assure_state
def launch(args):
    if not installed(args.version):
        print("{} is not installed!".format(args.version))
        exit(1)
    print("Launching {}".format(args.version))


def main():
    parser = argparse.ArgumentParser(
        description="A toolkit for managing Ren'Py instances via the command line.")
    subparsers = parser.add_subparsers()

    parser_list = subparsers.add_parser(
        "list", help="List Ren'Py versions.")
    parser_list.add_argument(
        "-n", type=int, default=5, help="The number of versions to show")
    parser_list.add_argument(
        "--installed", action="store_true", help="Only show installed versions")
    parser_list.set_defaults(func=list_versions)

    parser_install = subparsers.add_parser(
        "install", help="Install a version of Ren'Py.")
    parser_install.add_argument(
        "version", type=str, help="The version to install")
    parser_install.set_defaults(func=install)

    parser_uninstall = subparsers.add_parser(
        "uninstall", aliases=["remove"], help="Uninstall an installed version of Ren'Py.")
    parser_uninstall.add_argument(
        "version", type=str, help="The version to uninstall")
    parser_uninstall.set_defaults(func=uninstall)

    parser_launch = subparsers.add_parser(
        "launch", help="Launch an installed version of Ren'Py.")
    parser_launch.add_argument(
        "version", type=str, help="The version to launch")
    parser_launch.set_defaults(func=launch)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
