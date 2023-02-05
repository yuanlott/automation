from genie.testbed import load
from genie.libs.parser.utils.entry_points import add_parser
from extraparsers.top import Top

if __name__ == "__main__":
    testbed = load("testbed.yml")
    device = testbed.devices["sudan"]
    device.connect()
    # dmethods = [m for m in dir(device) if callable(getattr(device, m))]
    add_parser(Top, "linux")
    top_data = device.parse("top -n 1 -b", fuzzy=True)
    print(top_data)
    device.disconnect()
