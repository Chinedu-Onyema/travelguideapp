#!/bin/bash
# Python code standards
echo ==== PyLint checking ====
pylint *.py

# Coverage reports
echo ==== Code Coverage Report ====
coverage run -m unittest discover
coverage html

# View coverage in a web server
echo === View coverage results - press Ctrl-C to exit ====
python3 -m http.server -d htmlcov/ &> /dev/null