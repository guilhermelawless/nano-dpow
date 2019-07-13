from distutils.core import setup

setup(name='nano_dpow_server',
      version='1.0',
      description='Nano Distributed Proof of Work Server',
      author='Guilherme Lawless',
      author_email='guilherme.lawless@gmail.com',
      packages=['dpow'],
      package_dir={"dpow": "dpow"},
      package_data={"": ["../LICENSE"]},
     )
