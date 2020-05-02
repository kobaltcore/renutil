### System ###
import os
import re
import sys
import pickle
import shutil
import logging
import platform
from zipfile import ZipFile
from stat import S_IRUSR, S_IXUSR
from contextlib import contextmanager
from subprocess import run, PIPE, STDOUT, Popen

### Logging ###
import logzero
from logzero import logger

### CLI Parsing ###
import click

### I/O ###
import requests

### Parsing ###
from lxml import html
from semantic_version import Version

### Display ###
from tqdm import tqdm


semver = re.compile(r"^((0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(\+[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*)?)/?$")  # noqa: E501


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail("Too many matches: {}".format(", ".join(sorted(matches))))


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


class Registry():

    def __init__(self, filename):
        self.filename = filename
        self.instances = []

    def load(self):
        if not os.path.isfile(self.filename):
            self.persist()
        with open(self.filename, "rb") as f:
            self.instances = pickle.load(f)

    def persist(self):
        with open(self.filename, "wb") as f:
            pickle.dump(self.instances, f)

    def clear(self):
        self.instances = []
        self.persist()

    def add_instance(self, instance):
        self.load()
        if instance in self.instances:
            return

        self.instances.append(instance)

        self.persist()

    def remove_instance(self, instance):
        self.load()
        if instance not in self.instances:
            return

        for i, inst in enumerate(self.instances):
            if inst.version == instance.version:
                del self.instances[i]

        self.persist()

    def get_instance(self, version):
        self.load()
        if isinstance(version, str):
            try:
                version = Version(version)
            except ValueError:
                return None

        for instance in self.instances:
            if instance.version == version:
                return instance

        return None

    def installed(self, version):
        self.load()
        if isinstance(version, str):
            try:
                version = Version(version)
            except ValueError:
                return False

        for instance in self.instances:
            if instance.version == version:
                return True

        return False

    def __iter__(self):
        return iter(self.instances)


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


def assure_state():
    if not os.path.isdir(CACHE):
        logger.debug("Cache directory does not exist, creating it:\n{}".format(CACHE))
        os.mkdir(CACHE)
    if not os.access(CACHE, os.R_OK | os.W_OK):
        logger.debug("Cache directory is not writeable:\n{}\nPlease make sure this script has permission to write to this directory.".format(CACHE))  # noqa: E501
        sys.exit(1)
    instances = scan_instances(CACHE)
    REGISTRY.clear()
    for instance in instances:
        REGISTRY.add_instance(instance)


def valid_version(version):
    if isinstance(version, str):
        try:
            version = Version(version)
        except ValueError:
            return False
    # registry = get_registry()
    for instance in REGISTRY:
        if instance.version == version:
            return True
    releases = get_available_versions()
    for release in releases:
        if release.version == version:
            return True
    return False


def get_available_versions(args=None, unknown=None):
    assure_state()
    releases = []
    try:
        r = requests.get("https://www.renpy.org/dl/")
    except:  # noqa: E722
        logger.error("Could not retrieve version list: No connection could be established.")
        logger.error("This might mean that you are not connected to the internet or that renpy.org is down.")
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
    return sorted(REGISTRY, reverse=True)


@click.group(cls=AliasedGroup)
@click.option("-d", "--debug", is_flag=True)
@click.option("-r", "--registry", default=None, type=str,
              help="The path to store Ren'Py instances in")
def cli(debug, registry):
    """Commands can be abbreviated by the shortest unique string.

    \b
    For example:
        clean -> c
        la -> launch
        li -> list
    """
    global CACHE, REGISTRY

    if registry:
        registry = os.path.abspath(registry)
        os.makedirs(registry, exist_ok=True)
        CACHE = registry
    else:
        CACHE = os.path.join(os.path.expanduser("~"), ".renutil")
    REGISTRY = Registry(os.path.join(CACHE, "index.bin"))

    logger.debug("Registry Location: {}".format(CACHE))

    logzero.loglevel(logging.DEBUG if debug else logging.INFO)


@cli.command()
@click.option("-a/-l", "--all/--local", "show_all", default=False,
              help="Show all versions available to download or just the local ones")
@click.option("-n", "--num-versions", "count", default=5, type=int,
              help="Amount of versions to show, sorted in descending order")
def list(show_all, count):
    """List all available versions of Ren'Py.
    """
    assure_state()
    if show_all:
        releases = get_available_versions()
        if not releases:
            logger.warning("No releases are available online.")
        else:
            for release in releases[:count]:
                click.echo(release.version)
    else:
        instances = get_installed_versions()
        if not instances:
            logger.warning("No instances are currently installed.")
        else:
            for release in instances[:count]:
                click.echo(release.version)


def download(url, dest):
    response = requests.head(url)
    if response.status_code == 404:
        logger.error("The package could not be found.")
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


