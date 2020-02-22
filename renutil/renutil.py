### System ###
import os
import re
import sys
import shutil
import textwrap
import argparse
import requests
from zipfile import ZipFile
from stat import S_IRUSR, S_IXUSR
from contextlib import contextmanager
from subprocess import run, PIPE, Popen
from json.decoder import JSONDecodeError

### Parsing ###
import jsonpickle
from lxml import html
from semantic_version import Version

### Display ###
from tqdm import tqdm


semver = re.compile(r"^((0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(\+[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*)?)/?$")  # noqa: E501


CACHE = os.path.join(os.path.expanduser("~"), ".renutil")
INSTANCE_REGISTRY = os.path.join(CACHE, "index.json")


class ComparableVersion():

    def __init__(self, version=None):
        if isinstance(version, str):
            version = Version(version)
        self.version = version

    def __repr__(self):
        return "ComparableVersion(version={})".format(self.version)

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
        self.rapt_path = os.path.join(self.path, "rapt")
        self.launcher_path = os.path.join(self.path, "launcher")

    def __repr__(self):
        return "RenpyInstance(version={}, path='{}', launcher_path='{}')".format(self.version, self.path, self.launcher_path)  # noqa: E501


class RenpyRelease(ComparableVersion):

    def __init__(self, version=None, url=None):
        super(RenpyRelease, self).__init__(version)
        self.url = url

    def __repr__(self):
        return "RenpyRelease(version={}, url='{}')".format(self.version, self.url)


