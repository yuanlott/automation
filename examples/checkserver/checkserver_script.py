#!/usr/bin/env python
###################################################################
# connection_example.py : A test script example which includes:
#     common_seup section - device connection, configuration
#     Tescase section with testcase setup and teardown (cleanup)
#     common_cleanup section - device cleanup
###################################################################

# To get a logger for the script
import logging

# Needed for aetest script
from pyats import aetest
from genie.libs.parser.utils.entry_points import add_parser

# my lib
from extraparsers.top import Top


# Get your logger for your script
log = logging.getLogger()

###################################################################
###                  COMMON SETUP SECTION                       ###
###################################################################

# This is how to create a CommonSetup
# You can have one of no CommonSetup
# CommonSetup can be named whatever you want


class common_setup(aetest.CommonSetup):
    """Common Setup section"""

    # CommonSetup have subsection.
    # You can have 1 to as many subsection as wanted

    # 1st subsection
    @aetest.subsection
    def connect(self, testscript, testbed):
        """Common Setup subsection"""
        log.info("Aetest Common Setup: connect to device")
        device = testbed.devices["egypt"]
        # Connecting to the devices using the default connection
        device.connect()

        # Save it in testscript parmaeters to be able to use it from other
        # test sections
        testscript.parameters["uut"] = device

    # 2nd subsection
    @aetest.subsection
    def register_parser(self, section):
        log.info("Aetest Common Setup: add parser")
        # register my parser
        add_parser(Top, "linux")

        # Save it in testscript parmaeters to be able to use it from other


###################################################################
###                     TESTCASES SECTION                       ###
###################################################################

# This is how to create a testcase
# You can have 0 to as many testcase as wanted


# Testcase name : tc_one
class test_top(aetest.Testcase):
    """This is user Testcases section"""

    # Testcases are divided into 3 sections
    # Setup, Test and Cleanup.

    # This is how to create a setup section
    @aetest.setup
    def send_command(self, uut):
        # Get device output
        self.output = uut.parse("top -n 1 -b")

        # Configuration can also be send
        # uut.configure('some configuration')


#####################################################################
####                       COMMON CLEANUP SECTION                 ###
#####################################################################


# This is how to create a CommonCleanup
# You can have 0 , or 1 CommonCleanup.
# CommonCleanup can be named whatever you want :)
class common_cleanup(aetest.CommonCleanup):
    """Common Cleanup for Sample Test"""

    # CommonCleanup follow exactly the same rule as CommonSetup regarding
    # subsection
    # You can have 1 to as many subsection as wanted

    @aetest.subsection
    def disconnect(self, uut):
        """Common Cleanup Subsection"""
        uut.disconnect()
