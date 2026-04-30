from pythonforandroid.recipes.python3 import Python3Recipe
from pythonforandroid.patching import version_starts_with


class Python3RecipeFixed(Python3Recipe):
    # Full copy of upstream patches plus our Android bionic fix.
    # Patch files live in ./patches/ alongside this file — no recipe_dir tricks.
    patches = [
        'patches/pyconfig_detection.patch',
        'patches/reproducible-buildinfo.diff',

        # Python 3.7
        ('patches/py3.7.1_fix-ctypes-util-find-library.patch', version_starts_with('3.7')),
        ('patches/py3.7.1_fix-zlib-version.patch',              version_starts_with('3.7')),

        # Python 3.8 / 3.9 / 3.10
        ('patches/py3.8.1.patch', version_starts_with('3.8')),
        ('patches/py3.8.1.patch', version_starts_with('3.9')),
        ('patches/py3.8.1.patch', version_starts_with('3.10')),

        # Python 3.11+
        ('patches/cpython-311-ctypes-find-library.patch', version_starts_with('3.11')),

        # Android bionic: stub out missing group-enumeration functions
        'patches/fix-grpmodule-android.patch',
    ]


recipe = Python3RecipeFixed()
