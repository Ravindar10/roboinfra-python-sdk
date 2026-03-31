from setuptools import setup, find_packages

setup(
    name="roboinfra-sdk",
    version="1.0.5",
    description="Python SDK for RoboInfra URDF validation, Mesh Analyzer and 3D Model Converter robotics APIs",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Ravindar J",
    url="https://pypi.org/project/roboinfra-sdk/",
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.8",
    keywords="robotics urdf api sdk mesh ros 3d-model",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Intended Audience :: Developers",
    ],
)