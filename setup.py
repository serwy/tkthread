from setuptools import setup
from tkthread._version import __version__

with open('README.md', encoding='utf-8') as fid:
    LONG_DESCRIPTION = fid.read()

setup(
    name='tkthread',
    version=__version__,
    author='Roger D. Serwy',
    author_email='roger.serwy@gmail.com',
    license="Apache Version 2.0",
    keywords="tkinter threading",
    url="http://github.com/serwy/tkthread",
    packages=['tkthread'],
    description='Easy multithreading with Tkinter',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    platforms=["Windows", "Linux", "Solaris", "Mac OS-X", "Unix"],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: User Interfaces',
    ],
)
