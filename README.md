# renUtil
A toolkit for managing Ren'Py instances via the command line.

renUtil can install, update, launch and remove instances of Ren'Py. The instances are completely independent from each other. It automatically sets up and configures RAPT so new instances are instantly ready to deploy for many different platforms.

## Usage
```
usage: renutil [-h] {list,install,uninstall,remove,launch} ...

A toolkit for managing Ren'Py instances via the command line.

positional arguments:
  {list,install,uninstall,remove,launch}
    list                List Ren'Py versions.
    install             Install a version of Ren'Py.
    uninstall (remove)  Uninstall an installed version of Ren'Py.
    launch              Launch an installed version of Ren'Py.

optional arguments:
  -h, --help            show this help message and exit
```