def get_members_zip(zip):
    parts = []
    for name in zip.namelist():
        if not name.endswith("/"):
            data = name.split("/")[:-1]
            if data:
                parts.append(data)
    prefix = os.path.commonprefix(parts)
    if prefix:
        prefix = "/".join(prefix) + "/"
    offset = len(prefix)
    for zipinfo in zip.infolist():
        name = zipinfo.filename
        if len(name) > offset:
            zipinfo.filename = name[offset:]
            yield zipinfo


def get_members_tar(tar):
    parts = []
    for name in tar.getnames():
        if not name.endswith("/"):
            data = name.split("/")[:-1]
            if data:
                parts.append(data)
    prefix = os.path.commonprefix(parts)
    if prefix:
        prefix = "/".join(prefix) + "/"
    offset = len(prefix)
    for tarinfo in tar.getmembers():
        name = tarinfo.name
        if len(name) > offset:
            tarinfo.name = name[offset:]
            yield tarinfo


def patch_file(file, target_line, patch, reverse=False):
    with open(file, "r") as f:
        data = f.readlines()

    found = False
    with open(file, "w") as f:
        for line in data:
            if found:
                if reverse:
                    f.write(line)
                    f.write(patch)
                else:
                    f.write(patch)
                    f.write(line)
                found = False
            else:
                f.write(line)
            if target_line in line:
                found = True


@cli.command()
@click.argument("version", required=True, type=str)
@click.option("-f", "--force", is_flag=True)
def install(version, force):
    """Install the specified version of Ren'Py (including RAPT).
    """
    assure_state()
    if REGISTRY.installed(version):
        if force:
            logger.info("Uninstalling {} before reinstalling...".format(version))
            instance = REGISTRY.get_instance(version)
            REGISTRY.remove_instance(instance)
            shutil.rmtree(os.path.join(CACHE, instance.path))
            logger.info("Done uninstalling")
        else:
            logger.error("{} is already installed!".format(version))
            sys.exit(1)
    if not valid_version(version):
        logger.error("Invalid version specifier!")
        sys.exit(1)

    logger.info("Downloading necessary files...")
    sdk_filename = "renpy-{}-sdk.zip".format(version)
    rapt_filename = "renpy-{}-rapt.zip".format(version)

    SDK_URL = "https://www.renpy.org/dl/{}/{}".format(version, sdk_filename)
    RAPT_URL = "https://www.renpy.org/dl/{}/{}".format(version, rapt_filename)

    download(SDK_URL, os.path.join(CACHE, sdk_filename))
    download(RAPT_URL, os.path.join(CACHE, rapt_filename))

    logger.info("Extracting files...")
    sdk_zip = ZipFile(os.path.join(CACHE, sdk_filename), "r")
    rapt_zip = ZipFile(os.path.join(CACHE, rapt_filename), "r")
    sdk_zip.extractall(path=os.path.join(CACHE, version), members=get_members_zip(sdk_zip))
    rapt_zip.extractall(path=os.path.join(CACHE, version, "rapt"), members=get_members_zip(rapt_zip))

    logger.info("Installing RAPT...")
    rapt_path = os.path.join(CACHE, version, "rapt")

    arch = get_platform()
    if arch == "windows-i686":
        python_path = os.path.join(CACHE, version, "lib", arch, "python.exe")
    else:
        python_path = os.path.join(CACHE, version, "lib", arch, "python")
        os.chmod(python_path, S_IRUSR | S_IXUSR)
    site_package_path = os.path.join(CACHE, version, "lib", arch, "lib", "python2.7")

    with cd(rapt_path):
        patch = "sys.path.insert(0, '{}')\n\nimport ssl\nssl._create_default_https_context = ssl._create_unverified_context\n".format(site_package_path)  # noqa: E501
        patch_file("android.py", "import sys", patch, reverse=True)

        patch_file(os.path.join("buildlib", "rapt", "interface.py"),
                   "def yesno_choice(self, prompt, default=None):",
                   "        return True\n")

        patch_file(os.path.join("buildlib", "rapt", "interface.py"),
                   "def input(self, prompt, empty=None):",
                   "        return \"renutil\"\n")

    os.environ["RAPT_NO_TERMS"] = "no"
    with cd(rapt_path):
        logger.debug("Running {}".format(" ".join((python_path, "-O", "android.py", "installsdk"))))
        install = Popen([python_path, "-O", "android.py", "installsdk"], stdout=PIPE, stderr=STDOUT)
        for line in install.stdout:
            line = line.strip()
            if line:
                logger.debug(str(line, "latin-1"))
    del os.environ["RAPT_NO_TERMS"]

    logger.info("Registering instance...")
    instance = RenpyInstance(version, version)
    REGISTRY.add_instance(instance)

    head, _ = os.path.split(get_libraries(instance)[0])
    if arch != "windows-i686":
        paths = [os.path.join(head, "python"), os.path.join(head, "pythonw"),
                 os.path.join(head, "renpy"), os.path.join(head, "zsync"),
                 os.path.join(head, "zsyncmake"),
                 os.path.join(CACHE, instance.rapt_path, "project", "gradlew")]
        for path in paths:
            os.chmod(path, S_IRUSR | S_IXUSR)

    with open(os.path.join(CACHE, instance.rapt_path, "project", "gradle.properties"), "r") as f:
        original_content = f.readlines()

    with open(os.path.join(CACHE, instance.rapt_path, "project", "gradle.properties"), "w") as f:
        for line in original_content:
            if line.startswith("org.gradle.jvmargs"):
                f.write("org.gradle.jvmargs=-Xmx8g\n")
            else:
                f.write(line)

    logger.info("Done installing {}".format(version))


