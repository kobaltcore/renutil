# renUtil
A toolkit for managing Ren'Py instances via the command line.

renUtil can install, update, launch and remove instances of Ren'Py. The instances are completely independent from each other. It automatically sets up and configures RAPT so new instances are instantly ready to deploy to many different platforms. Best of all, renUtil automatically configures Ren'Py in such a way that you can run it headless, making it well suited for build servers and continuous integration pipelines.

## Installation
renUtil can be installed via pip:
```
$ pip install renutil
```

Please note that renUtil requires Python 3 and will not provide backwards compatibility for Python 2 for the foreseeable future.

## Usage
```
usage: renutil [-h]
               {list,ls,install,i,uninstall,u,remove,r,rm,launch,l,cleanup,clean,c}
               ...

A toolkit for managing Ren'Py instances via the command line.

positional arguments:
  {list,ls,install,i,uninstall,u,remove,r,rm,launch,l,cleanup,clean,c}
    list (ls)           List Ren'Py versions.
    install (i)         Install a version of Ren'Py.
    uninstall (u, remove, r, rm)
                        Uninstall an installed version of Ren'Py.
    launch (l)          Launch an installed version of Ren'Py.
    cleanup (clean, c)  Clean temporary files of the specified Ren'Py version.

optional arguments:
  -h, --help            show this help message and exit
```

# Disclaimer
renUtil is a hobby project and not in any way affiliated with Ren'Py. This means that there is no way I can guarantee that it will work at all, or continue to work once it does. Commands are mostly relayed to the Ren'Py CLI, so any issues with distribution building or startup are likely the fault of Ren'Py and not mine. renUtil is not likely to break on subsequent updates of Ren'Py, but it is not guaranteed that any available version will work correctly. Use this at your own discretion.
