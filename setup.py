import setuptools

setuptools.setup(
    name="parallel-pyspin",
    version="0.1dev1",
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
)
