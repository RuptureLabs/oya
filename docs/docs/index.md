# Welcome to Oya

Oya is a thin fonctionnal layer over litestar and tortoise orm, designed with fast templating in mind.

## Installation

to install oya type this command

    $ pip install https://github.com/oya-0.1.gz

## CLI Usage
* `oya project_name -p [or --project]` - Create a new project.
* `oya project_name --project --directory MyappFolder` - Create new in the target directory.
* `oya app_name -a [or --application] [--directory MyAppFolder]` - Create new app like django application.
* `oya --version` - show the installed oya version
* `oya --help` - Print help message and exit.

## Project layout
After project is created, this will be the project structure

    $ oya MyProject --project

This will the result :

    MyProject/    # The configuration file.
        MyProject/
            main.py  # this file contains the definition of the litestar application install.
            settings.py  # the oya settings file
        manage.py  # oya shell interface

## Application layout
Application must be created in a project folder, by the following command

    $ oya MyApp --application 

Or by targeting the project folder

    $ oya MyApp --application --directory MyProject

This will the result :

    MyProject/    # The configuration file.
        MyProject/
            main.py  # this file contains the definition of the litestar application install.
            settings.py  # the oya settings file
        manage.py  # oya shell interface

        myapp/
            apps.py
            endpoints.py
            models.py
            tests.py

[!NOTE]
the application's name must be a valid identifier


## Version & Help

Check oya version

    $ oya --version

print the page

    $ oya --help
