import os
import setuptools

# scrape dependencies from the requirements.txt file
requirements = os.path.join(os.path.dirname(os.path.abspath('llpyspin')),'requirements.txt')
with open(requirements,'r') as stream:
    dependencies = [requirement.strip('\n') for requirement in stream.readlines()]

setuptools.setup(
    name="parallel-pyspin",
    version="0.2dev1",
    author="Joshua Hunt",
    author_email="hunt.brian.joshua@gmail.com",
    description="parallel and synchronous video acqusition with FLIR USB3 cameras",
    url="https://github.com/jbhunt/parallel-pyspin",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=dependencies,
    include_package_date=True,
    package_data={"":["*.yaml"]}
)
