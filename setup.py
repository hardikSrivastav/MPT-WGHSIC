from setuptools import setup, find_packages

setup(
    name="mpt",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'Flask',
        'python-dotenv',
        'redis',
        'psycopg2-binary',
    ],
) 