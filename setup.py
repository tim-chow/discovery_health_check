from setuptools import setup, find_packages

setup(
    name='discovery_health_check',
    version='1.0.0',
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        "redis>=2.10.5",
        "requests>=2.6.0"
    ],
    package_data={
        '': ['*.tpl'],
    },
    entry_points={
        "console_scripts": [
            "discovery_health_check = discovery_health_check.main:main",
        ]
    },

    author='timchow',
    author_email='744475502@qq.com',
    url='http://timd.cn/',
    description='discovery health check',
    keywords='ngx-service-discovery',
    license='MIT')
