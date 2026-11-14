# Used by catkin_python_setup() only; do not run directly.
from catkin_pkg.python_setup import generate_distutils_setup
from setuptools import setup

setup(
    **generate_distutils_setup(
        packages=["ai_perception", "ai_perception.sources"], package_dir={"": "src"}
    )
)
