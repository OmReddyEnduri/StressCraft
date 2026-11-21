from setuptools import setup, find_packages

setup(
    name="stresscraft",
    version="0.1.0",
    description="High-performance automated competitive programming differential fuzzing, testcase generator, and delta-debugging counterexample minimizer engine.",
    author="Om Reddy Enduri",
    author_email="omreddyenduri@gmail.com",
    url="https://github.com/OmReddyEnduri/StressCraft",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "rich>=12.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stresscraft = stresscraft.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
