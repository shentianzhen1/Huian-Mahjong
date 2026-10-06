"""Keep package-local regression modules out of distributable runtime wheels."""
from setuptools import setup
from setuptools.command.build_py import build_py


class RuntimeBuildPy(build_py):
    def find_package_modules(self, package, package_dir):
        return [
            item for item in super().find_package_modules(package, package_dir)
            if not item[1].startswith('test_')
        ]


setup(cmdclass={'build_py': RuntimeBuildPy})