@contextmanager
def cd(dir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(dir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def is_online():
    r = requests.head("https://www.renpy.org")
    renpy_down = r.status_code == 200
    r = requests.head("https://www.google.com")
    google_down = r.status_code == 200
    if google_down and renpy_down:
        return -2
    elif renpy_down:
        return -1
    return 1


def scan_instances(path):
    instances = []
    for folder in os.listdir(path):
        m = semver.match(folder)
        if m:
            try:
                version = Version(m.group(1))
                instances.append(RenpyInstance(version, folder))
            except ValueError:
                continue
    return instances


def assure_state(func):
    def wrapper(args=None, unknown=None):
        if not os.path.isdir(CACHE):
            print("Cache directory does not exist, creating it:\n{}".format(CACHE))
            os.mkdir(CACHE)
        if not os.access(CACHE, os.R_OK | os.W_OK):
            print("Cache directory is not writeable:\n{}\nPlease make sure this script has permission to write to this directory.".format(CACHE))  # noqa: E501
            sys.exit(1)
        instances = scan_instances(CACHE)
        if not os.path.isfile(INSTANCE_REGISTRY):
            print("Instance registry does not exist, creating it:\n{}".format(INSTANCE_REGISTRY))
            with open(INSTANCE_REGISTRY, "w") as f:
                f.write(jsonpickle.encode(instances))
        else:
            for instance in instances:
                add_to_registry(instance)
        return func(args, unknown)
    return wrapper


@assure_state
def call_assure_state(args=None, unknown=None):
    pass


def get_registry(args=None, unknown=None):
    file = open(INSTANCE_REGISTRY, "r")
    try:
        registry = jsonpickle.decode(file.read())
    except JSONDecodeError:
        os.remove(INSTANCE_REGISTRY)
        call_assure_state()
        return None
    return registry


def remove_from_registry(instance):
    registry = get_registry()
    for i, inst in enumerate(registry):
        if inst.version == instance.version:
            del registry[i]
    with open(INSTANCE_REGISTRY, "w") as f:
        f.write(jsonpickle.encode(registry))


def add_to_registry(instance):
    registry = get_registry()
    if instance not in registry:
        registry.append(instance)
        with open(INSTANCE_REGISTRY, "w") as f:
            f.write(jsonpickle.encode(registry))


def get_instance(version):
    if isinstance(version, str):
        try:
            version = Version(version)
        except ValueError:
            return None
    registry = get_registry()
    for instance in registry:
        if instance.version == version:
            return instance
    return None


def valid_version(version):
    if isinstance(version, str):
        try:
            version = Version(version)
        except ValueError:
            return False
    registry = get_registry()
    for instance in registry:
        if instance.version == version:
            return True
    releases = get_available_versions()
    for release in releases:
        if release.version == version:
            return True
    return False


@assure_state
def get_available_versions(args=None, unknown=None):
    releases = []
    try:
        r = requests.get("https://www.renpy.org/dl/")
    except:  # noqa: E722
        print("Could not retrieve version list: No connection could be established.")
        print("This might mean that you are not connected to the internet or that renpy.org is down.")
        sys.exit(1)
    tree = html.fromstring(r.content)
    links = tree.xpath("//a/text()")
    for link in links:
        m = semver.match(link)
        if not m:
            continue
        try:
            version = Version(m.group(1))
            url = "https://www.renpy.org/dl/{0}/renpy-{0}-sdk.zip".format(m.group(1))
            release = RenpyRelease(version, url)
            releases.append(release)
        except ValueError:
            continue
    return sorted(releases, reverse=True)


def get_installed_versions(args=None, unknown=None):
    return sorted(get_registry(), reverse=True)


@assure_state
def list_versions(args, unknown):
    if args.available:
        releases = get_available_versions()
        if not releases:
            print("No releases are available.")
        else:
            for release in releases[:args.n]:
                print(release.version)
    else:
        instances = get_installed_versions()
        if not instances:
            print("No instances are currently installed.")
        else:
            for release in instances[:args.n]:
                print(release.version)


def installed(version):
    if isinstance(version, str):
        try:
            version = Version(version)
        except ValueError:
            return False
    for instance in get_registry():
        if instance.version == version:
            return True
    return False


def download(url, dest):
    response = requests.head(url)
    if response.status_code == 404:
        print("The engine package could not be found.")
        sys.exit(1)
    file_size = int(response.headers.get("Content-Length", -1))
    if os.path.exists(dest):
        first_byte = os.path.getsize(dest)
    else:
        first_byte = 0
    if first_byte >= file_size:
        return
    header = {"Range": "bytes={}-{}".format(first_byte, file_size)}
    progress_bar = tqdm(total=file_size, initial=first_byte, unit="B",
                        unit_scale=True, desc=url.split("/")[-1])
    req = requests.get(url, headers=header, stream=True)
    with(open(dest, "ab")) as f:
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                progress_bar.update(1024)
    progress_bar.close()


def get_members(zip):
    parts = []
    for name in zip.namelist():
        if not name.endswith('/'):
            parts.append(name.split('/')[:-1])
    prefix = os.path.commonprefix(parts)
    if prefix:
        prefix = '/'.join(prefix) + '/'
    offset = len(prefix)
    for zipinfo in zip.infolist():
        name = zipinfo.filename
        if len(name) > offset:
            zipinfo.filename = name[offset:]
            yield zipinfo


@assure_state
def install(args, unknown):
    if installed(args.version):
        print("{} is already installed!".format(args.version))
        sys.exit(1)
    if not valid_version(args.version):
        print("Invalid version specifier!")
        sys.exit(1)

    print("Downloading necessary files...")
    sdk_filename = "renpy-{0}-sdk.zip".format(args.version)
    rapt_filename = "renpy-{0}-rapt.zip".format(args.version)
    folder_name = args.version
    SDK_URL = "https://www.renpy.org/dl/{}/{}".format(args.version, sdk_filename)
    RAPT_URL = "https://www.renpy.org/dl/{}/{}".format(args.version, rapt_filename)
    download(SDK_URL, os.path.join(CACHE, sdk_filename))
    download(RAPT_URL, os.path.join(CACHE, rapt_filename))

    print("Extracting Ren'Py...")
    sdk_zip = ZipFile(os.path.join(CACHE, sdk_filename), "r")
    rapt_zip = ZipFile(os.path.join(CACHE, rapt_filename), "r")
    sdk_zip.extractall(path=os.path.join(CACHE, folder_name), members=get_members(sdk_zip))
    rapt_zip.extractall(path=os.path.join(CACHE, folder_name, "rapt"), members=get_members(rapt_zip))

    print("Installing RAPT...")
    os.environ["PGS4A_NO_TERMS"] = "no"
    rapt_path = os.path.join(CACHE, folder_name, "rapt")
    with cd(rapt_path):
        echo = Popen(["echo", """Y
Y
Y
renutil"""], stdout=PIPE)
        install = Popen(["python2", "android.py", "installsdk"], stdin=echo.stdout, stdout=PIPE)
        for line in install.stdout:
            if args.verbose:
                print(str(line.strip(), "utf-8"))
    del os.environ["PGS4A_NO_TERMS"]

    print("Registering instance...")
    instance = RenpyInstance(args.version, folder_name)
    add_to_registry(instance)

    head, _ = os.path.split(get_libraries(instance)[0])
    paths = [os.path.join(head, "python"), os.path.join(head, "pythonw"),
             os.path.join(head, "renpy"), os.path.join(head, "zsync"), os.path.join(head, "zsyncmake")]
    for path in paths:
        os.chmod(path, S_IRUSR | S_IXUSR)


@assure_state
def uninstall(args, unknown):
    if not installed(args.version):
        print("{} is not installed!".format(args.version))
        sys.exit(1)
    instance = get_instance(args.version)
    remove_from_registry(instance)
    shutil.rmtree(os.path.join(CACHE, instance.path))


def get_libraries(instance):
    info = os.uname()
    platform = "{}-{}".format(info.sysname, info.machine)
    root = instance.path
    root1 = root
    root2 = root
    lib = None
    if "Darwin" in info.sysname:
        platform = "darwin-x86_64"
        root1 = root + "/../Resources/autorun"
        root2 = root + "/../../.."
    elif "x86_64" in info.machine or "amd64" in info.machine:
        platform = "linux-x86_64"
        root1 = root
        root2 = root
    elif re.match(r"i.*86", info.machine):
        platform = "linux-i686"
        root1 = root
        root2 = root
    elif "Linux" in info.sysname:
        platform = "linux-{}".format(info.machine)
        root1 = root
        root2 = root
    else:
        print("Could not detect system architecture. It might not be supported.")
        sys.exit(1)

    for folder in [root, root1, root2]:
        lib = os.path.join(CACHE, folder, "lib", platform)
        if os.path.isdir(lib):
            break
    lib = os.path.join(lib, "renpy")

    if not lib:
        print("Ren'Py platform files not found in '{}'".format(os.path.join(root, "lib", platform)))

    if "LD_LIBRARY_PATH" in os.environ and len(os.environ["LD_LIBRARY_PATH"]) != 0:
        os.environ["LD_LIBRARY_PATH"] = "{}:{}".format(lib, os.environ["LD_LIBRARY_PATH"])

    for folder in [root, root1, root2]:
        base_file = os.path.join(CACHE, folder, "renpy.py")
        if os.path.isfile(base_file):
            break

    return [lib, "-EO", base_file]


@assure_state
def launch(args, unknown):
    if not installed(args.version):
        print("{} is not installed!".format(args.version))
        print("Available versions:")
        args.available = False
        args.n = 5
        list_versions(args, unknown)
        sys.exit(1)
    instance = get_instance(args.version)
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    cmd = get_libraries(instance)
    if not args.direct:
        cmd += [os.path.join(CACHE, instance.launcher_path)]
    cmd += unknown
    try:
        if args.verbose:
            print(" ".join(cmd))
        run(cmd)
    except KeyboardInterrupt:
        call_assure_state()
    del os.environ["SDL_AUDIODRIVER"]


@assure_state
def cleanup(args, unknown):
    if not installed(args.version):
        print("{} is not installed!".format(args.version))
        args.available = False
        args.n = 5
        list_versions(args, unknown)
        sys.exit(1)
    instance = get_instance(args.version)
    paths = [os.path.join(instance.path, "tmp"),
             os.path.join(instance.rapt_path, "assets"), os.path.join(instance.rapt_path, "bin")]
    for path in paths:
        if os.path.isdir(os.path.join(CACHE, path)):
            shutil.rmtree(os.path.join(CACHE, path))


main_description = """
"""


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent("""
                                                 A toolkit for managing Ren'Py instances via the command line.\n
                                                 Various versions of Ren'Py can be installed and launched at
                                                 the same time and completely independently from each other.\n
                                                 Instances can be launched with their GUI or CLI-only.""")
                                     )
    subparsers = parser.add_subparsers()

    parser_list = subparsers.add_parser("list", aliases=["ls"],
                                        formatter_class=argparse.RawDescriptionHelpFormatter,
                                        description=textwrap.dedent("""
                                                    List all installed versions of Ren'Py, or alternatively
                                                    query available versions from https://renpy.org/dl."""),
                                        help="List Ren'Py versions.")
    parser_list.add_argument("-n",
                             type=int,
                             default=5,
                             help="The number of versions to show (default: 5)")
    parser_list.add_argument("-a", "--available",
                             action="store_true",
                             help="Show versions available to be installed")
    parser_list.set_defaults(func=list_versions)

    parser_install = subparsers.add_parser("install", aliases=["i"],
                                           formatter_class=argparse.RawDescriptionHelpFormatter,
                                           description=textwrap.dedent("""
                                                       Install the specified version of Ren'Py (including RAPT),
                                                       set up for use via 'renutil launch'."""),
                                           help="Install a version of Ren'Py.",
                                           epilog=textwrap.dedent("""
                                                  This tool will automatically accept the Android SDK licenses for you
                                                  while installing any version of Ren'Py. If you are no okay with this,
                                                  you can not use this tool."""))
    parser_install.add_argument("version", type=str, help="The version to install in SemVer format")
    parser_install.add_argument("-v", "--verbose", action="store_true", help="Print more information when given")
    parser_install.set_defaults(func=install)

    parser_uninstall = subparsers.add_parser("uninstall", aliases=["u", "remove", "r", "rm"],
                                             formatter_class=argparse.RawDescriptionHelpFormatter,
                                             description=textwrap.dedent("""
                                                         Uninstall the specified version of Ren'Py, removing
                                                         all related artifacts and cache objects."""),
                                             help="Uninstall an installed version of Ren'Py.")
    parser_uninstall.add_argument("version",
                                  type=str,
                                  help="The version to uninstall in SemVer format")
    parser_uninstall.set_defaults(func=uninstall)

    description = """
    Launch the specified version of Ren'Py.\n
    If invoked with default arguments, starts the 'launcher' project,
    which results in starting up the regular GUI launcher interface.\n
    If invoked with the --direct flag, grants command-line access to
    'renpy.py' and hands off all subsequent arguments to its argument parser.\n
    Launch a project directly:
        renutil launch <version> -d <path_to_project_directory>\n
    Build PC / Linux / macOS distributions for a project:
        renutil launch <version> distribute <path_to_project_directory>\n
    Build Android distributions for a project:
        renutil launch <version> android_build <path_to_project_directory> assembleRelease|installDebug
    """

    # TODO: Android building is currently broken
    # because of incorrect permissions somewhere
    parser_launch = subparsers.add_parser("launch", aliases=["l"],
                                          formatter_class=argparse.RawDescriptionHelpFormatter,
                                          description=textwrap.dedent(description),
                                          help="Launch an installed version of Ren'Py.")

    parser_launch.add_argument("version",
                               type=str,
                               help="The version to launch in SemVer format")
    parser_launch.add_argument("-d", "--direct",
                               action="store_true",
                               help="Launches the Ren'Py script directly")
    parser_launch.add_argument("-v", "--verbose", action="store_true", help="Print more information when given")
    parser_launch.set_defaults(func=launch)

    parser_clear_cache = subparsers.add_parser("cleanup", aliases=["clean", "c"],
                                               formatter_class=argparse.RawDescriptionHelpFormatter,
                                               description=textwrap.dedent("""
                                                           Clean the temporary build artifacts of the specified version of Ren'Py."""),  # noqa: E501
                                               help="Clean temporary files of the specified Ren'Py version.")
    parser_clear_cache.add_argument("version",
                                    type=str,
                                    help="The version to clean in SemVer format")
    parser_clear_cache.set_defaults(func=cleanup)

    args, unknown = parser.parse_known_args()
    if vars(args).get("func", None):
        try:
            args.func(args, unknown)
        except KeyboardInterrupt:
            tqdm.write("Aborted")
    else:
        print("Type 'renutil -h' to see all available actions")


if __name__ == '__main__':
    main()
