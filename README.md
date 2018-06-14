# renUtil
A toolkit for managing Ren'Py instances via the command line.

renUtil can install, update, launch and remove instances of Ren'Py. The instances are completely independent from each other. It automatically sets up and configures RAPT so new instances are instantly ready to deploy for many different platforms.

## Installation
renUtil can be installed via pip:
```
$ pip install renutil
```

Please note that renUtil requires Python 3 and will not provide backwards compatibility for Python 2 for the foreseeable future.

## Usage
```
usage: renutil [-h] {list,ls,install,i,uninstall,u,remove,r,rm,launch,l} ...

A toolkit for managing Ren'Py instances via the command line.

positional arguments:
  {list,ls,install,i,uninstall,u,remove,r,rm,launch,l}
    list (ls)           List Ren'Py versions.
    install (i)         Install a version of Ren'Py.
    uninstall (u, remove, r, rm)
                        Uninstall an installed version of Ren'Py.
    launch (l)          Launch an installed version of Ren'Py.

optional arguments:
  -h, --help            show this help message and exit
```
