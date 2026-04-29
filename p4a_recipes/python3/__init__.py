import os
from os.path import dirname
from pythonforandroid.recipes.python3 import Python3Recipe


_ANDROID_STUBS = (
    '\n#ifdef __ANDROID__\n'
    '/* setgrent/getgrent/endgrent absent from Android bionic */\n'
    'static void setgrent(void) {}\n'
    'static void endgrent(void) {}\n'
    'static struct group *getgrent(void) { return NULL; }\n'
    '#endif\n'
)


class Python3RecipeFixed(Python3Recipe):

    def apply_patches(self, arch):
        # Upstream patches live next to the real Python3Recipe, not in our
        # local recipe dir. Temporarily point recipe_dir there so that
        # apply_patch() can find them, then restore.
        import pythonforandroid.recipes.python3 as _upstream_mod
        upstream_dir = dirname(_upstream_mod.__file__)
        orig_dir = self._recipe_dir
        self._recipe_dir = upstream_dir
        try:
            super().apply_patches(arch)
        finally:
            self._recipe_dir = orig_dir

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        # Patch grpmodule.c after upstream patches are applied
        grp = os.path.join(
            self.get_build_dir(arch.arch), 'Modules', 'grpmodule.c'
        )
        if not os.path.exists(grp):
            return
        src = open(grp, encoding='utf-8').read()
        if '__ANDROID__' in src:
            return
        patched = src.replace(
            '#include <grp.h>\n',
            '#include <grp.h>\n' + _ANDROID_STUBS,
            1,
        )
        if patched == src:
            patched = src.replace(
                '#include <grp.h>',
                '#include <grp.h>' + _ANDROID_STUBS,
                1,
            )
        open(grp, 'w', encoding='utf-8').write(patched)


recipe = Python3RecipeFixed()
