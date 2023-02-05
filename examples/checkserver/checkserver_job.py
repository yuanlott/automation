import os
from pyats.easypy import run

# To run the job:
# Inside your python virtual environment
# pyats run job checkserver_job.py --testbed-file testbed.yml
#
# Description: This example uses linux servers as sample testbed,
#              connects to a device whose name is passed from the job file,
#              executes some system checking commands,
#              and verifies the result.


# All run() must be inside a main function
def main():
    # Find the location of the script in relation to the job file
    test_path = os.path.dirname(os.path.abspath(__file__))
    testscript = os.path.join(test_path, "checkserver_script.py")

    # Execute the testscript
    run(testscript=testscript)
