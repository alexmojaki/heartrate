import os
import re

from setuptools import setup

package = 'heartrate'

# __version__ is defined inside the package, but we can't import
# it because it imports dependencies which may not be installed yet,
# so we extract it manually
init_path = os.path.join(os.path.dirname(__file__),
                         package,
                         '__init__.py')
with open(init_path) as f:
    contents = f.read()
__version__ = re.search(r"__version__ = '([.\d]+)'", contents).group(1)

install_requires = [
    'pygments',
    'Flask',
]

setup(name=package,
      version=__version__,
      description='Simple real time visualisation of the execution of a Python program.',
      url='https://github.com/alexmojaki/' + package,
      author='Alex Hall',
      author_email='alex.mojaki@gmail.com',
      license='MIT',
      packages=[package],
      install_requires=install_requires,
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
      ],
      package_data={'': [os.path.join(root, filename)[len(package + '/'):]
                         for root, dirnames, filenames in os.walk(package)
                         for filename in filenames
                         if not filename.endswith('.pyc')]},
      zip_safe=False)