@cli.command()
@click.argument("version", required=True, type=str)
def uninstall(version):
    """Uninstall the specified Ren'Py version.
    """
    assure_state()
    if not REGISTRY.installed(version):
        logger.error("{} is not installed!".format(version))
        sys.exit(1)
    instance = REGISTRY.get_instance(version)
    REGISTRY.remove_instance(instance)
    shutil.rmtree(os.path.join(CACHE, instance.path))


def get_platform():
    logger.debug("System: {}".format(platform.system()))
    logger.debug("Machine: {}".format(platform.machine()))

    if "Darwin" in platform.system():
        return "darwin-x86_64"
    elif "Windows" in platform.system():
        return "windows-i686"
    elif "x86_64" in platform.machine() or "amd64" in platform.machine():
        return "linux-x86_64"
    elif re.match(r"i.*86", platform.machine()):
        return "linux-i686"
    elif "Linux" in platform.system():
        return "linux-{}".format(platform.machine())


def get_libraries(instance):
    root = instance.path
    root1 = root
    root2 = root
    lib = None
    arch = get_platform()

    if arch == "darwin-x86_64":
        root1 = root + "/../Resources/autorun"
        root2 = root + "/../../.."
    elif arch == "windows-i686":
        root1 = root
        root2 = root
    elif arch == "linux-x86_64":
        root1 = root
        root2 = root
    elif arch == "linux-i686":
        root1 = root
        root2 = root
    elif arch.startswith("linux-"):
        root1 = root
        root2 = root
    else:
        logger.error("Could not detect system architecture. It might not be supported.")
        sys.exit(1)

    for folder in [root, root1, root2]:
        lib = os.path.join(CACHE, folder, "lib", arch)
        if os.path.isdir(lib):
            break
    if arch == "windows-i686":
        lib = os.path.join(lib, "renpy.exe")
    else:
        lib = os.path.join(lib, "renpy")

    if not lib:
        logger.error("Ren'Py platform files not found in '{}'".format(os.path.join(root, "lib", arch)))

    if "LD_LIBRARY_PATH" in os.environ and len(os.environ["LD_LIBRARY_PATH"]) != 0:
        os.environ["LD_LIBRARY_PATH"] = "{}:{}".format(lib, os.environ["LD_LIBRARY_PATH"])

    for folder in [root, root1, root2]:
        base_file = os.path.join(CACHE, folder, "renpy.py")
        if os.path.isfile(base_file):
            break

    return [lib, "-EO", base_file]


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("version", required=True, type=str)
@click.option("-d", "--direct", is_flag=True)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def launch(version, direct, args):
    """Launch the specified version of Ren'Py.

    If invoked with default arguments, starts the 'launcher' project,
    which results in starting up the regular GUI launcher interface.

    If invoked with the --direct flag, grants command-line access to
    'renpy.py' and hands off all subsequent arguments to its argument parser.

    \b
    Launch a project directly:
        renutil launch <version> -d <path_to_project_directory>

    \b
    Build PC / Linux / macOS distributions for a project:
        renutil launch <version> distribute <path_to_project_directory>

    \b
    Build Android distributions for a project:
        renutil launch <version> android_build <path_to_project_directory> assembleRelease|installDebug

    \b
    Lint a project:
        renutil launch -d <version> <path_to_project_directory> lint
    """
    assure_state()
    if not REGISTRY.installed(version):
        logger.error("{} is not installed!".format(version))
        sys.exit(1)
    instance = REGISTRY.get_instance(version)
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    cmd = get_libraries(instance)
    if not direct:
        cmd += [os.path.join(CACHE, instance.launcher_path)]
    cmd += args
    try:
        logger.debug(" ".join(cmd))
        run(cmd)
    except KeyboardInterrupt:
        assure_state()
    del os.environ["SDL_AUDIODRIVER"]


@cli.command()
@click.argument("version", required=True, type=str)
def cleanup(version):
    """Clean temporary files of the specified Ren'Py version.
    """
    assure_state()
    if not REGISTRY.installed(version):
        logger.error("{} is not installed!".format(version))
        sys.exit(1)
    instance = REGISTRY.get_instance(version)
    paths = [os.path.join(instance.path, "tmp"),
             os.path.join(instance.rapt_path, "assets"),
             os.path.join(instance.rapt_path, "bin"),
             os.path.join(instance.rapt_path, "project", "app")]
    for path in paths:
        if os.path.isdir(os.path.join(CACHE, path)):
            shutil.rmtree(os.path.join(CACHE, path))


if __name__ == '__main__':
    cli()
