import pathlib
import sys
import os.path
def installer_func():
    plugin_dir = os.path.dirname(os.path.realpath(__file__))

    try:
        import pip
    except ImportError:
        exec(
            open(str(pathlib.Path(plugin_dir, 'scripts', 'get_pip.py'))).read()
        )
        import pip
        # just in case the included version is old
        pip.main(['install', '--upgrade', 'pip'])

    sys.path.append(plugin_dir)

    with open(os.path.join(plugin_dir,'requirements.txt'), "r") as requirements:
        for dep in requirements.readlines():
            dep = dep.strip().split("==")[0]
            try:
                __import__(dep)
            except ImportError as e:
                print("{} not available, installing".format(dep))
                pip.main(['install', dep])