from setuptools import setup, find_packages
import moadevs


setup(
    name='MoaDevs',
    version=moadevs.__version__,
    packages=find_packages(),
    install_requires=['moa'],
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    license='MIT',
    description=(
        'Moa interfaced devices for the CPL lab.')
    )
