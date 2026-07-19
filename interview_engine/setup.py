from setuptools import find_packages, setup

setup(
    name="independent-ai-interview-engine",
    version="0.1.0",
    description="Standalone AI technical interview engine",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.110",
        "uvicorn[standard]>=0.29",
        "pydantic>=2.0",
        "python-dotenv>=1.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0", "httpx>=0.27"],
    },
)
