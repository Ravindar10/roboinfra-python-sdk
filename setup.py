from setuptools import setup, find_packages

setup(
    name='roboinfra-sdk',
    version='1.0.11',
    description='Python SDK for RoboInfra URDF validation, kinematic analysis, 3D model conversion and mesh analysis APIs for ROS developers',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='RoboInfra',
    url='https://github.com/Ravindar10/roboinfra-python-sdk',
    keywords=[
        'robotics', 'ros', 'urdf', 'validation', 'robot',
        'kinematic', '3d-model', 'mesh-analysis', 'gazebo',
        'ci-cd', 'urdf-validator', 'model-conversion',
        'stl', 'fbx', 'obj', 'gltf', 'moveit'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    python_requires='>=3.8',
    install_requires=['requests>=2.20.0'],
    packages=['roboinfra'],
)